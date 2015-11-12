# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

import re
import os
import time
import random

from nose.plugins.skip import SkipTest

from mapproxy.cache.mongodb import MongoDBCache 
from mapproxy.cache.tile import Tile
from mapproxy.grid import tile_grid
from mapproxy.test.image import create_tmp_image_buf

from mapproxy.test.unit.test_cache_tile import TileCacheTestBase

from nose.tools import assert_almost_equal, eq_

tile_image = create_tmp_image_buf((256, 256), color='blue')
tile_image2 = create_tmp_image_buf((256, 256), color='red')

class TestMongoDBCache(TileCacheTestBase):
    always_loads_metadata = True
    def setup(self):
        if not os.environ.get('MAPPROXY_TEST_MONGODB'):
            raise SkipTest()

        mongo_address = os.environ['MAPPROXY_TEST_MONGODB']
        layer_name = 'mapproxy_test_%d' % random.randint(0, 100000)

        TileCacheTestBase.setup(self)
        self.cache = MongoDBCache(mongo_address, layer_name, 'EPSG:3857')

    def teardown(self):
        TileCacheTestBase.teardown(self)

    def test_store_bulk_with_overwrite(self):
        tile = self.create_tile((0, 0, 4))
        self.create_cached_tile(tile)

        assert self.cache.is_cached(Tile((0, 0, 4)))
        loaded_tile = Tile((0, 0, 4))
        assert self.cache.load_tile(loaded_tile)
        assert loaded_tile.source_buffer().read() == tile.source_buffer().read()

        assert not self.cache.is_cached(Tile((1, 0, 4)))

        tiles = [self.create_another_tile((x, 0, 4)) for x in range(2)]
        assert self.cache.store_tiles(tiles)

        assert self.cache.is_cached(Tile((0, 0, 4)))
        loaded_tile = Tile((0, 0, 4))
        assert self.cache.load_tile(loaded_tile)
        # check that tile is overwritten
        assert loaded_tile.source_buffer().read() != tile.source_buffer().read()
        assert loaded_tile.source_buffer().read() == tiles[0].source_buffer().read()

    def test_double_remove(self):
        tile = self.create_tile()
        self.create_cached_tile(tile)
        assert self.cache.remove_tile(tile)
        assert self.cache.remove_tile(tile)
