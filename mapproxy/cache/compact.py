# This file is part of the MapProxy project.
# Copyright (C) 2016 Omniscale <http://omniscale.de>
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

from __future__ import with_statement
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


class CompactCacheV1(TileCacheBase):
    supports_timestamp = False

    def __init__(self, cache_dir):
        self.lock_cache_id = 'compactcache-' + hashlib.md5(cache_dir.encode('utf-8')).hexdigest()
        self.cache_dir = cache_dir

    def _get_bundle(self, tile_coord):
        x, y, z = tile_coord

        level_dir = os.path.join(self.cache_dir, 'L%02d' % z)

        c = x // BUNDLEX_GRID_WIDTH * BUNDLEX_GRID_WIDTH
        r = y // BUNDLEX_GRID_HEIGHT * BUNDLEX_GRID_HEIGHT

        basename = 'R%04xC%04x' % (r, c)
        return Bundle(os.path.join(level_dir, basename))

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
        self.load_tile(tile)

    def remove_level_tiles_before(self, level, timestamp):
        if timestamp == 0:
            level_dir = os.path.join(self.cache_dir, 'L%02d' % level)
            shutil.rmtree(level_dir, ignore_errors=True)
            return True
        return False

BUNDLE_EXT = '.bundle'
BUNDLEX_EXT = '.bundlx'

class Bundle(object):
    def __init__(self, base_filename):
        self.base_filename = base_filename
        self.lock_filename = base_filename + '.lck'

    def _rel_tile_coord(self, tile_coord):
        return (
            tile_coord[0] % BUNDLEX_GRID_WIDTH,
            tile_coord[1] % BUNDLEX_GRID_HEIGHT,
        )

    def is_cached(self, tile):
        if tile.source or tile.coord is None:
            return True

        idx = BundleIndex(self.base_filename + BUNDLEX_EXT)
        x, y = self._rel_tile_coord(tile.coord)
        offset = idx.tile_offset(x, y)
        if offset == 0:
            return False

        bundle = BundleData(self.base_filename + BUNDLE_EXT)
        size = bundle.read_size(offset)
        return size != 0

    def store_tile(self, tile):
        if tile.stored:
            return True

        with tile_buffer(tile) as buf:
            data = buf.read()

        with FileLock(self.lock_filename):
            bundle = BundleData(self.base_filename + BUNDLE_EXT)
            offset, size = bundle.append_tile(data)

            idx = BundleIndex(self.base_filename + BUNDLEX_EXT)
            x, y = self._rel_tile_coord(tile.coord)
            idx.update_tile_offset(x, y, offset=offset, size=size)

        return True

    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True

        idx = BundleIndex(self.base_filename + BUNDLEX_EXT)
        x, y = self._rel_tile_coord(tile.coord)
        offset = idx.tile_offset(x, y)
        if offset == 0:
            return False

        bundle = BundleData(self.base_filename + BUNDLE_EXT)
        data = bundle.read_tile(offset)
        if not data:
            return False
        tile.source = ImageSource(BytesIO(data))

        return True

    def remove_tile(self, tile):
        if tile.coord is None:
            return True

        with FileLock(self.lock_filename):
            idx = BundleIndex(self.base_filename + BUNDLEX_EXT)
            x, y = self._rel_tile_coord(tile.coord)
            idx.remove_tile_offset(x, y)

        return True


BUNDLEX_GRID_WIDTH = 128
BUNDLEX_GRID_HEIGHT = 128
BUNDLEX_HEADER_SIZE = 16
BUNDLEX_HEADER = b'\x03\x00\x00\x00\x10\x00\x00\x00\x00\x40\x00\x00\x05\x00\x00\x00'
BUNDLEX_FOOTER_SIZE = 16
BUNDLEX_FOOTER = b'\x00\x00\x00\x00\x10\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00'

class BundleIndex(object):
    def __init__(self, filename):
        self.filename = filename
        if not os.path.exists(self.filename):
            self._init_index()

    def _init_index(self):
        ensure_directory(self.filename)
        buf = BytesIO()
        buf.write(BUNDLEX_HEADER)
        for i in range(BUNDLEX_GRID_WIDTH * BUNDLEX_GRID_HEIGHT):
            buf.write(struct.pack('<Q', (i*4)+BUNDLE_HEADER_SIZE)[:5])
        buf.write(BUNDLEX_FOOTER)
        write_atomic(self.filename, buf.getvalue())

    def _tile_offset(self, x, y):
        return BUNDLEX_HEADER_SIZE + (x * BUNDLEX_GRID_HEIGHT + y) * 5

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
        idx_offset = self._tile_offset(x, y)
        offset = struct.pack('<Q', offset)[:5]
        with open(self.filename, 'r+b') as f:
            f.seek(idx_offset, os.SEEK_SET)
            f.write(offset)

    def remove_tile_offset(self, x, y):
        idx_offset = self._tile_offset(x, y)
        with open(self.filename, 'r+b') as f:
            f.seek(idx_offset)
            f.write(b'\x00' * 5)

BUNDLE_HEADER_SIZE = 60
BUNDLE_HEADER = (
    b'\x03\x00\x00\x00\x00\x40\x00\x00\x9c\x7a\x00\x00\x05\x00\x00\x00' +
    b'\x10\x00\x00\x00\x00\x00\x00\x00\xd5\xd2\x02\x00\x00\x00\x00\x00' +
    b'\x28\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00' +
    b'\x7f\x00\x00\x00\x00\x00\x00\x00\x7f\x00\x00\x00'
)

class BundleData(object):
    def __init__(self, filename):
        self.filename = filename
        if not os.path.exists(self.filename):
            self._init_bundle()

    def _init_bundle(self):
        ensure_directory(self.filename)
        write_atomic(self.filename,
            BUNDLE_HEADER + (b'\x00' * BUNDLEX_GRID_HEIGHT * BUNDLEX_GRID_WIDTH * 4))

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

    def append_tile(self, data):
        size = len(data)
        with open(self.filename, 'r+b') as f:
            f.seek(0, os.SEEK_END)
            offset = f.tell()
            if offset == 0:
                f.write(b'\x00' * 16) # header
                offset = 16
            f.write(struct.pack('<L', size))
            f.write(data)
        return offset, size

