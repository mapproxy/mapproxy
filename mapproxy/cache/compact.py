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

import contextlib
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

    def _get_bundle_fname_and_offset(self, tile_coord):
        x, y, z = tile_coord

        level_dir = os.path.join(self.cache_dir, 'L%02d' % z)

        c = x // BUNDLEX_V1_GRID_WIDTH * BUNDLEX_V1_GRID_WIDTH
        r = y // BUNDLEX_V1_GRID_HEIGHT * BUNDLEX_V1_GRID_HEIGHT

        basename = 'R%04xC%04x' % (r, c)
        return os.path.join(level_dir, basename), (c, r)

    def _get_bundle(self, tile_coord):
        bundle_fname, offset = self._get_bundle_fname_and_offset(tile_coord)
        return self.bundle_class(bundle_fname, offset=offset)

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

    def store_tiles(self, tiles):
        if len(tiles) > 1:
            # Check if all tiles are from a single bundle.
            bundle_files = set()
            tile_coord = None
            for t in tiles:
                if t.stored:
                    continue
                bundle_files.add(self._get_bundle_fname_and_offset(t.coord)[0])
                tile_coord = t.coord
            if len(bundle_files) == 1:
                return self._get_bundle(tile_coord).store_tiles(tiles)

        # Tiles are across multiple bundles
        failed = False
        for tile in tiles:
            if not self.store_tile(tile):
                failed = True
        return not failed


    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True

        return self._get_bundle(tile.coord).load_tile(tile)

    def load_tiles(self, tiles, with_metadata=False):
        if len(tiles) > 1:
            # Check if all tiles are from a single bundle.
            bundle_files = set()
            tile_coord = None
            for t in tiles:
                if t.source or t.coord is None:
                    continue
                bundle_files.add(self._get_bundle_fname_and_offset(t.coord)[0])
                tile_coord = t.coord
            if len(bundle_files) == 1:
                return self._get_bundle(tile_coord).load_tiles(tiles)

        # No support_bulk_load or tiles are across multiple bundles
        missing = False
        for tile in tiles:
            if not self.load_tile(tile, with_metadata=with_metadata):
                missing = True
        return not missing

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

    def data(self):
        return BundleDataV1(self.base_filename + BUNDLE_EXT, self.offset)

    def index(self):
        return BundleIndexV1(self.base_filename + BUNDLEX_V1_EXT)

    def is_cached(self, tile):
        if tile.source or tile.coord is None:
            return True

        with self.index().readonly() as idx:
            if not idx:
                return False
            x, y = self._rel_tile_coord(tile.coord)
            offset = idx.tile_offset(x, y)
            if offset == 0:
                return False

        with self.data().readonly() as bundle:
            size = bundle.read_size(offset)
        return size != 0

    def store_tile(self, tile):
        if tile.stored:
            return True
        return self.store_tiles([tile])

    def store_tiles(self, tiles):
        tiles_data = []
        for t in tiles:
            if t.stored:
                continue
            with tile_buffer(t) as buf:
                data = buf.read()
            tiles_data.append((t.coord, data))

        with FileLock(self.lock_filename):
            with self.data().readwrite() as bundle:
                with self.index().readwrite() as idx:
                    for tile_coord, data in tiles_data:
                        x, y = self._rel_tile_coord(tile_coord)
                        offset = idx.tile_offset(x, y)
                        offset, size = bundle.append_tile(data, prev_offset=offset)
                        idx.update_tile_offset(x, y, offset=offset, size=size)

        return True


    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True
        return self.load_tiles([tile], with_metadata)

    def load_tiles(self, tiles, with_metadata=False):
        missing = False

        with self.index().readonly() as idx:
            if not idx:
                return False
            with self.data().readonly() as bundle:
                for t in tiles:
                    if t.source or t.coord is None:
                        continue
                    x, y = self._rel_tile_coord(t.coord)
                    offset = idx.tile_offset(x, y)
                    if offset == 0:
                        missing = True
                        continue

                    data = bundle.read_tile(offset)
                    if not data:
                        missing = True
                        continue
                    t.source = ImageSource(BytesIO(data))

        return not missing

    def remove_tile(self, tile):
        if tile.coord is None:
            return True

        with FileLock(self.lock_filename):
            with self.index().readwrite() as idx:
                x, y = self._rel_tile_coord(tile.coord)
                idx.remove_tile_offset(x, y)

        return True

    def size(self):
        total_size = 0

        with self.index().readonly() as idx:
            if not idx:
                return 0, 0

            with self.data().readonly() as bundle:
                for y in range(BUNDLEX_V1_GRID_HEIGHT):
                    for x in range(BUNDLEX_V1_GRID_WIDTH):
                        offset = idx.tile_offset(x, y)
                        if not offset:
                            continue
                        size = bundle.read_size(offset)
                        if not size:
                            continue
                        total_size += size + 4

        actual_size = os.path.getsize(bundle.filename)
        return total_size + BUNDLE_V1_HEADER_SIZE + (BUNDLEX_V1_GRID_HEIGHT * BUNDLEX_V1_GRID_WIDTH * 4), actual_size


