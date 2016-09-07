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

from mapproxy.cache.compact import CompactCacheV1
from mapproxy.cache.tile import Tile
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase

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

    def test_missing_tiles(self):
        self.cache.store_tile(self.create_tile(coord=(0, 0, 0)))
        assert os.path.exists(os.path.join(self.cache_dir, 'L00', 'R0000C0000.bundle'))
        assert os.path.exists(os.path.join(self.cache_dir, 'L00', 'R0000C0000.bundlx'))

        # test that all other tiles in this bundle are missing
        assert self.cache.is_cached(Tile((0, 0, 0)))
        for x in range(128):
            for y in range(128):
                if x == 0 and y == 0:
                    continue
                assert not self.cache.is_cached(Tile((x, y, 0)))
                assert not self.cache.load_tile(Tile((x, y, 0)))

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
