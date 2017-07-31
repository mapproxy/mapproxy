# This file is part of the MapProxy project.
# Copyright (C) 2016-2017 Omniscale <http://omniscale.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import errno
import hashlib
import os
import shutil
import struct

from mapproxy.image import ImageSource
from mapproxy.cache.base import TileCacheBase, tile_buffer
from mapproxy.util.fs import ensure_directory, write_atomic
from mapproxy.util.lock import FileLock
from mapproxy.compat import BytesIO

import logging
log = logging.getLogger(__name__)


class CompactCacheBase(TileCacheBase):
    supports_timestamp = False
    bundle_class = None

    def __init__(self, cache_dir):
        self.lock_cache_id = 'compactcache-' + hashlib.md5(cache_dir.encode('utf-8')).hexdigest()
        self.cache_dir = cache_dir

    def _get_bundle(self, tile_coord):
        x, y, z = tile_coord

        level_dir = os.path.join(self.cache_dir, 'L%02d' % z)

        c = x // BUNDLEX_V1_GRID_WIDTH * BUNDLEX_V1_GRID_WIDTH
        r = y // BUNDLEX_V1_GRID_HEIGHT * BUNDLEX_V1_GRID_HEIGHT

        basename = 'R%04xC%04x' % (r, c)
        return self.bundle_class(os.path.join(level_dir, basename), offset=(c, r))

    def is_cached(self, tile):
        if tile.coord is None:
            return True
        if tile.source:
            return True

        return self._get_bundle(tile.coord).is_cached(tile)

    def store_tile(self, tile):
        if tile.stored:
            return True

        return self._get_bundle(tile.coord).store_tile(tile)

    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True

        return self._get_bundle(tile.coord).load_tile(tile)

    def remove_tile(self, tile):
        if tile.coord is None:
            return True

        return self._get_bundle(tile.coord).remove_tile(tile)

    def load_tile_metadata(self, tile):
        if self.load_tile(tile):
            tile.timestamp = -1

    def remove_level_tiles_before(self, level, timestamp):
        if timestamp == 0:
            level_dir = os.path.join(self.cache_dir, 'L%02d' % level)
            shutil.rmtree(level_dir, ignore_errors=True)
            return True
        return False

BUNDLE_EXT = '.bundle'
BUNDLEX_V1_EXT = '.bundlx'

class BundleV1(object):
    def __init__(self, base_filename, offset):
        self.base_filename = base_filename
        self.lock_filename = base_filename + '.lck'
        self.offset = offset

    def _rel_tile_coord(self, tile_coord):
        return (
            tile_coord[0] % BUNDLEX_V1_GRID_WIDTH,
            tile_coord[1] % BUNDLEX_V1_GRID_HEIGHT,
        )

    def is_cached(self, tile):
        if tile.source or tile.coord is None:
            return True

        idx = BundleIndexV1(self.base_filename + BUNDLEX_V1_EXT)
        x, y = self._rel_tile_coord(tile.coord)
        offset = idx.tile_offset(x, y)
        if offset == 0:
            return False

        bundle = BundleDataV1(self.base_filename + BUNDLE_EXT, self.offset)
        size = bundle.read_size(offset)
        return size != 0

    def store_tile(self, tile):
        if tile.stored:
            return True

        with tile_buffer(tile) as buf:
            data = buf.read()

        with FileLock(self.lock_filename):
            bundle = BundleDataV1(self.base_filename + BUNDLE_EXT, self.offset)
            idx = BundleIndexV1(self.base_filename + BUNDLEX_V1_EXT)
            x, y = self._rel_tile_coord(tile.coord)
            offset = idx.tile_offset(x, y)
            offset, size = bundle.append_tile(data, prev_offset=offset)
            idx.update_tile_offset(x, y, offset=offset, size=size)

        return True

    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True

        idx = BundleIndexV1(self.base_filename + BUNDLEX_V1_EXT)
        x, y = self._rel_tile_coord(tile.coord)
        offset = idx.tile_offset(x, y)
        if offset == 0:
            return False

        bundle = BundleDataV1(self.base_filename + BUNDLE_EXT, self.offset)
        data = bundle.read_tile(offset)
        if not data:
            return False
        tile.source = ImageSource(BytesIO(data))

        return True

    def remove_tile(self, tile):
        if tile.coord is None:
            return True

        with FileLock(self.lock_filename):
            idx = BundleIndexV1(self.base_filename + BUNDLEX_V1_EXT)
            x, y = self._rel_tile_coord(tile.coord)
            idx.remove_tile_offset(x, y)

        return True


