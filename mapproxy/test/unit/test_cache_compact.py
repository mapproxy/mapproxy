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

from __future__ import with_statement, division

import os
import time
import struct

from io import BytesIO

from mapproxy.cache.compact import CompactCacheV1
from mapproxy.cache.tile import Tile
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase

from nose.tools import eq_

class TestCompactCacheV1(TileCacheTestBase):

    always_loads_metadata = True

    def setup(self):
        TileCacheTestBase.setup(self)
        self.cache = CompactCacheV1(
            cache_dir=self.cache_dir,
        )

    def test_bundle_files(self):
        assert not os.path.exists(os.path.join(self.cache_dir, 'L00', 'R0000C0000.bundle'))
        assert not os.path.exists(os.path.join(self.cache_dir, 'L00', 'R0000C0000.bundlx'))
        self.cache.store_tile(self.create_tile(coord=(0, 0, 0)))
        assert os.path.exists(os.path.join(self.cache_dir, 'L00', 'R0000C0000.bundle'))
        assert os.path.exists(os.path.join(self.cache_dir, 'L00', 'R0000C0000.bundlx'))

        assert not os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0000C0000.bundle'))
        assert not os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0000C0000.bundlx'))
        self.cache.store_tile(self.create_tile(coord=(127, 127, 12)))
        assert os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0000C0000.bundle'))
        assert os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0000C0000.bundlx'))

        assert not os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0100C0080.bundle'))
        assert not os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0100C0080.bundlx'))
        self.cache.store_tile(self.create_tile(coord=(128, 256, 12)))
        assert os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0100C0080.bundle'))
        assert os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0100C0080.bundlx'))

    def test_bundle_files_not_created_on_is_cached(self):
        assert not os.path.exists(os.path.join(self.cache_dir, 'L00', 'R0000C0000.bundle'))
        assert not os.path.exists(os.path.join(self.cache_dir, 'L00', 'R0000C0000.bundlx'))
        self.cache.is_cached(Tile(coord=(0, 0, 0)))
        assert not os.path.exists(os.path.join(self.cache_dir, 'L00', 'R0000C0000.bundle'))
        assert not os.path.exists(os.path.join(self.cache_dir, 'L00', 'R0000C0000.bundlx'))

    def test_missing_tiles(self):
        self.cache.store_tile(self.create_tile(coord=(130, 200, 8)))
        assert os.path.exists(os.path.join(self.cache_dir, 'L08', 'R0080C0080.bundle'))
        assert os.path.exists(os.path.join(self.cache_dir, 'L08', 'R0080C0080.bundlx'))

        # test that all other tiles in this bundle are missing
        assert self.cache.is_cached(Tile((130, 200, 8)))
        for x in range(128, 255):
            for y in range(128, 255):
                if x == 130 and y == 200:
                    continue
                assert not self.cache.is_cached(Tile((x, y, 8))), (x, y)
                assert not self.cache.load_tile(Tile((x, y, 8))), (x, y)

    def test_remove_level_tiles_before(self):
        self.cache.store_tile(self.create_tile(coord=(0, 0, 12)))
        assert os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0000C0000.bundle'))
        assert os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0000C0000.bundlx'))

        # not removed with timestamp
        self.cache.remove_level_tiles_before(12, time.time())
        assert os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0000C0000.bundle'))
        assert os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0000C0000.bundlx'))

        # removed with timestamp=0 (remove_all:true in seed.yaml)
        self.cache.remove_level_tiles_before(12, 0)
        assert not os.path.exists(os.path.join(self.cache_dir, 'L12'))


    def test_bundle_header(self):
        t = Tile((5000, 1000, 12), ImageSource(BytesIO(b'a' * 4000), image_opts=ImageOptions(format='image/png')))
        self.cache.store_tile(t)
        assert os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0380C1380.bundle'))
        assert os.path.exists(os.path.join(self.cache_dir, 'L12', 'R0380C1380.bundlx'))

        def assert_header(tile_bytes_written, max_tile_bytes):
            with open(os.path.join(self.cache_dir, 'L12', 'R0380C1380.bundle'), 'r+b') as f:
                header = struct.unpack('<lllllllllllllll', f.read(60))
                eq_(header[11], 896)
                eq_(header[12], 1023)
                eq_(header[13], 4992)
                eq_(header[14], 5119)
                eq_(header[6], 60 + 128*128*4 + sum(tile_bytes_written))
                eq_(header[2], max_tile_bytes)
                eq_(header[4], len(tile_bytes_written)*4)

        assert_header([4000 + 4], 4000)

        t = Tile((5000, 1001, 12), ImageSource(BytesIO(b'a' * 6000), image_opts=ImageOptions(format='image/png')))
        self.cache.store_tile(t)
        assert_header([4000 + 4, 6000 + 4], 6000)

        t = Tile((4992, 999, 12), ImageSource(BytesIO(b'a' * 1000), image_opts=ImageOptions(format='image/png')))
        self.cache.store_tile(t)
        assert_header([4000 + 4, 6000 + 4, 1000 + 4], 6000)

        t = Tile((5000, 1001, 12), ImageSource(BytesIO(b'a' * 3000), image_opts=ImageOptions(format='image/png')))
        self.cache.store_tile(t)
        assert_header([4000 + 4, 6000 + 4 + 3000 + 4, 1000 + 4], 6000) # still contains bytes from overwritten tile