BUNDLEX_V1_GRID_WIDTH = 128
BUNDLEX_V1_GRID_HEIGHT = 128
BUNDLEX_V1_HEADER_SIZE = 16
BUNDLEX_V1_HEADER = b'\x03\x00\x00\x00\x10\x00\x00\x00\x00\x40\x00\x00\x05\x00\x00\x00'
BUNDLEX_V1_FOOTER_SIZE = 16
BUNDLEX_V1_FOOTER = b'\x00\x00\x00\x00\x10\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00'

INT64LE = struct.Struct('<Q')

class BundleIndexV1(object):
    def __init__(self, filename):
        self.filename = filename
        self._fh = None
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
            buf.write(INT64LE.pack((i*4)+BUNDLE_V1_HEADER_SIZE)[:5])
        buf.write(BUNDLEX_V1_FOOTER)
        write_atomic(self.filename, buf.getvalue())

    def _tile_index_offset(self, x, y):
        return BUNDLEX_V1_HEADER_SIZE + (x * BUNDLEX_V1_GRID_HEIGHT + y) * 5

    def tile_offset(self, x, y):
        if self._fh is None:
            raise RuntimeError('not called within readonly/readwrite context')
        idx_offset = self._tile_index_offset(x, y)
        self._fh.seek(idx_offset)
        offset = INT64LE.unpack(self._fh.read(5) + b'\x00\x00\x00')[0]
        return offset

    def update_tile_offset(self, x, y, offset, size):
        if self._fh is None:
            raise RuntimeError('not called within readwrite context')
        idx_offset = self._tile_index_offset(x, y)
        offset = INT64LE.pack(offset)[:5]
        self._fh.seek(idx_offset, os.SEEK_SET)
        self._fh.write(offset)

    def remove_tile_offset(self, x, y):
        if self._fh is None:
            raise RuntimeError('not called within readwrite context')
        idx_offset = self._tile_index_offset(x, y)
        self._fh.seek(idx_offset)
        self._fh.write(b'\x00' * 5)

    @contextlib.contextmanager
    def readonly(self):
        try:
            with open(self.filename, 'rb') as fh:
                b = BundleIndexV1(self.filename)
                b._fh = fh
                yield b
        except IOError as ex:
            if ex.errno == errno.ENOENT:
                # missing bundle file -> missing tile
                yield None
            else:
                raise ex

    @contextlib.contextmanager
    def readwrite(self):
        self._init_index()
        with open(self.filename, 'r+b') as fh:
            b = BundleIndexV1(self.filename)
            b._fh = fh
            yield b



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
        self._fh = None
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


    @contextlib.contextmanager
    def readonly(self):
        with open(self.filename, 'rb') as fh:
            b = BundleDataV1(self.filename, self.tile_offsets)
            b._fh = fh
            yield b

    @contextlib.contextmanager
    def readwrite(self):
        with open(self.filename, 'r+b') as fh:
            b = BundleDataV1(self.filename, self.tile_offsets)
            b._fh = fh
            yield b

    def read_size(self, offset):
        if self._fh is None:
            raise RuntimeError('not called within readonly/readwrite context')
        self._fh.seek(offset)
        return struct.unpack('<L', self._fh.read(4))[0]

    def read_tile(self, offset):
        if self._fh is None:
            raise RuntimeError('not called within readonly/readwrite context')
        self._fh.seek(offset)
        size = struct.unpack('<L', self._fh.read(4))[0]
        if size <= 0:
            return False
        return self._fh.read(size)

    def append_tile(self, data, prev_offset):
        if self._fh is None:
            raise RuntimeError('not called within readwrite context')
        size = len(data)
        is_new_tile = True
        if prev_offset:
            self._fh.seek(prev_offset, os.SEEK_SET)
            if self._fh.tell() == prev_offset:
                if struct.unpack('<L', self._fh.read(4))[0] > 0:
                    is_new_tile = False

        self._fh.seek(0, os.SEEK_END)
        offset = self._fh.tell()
        if offset == 0:
            self._fh.write(b'\x00' * 16) # header
            offset = 16
        self._fh.write(struct.pack('<L', size))
        self._fh.write(data)

        # update header
        self._fh.seek(0, os.SEEK_SET)
        header = list(struct.unpack(BUNDLE_V1_HEADER_STRUCT_FORMAT, self._fh.read(60)))
        header[2] = max(header[2], size)
        header[5] += size + 4
        if is_new_tile:
            header[4] += 4
        self._fh.seek(0, os.SEEK_SET)
        self._fh.write(struct.pack(BUNDLE_V1_HEADER_STRUCT_FORMAT, *header))

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
        val = INT64LE.unpack(fh.read(8))[0]
        # Index contains 8 bytes per tile.
        # Size is stored in 24 most significant bits.
        # Offset in the least significant 40 bits.
        size = val >> 40
        if size == 0:
            return 0, 0
        offset = val - (size << 40)
        return offset, size

    def _load_tile(self, fh, tile):
        if tile.source or tile.coord is None:
            return True

        x, y = self._rel_tile_coord(tile.coord)
        offset, size = self._tile_offset_size(fh, x, y)
        if not size:
            return False

        fh.seek(offset)
        data = fh.read(size)

        tile.source = ImageSource(BytesIO(data))
        return True

    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True

        return self.load_tiles([tile], with_metadata)

    def load_tiles(self, tiles, with_metadata=False):
        missing = False

        with self._readonly() as fh:
            if not fh:
                return False

            for t in tiles:
                if t.source or t.coord is None:
                    continue
                if not self._load_tile(fh, t):
                    missing = True

        return not missing

    def is_cached(self, tile):
        with self._readonly() as fh:
            if not fh:
                return False

            x, y = self._rel_tile_coord(tile.coord)
            _, size = self._tile_offset_size(fh, x, y)
            if not size:
                return False
            return True

    def _update_tile_offset(self, fh, x, y, offset, size):
        idx_offset = self._tile_idx_offset(x, y)
        val = offset + (size << 40)

        fh.seek(idx_offset, os.SEEK_SET)
        fh.write(INT64LE.pack(val))

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

    def _store_tile(self, fh, tile_coord, data):
        size = len(data)
        x, y = self._rel_tile_coord(tile_coord)
        offset = self._append_tile(fh, data)
        self._update_tile_offset(fh, x, y, offset, size)

        filesize = offset + size
        self._update_metadata(fh, filesize, size)

    def store_tile(self, tile):
        if tile.stored:
            return True

        return self.store_tiles([tile])

    def store_tiles(self, tiles):
        self._init_index()

        tiles_data = []
        for t in tiles:
            if t.stored:
                continue
            with tile_buffer(t) as buf:
                data = buf.read()
            tiles_data.append((t.coord, data))

        with FileLock(self.lock_filename):
            with self._readwrite() as fh:
                for tile_coord, data in tiles_data:
                    self._store_tile(fh, tile_coord, data)

        return True


    def remove_tile(self, tile):
        if tile.coord is None:
            return True

        self._init_index()
        with FileLock(self.lock_filename):
            with self._readwrite() as fh:
                x, y = self._rel_tile_coord(tile.coord)
                self._update_tile_offset(fh, x, y, 0, 0)

        return True

    def size(self):
        total_size = 0
        with self._readonly() as fh:
            if not fh:
                return 0, 0
            for y in range(BUNDLE_V2_GRID_HEIGHT):
                for x in range(BUNDLE_V2_GRID_WIDTH):
                    _, size = self._tile_offset_size(fh, x, y)
                    if size:
                        total_size += size + 4
            fh.seek(0, os.SEEK_END)
            actual_size = fh.tell()
            return total_size + 64 + BUNDLE_V2_INDEX_SIZE, actual_size

    @contextlib.contextmanager
    def _readonly(self):
        try:
            with open(self.filename, 'rb') as fh:
                yield fh
        except IOError as ex:
            if ex.errno == errno.ENOENT:
                # missing bundle file -> missing tile
                yield None
            else:
                raise ex

    @contextlib.contextmanager
    def _readwrite(self):
        self._init_index()
        with open(self.filename, 'r+b') as fh:
            yield fh



class CompactCacheV1(CompactCacheBase):
    bundle_class = BundleV1

class CompactCacheV2(CompactCacheBase):
    bundle_class = BundleV2