BUNDLEX_V1_GRID_WIDTH = 128
BUNDLEX_V1_GRID_HEIGHT = 128
BUNDLEX_V1_HEADER_SIZE = 16
BUNDLEX_V1_HEADER = b'\x03\x00\x00\x00\x10\x00\x00\x00\x00\x40\x00\x00\x05\x00\x00\x00'
BUNDLEX_V1_FOOTER_SIZE = 16
BUNDLEX_V1_FOOTER = b'\x00\x00\x00\x00\x10\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00'

class BundleIndexV1(object):
    def __init__(self, filename):
        self.filename = filename
        # defer initialization to update/remove calls to avoid
        # index creation on is_cached (prevents new files in read-only caches)
        self._initialized = False

    def _init_index(self):
        self._initialized = True
        if os.path.exists(self.filename):
            return
        ensure_directory(self.filename)
        buf = BytesIO()
        buf.write(BUNDLEX_V1_HEADER)
        for i in range(BUNDLEX_V1_GRID_WIDTH * BUNDLEX_V1_GRID_HEIGHT):
            buf.write(struct.pack('<Q', (i*4)+BUNDLE_V1_HEADER_SIZE)[:5])
        buf.write(BUNDLEX_V1_FOOTER)
        write_atomic(self.filename, buf.getvalue())

    def _tile_offset(self, x, y):
        return BUNDLEX_V1_HEADER_SIZE + (x * BUNDLEX_V1_GRID_HEIGHT + y) * 5

    def tile_offset(self, x, y):
        idx_offset = self._tile_offset(x, y)
        try:
            with open(self.filename, 'rb') as f:
                f.seek(idx_offset)
                offset = struct.unpack('<Q', f.read(5) + b'\x00\x00\x00')[0]
            return offset
        except IOError as ex:
            if ex.errno == errno.ENOENT:
                # mising bundle file -> missing tile
                return 0
            raise

    def update_tile_offset(self, x, y, offset, size):
        self._init_index()
        idx_offset = self._tile_offset(x, y)
        offset = struct.pack('<Q', offset)[:5]
        with open(self.filename, 'r+b') as f:
            f.seek(idx_offset, os.SEEK_SET)
            f.write(offset)

    def remove_tile_offset(self, x, y):
        self._init_index()
        idx_offset = self._tile_offset(x, y)
        with open(self.filename, 'r+b') as f:
            f.seek(idx_offset)
            f.write(b'\x00' * 5)

# The bundle file has a header with 15 little-endian long values (60 bytes).
# NOTE: the fixed values might be some flags for image options (format, aliasing)
# all files available for testing had the same values however.
BUNDLE_V1_HEADER_SIZE = 60
BUNDLE_V1_HEADER = [
    3        , # 0,  fixed
    16384    , # 1,  max. num of tiles 128*128 = 16384
    16       , # 2,  size of largest tile
    5        , # 3,  fixed
    0        , # 4,  num of tiles in bundle (*4)
    60+65536 , # 5,  bundle size
    40       , # 6   fixed
    16       , # 7,  fixed
    0        , # 8,  y0
    127      , # 9,  y1
    0        , # 10, x0
    127      , # 11, x1
]
BUNDLE_V1_HEADER_STRUCT_FORMAT = '<4I3Q5I'

class BundleDataV1(object):
    def __init__(self, filename, tile_offsets):
        self.filename = filename
        self.tile_offsets = tile_offsets
        if not os.path.exists(self.filename):
            self._init_bundle()

    def _init_bundle(self):
        ensure_directory(self.filename)
        header = list(BUNDLE_V1_HEADER)
        header[10], header[8] = self.tile_offsets
        header[11], header[9] = header[10]+127, header[8]+127
        write_atomic(self.filename,
            struct.pack(BUNDLE_V1_HEADER_STRUCT_FORMAT, *header) +
            # zero-size entry for each tile
            (b'\x00' * (BUNDLEX_V1_GRID_HEIGHT * BUNDLEX_V1_GRID_WIDTH * 4)))

    def read_size(self, offset):
        with open(self.filename, 'rb') as f:
            f.seek(offset)
            return struct.unpack('<L', f.read(4))[0]

    def read_tile(self, offset):
        with open(self.filename, 'rb') as f:
            f.seek(offset)
            size = struct.unpack('<L', f.read(4))[0]
            if size <= 0:
                return False
            return f.read(size)

    def append_tile(self, data, prev_offset):
        size = len(data)
        is_new_tile = True
        with open(self.filename, 'r+b') as f:
            if prev_offset:
                f.seek(prev_offset, os.SEEK_SET)
                if f.tell() == prev_offset:
                    if struct.unpack('<L', f.read(4))[0] > 0:
                        is_new_tile = False

            f.seek(0, os.SEEK_END)
            offset = f.tell()
            if offset == 0:
                f.write(b'\x00' * 16) # header
                offset = 16
            f.write(struct.pack('<L', size))
            f.write(data)

            # update header
            f.seek(0, os.SEEK_SET)
            header = list(struct.unpack(BUNDLE_V1_HEADER_STRUCT_FORMAT, f.read(60)))
            header[2] = max(header[2], size)
            header[5] += size + 4
            if is_new_tile:
                header[4] += 4
            f.seek(0, os.SEEK_SET)
            f.write(struct.pack(BUNDLE_V1_HEADER_STRUCT_FORMAT, *header))

        return offset, size


BUNDLE_V2_GRID_WIDTH = 128
BUNDLE_V2_GRID_HEIGHT = 128
BUNDLE_V2_TILES = BUNDLE_V2_GRID_WIDTH * BUNDLE_V2_GRID_HEIGHT
BUNDLE_V2_INDEX_SIZE = BUNDLE_V2_TILES * 8

BUNDLE_V2_HEADER = (
    3,                          # Version
    BUNDLE_V2_TILES,            # numRecords
    0,                          # maxRecord Size
    5,                          # Offset Size
    0,                          # Slack Space
    64 + BUNDLE_V2_INDEX_SIZE,  # File Size
    40,                         # User Header Offset
    20 + BUNDLE_V2_INDEX_SIZE,  # User Header Size
    3,                          # Legacy 1
    16,                         # Legacy 2 0?
    BUNDLE_V2_TILES,            # Legacy 3
    5,                          # Legacy 4
    BUNDLE_V2_INDEX_SIZE        # Index Size
)
BUNDLE_V2_HEADER_STRUCT_FORMAT = '<4I3Q6I'
BUNDLE_V2_HEADER_SIZE = 64


class BundleV2(object):
    def __init__(self, base_filename, offset=None):
        # offset not used by V2
        self.filename = base_filename + '.bundle'
        self.lock_filename = base_filename + '.lck'

        # defer initialization to update/remove calls to avoid
        # index creation on is_cached (prevents new files in read-only caches)
        self._initialized = False

    def _init_index(self):
        self._initialized = True
        if os.path.exists(self.filename):
            return
        ensure_directory(self.filename)
        buf = BytesIO()
        buf.write(struct.pack(BUNDLE_V2_HEADER_STRUCT_FORMAT, *BUNDLE_V2_HEADER))
        # Empty index (ArcGIS stores an offset of 4 and size of 0 for missing tiles)
        buf.write(struct.pack('<%dQ' % BUNDLE_V2_TILES, *(4, ) * BUNDLE_V2_TILES))
        write_atomic(self.filename, buf.getvalue())

    def _tile_idx_offset(self, x, y):
        return BUNDLE_V2_HEADER_SIZE + (x + BUNDLE_V2_GRID_HEIGHT * y) * 8

    def _rel_tile_coord(self, tile_coord):
        return (tile_coord[0] % BUNDLE_V2_GRID_WIDTH,
                tile_coord[1] % BUNDLE_V2_GRID_HEIGHT, )

    def _tile_offset_size(self, fh, x, y):
        idx_offset = self._tile_idx_offset(x, y)
        fh.seek(idx_offset)
        val = struct.unpack('<Q', fh.read(8))[0]
        # Index contains 8 bytes per tile.
        # Size is stored in 24 most significant bits.
        # Offset in the least significant 40 bits.
        size = val >> 40
        if size == 0:
            return 0, 0
        offset = val - (size << 40)
        return offset, size

    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True

        try:
            with open(self.filename, 'rb') as f:
                x, y = self._rel_tile_coord(tile.coord)
                offset, size = self._tile_offset_size(f, x, y)
                if not size:
                    return False

                f.seek(offset)
                data = f.read(size)
        except IOError as ex:
            if ex.errno == errno.ENOENT:
                # missing bundle file -> missing tile
                return False
            raise

        tile.source = ImageSource(BytesIO(data))
        return True

    def is_cached(self, tile):
        try:
            with open(self.filename, 'rb') as f:
                x, y = self._rel_tile_coord(tile.coord)
                _, size = self._tile_offset_size(f, x, y)
                if not size:
                    return False
                return True
        except IOError as ex:
            if ex.errno == errno.ENOENT:
                # missing bundle file -> missing tile
                return False
            raise

    def _update_tile_offset(self, fh, x, y, offset, size):
        idx_offset = self._tile_idx_offset(x, y)
        val = offset + (size << 40)

        fh.seek(idx_offset, os.SEEK_SET)
        fh.write(struct.pack('<Q', val))

    def _append_tile(self, fh, data):
        # Write tile size first, then tile data.
        # Offset points to actual tile data.
        fh.seek(0, os.SEEK_END)
        fh.write(struct.pack('<L', len(data)))
        offset = fh.tell()
        fh.write(data)
        return offset

    def _update_metadata(self, fh, filesize, tilesize):
        # Max record/tile size
        fh.seek(8)
        old_tilesize = struct.unpack('<I', fh.read(4))[0]
        if tilesize > old_tilesize:
            fh.seek(8)
            fh.write(struct.pack('<I', tilesize))

        # Complete file size
        fh.seek(24)
        fh.write(struct.pack("<Q", filesize))

    def store_tile(self, tile):
        if tile.stored:
            return True

        self._init_index()
        with tile_buffer(tile) as buf:
            data = buf.read()
        size = len(data)
        x, y = self._rel_tile_coord(tile.coord)

        with FileLock(self.lock_filename):
            with open(self.filename, 'r+b') as f:
                offset = self._append_tile(f, data)
                self._update_tile_offset(f, x, y, offset, size)

                filesize = offset + size
                self._update_metadata(f, filesize, size)

        return True

    def remove_tile(self, tile):
        if tile.coord is None:
            return True

        self._init_index()
        with FileLock(self.lock_filename):
            with open(self.filename, 'r+b') as f:
                x, y = self._rel_tile_coord(tile.coord)
                self._update_tile_offset(f, x, y, 0, 0)

        return True


class CompactCacheV1(CompactCacheBase):
    bundle_class = BundleV1

class CompactCacheV2(CompactCacheBase):
    bundle_class = BundleV2

