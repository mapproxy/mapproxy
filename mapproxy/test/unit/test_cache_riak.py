# This file is part of the MapProxy project.
# Copyright (C) 2013 Omniscale <http://omniscale.de>
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

import os
import random

from nose.plugins.skip import SkipTest

from mapproxy.cache.riakcache import RiakCache
from mapproxy.cache.tile import Tile
from mapproxy.grid import tile_grid
from mapproxy.test.image import create_tmp_image_buf
from mapproxy.image import ImageSource
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase

tile_image = create_tmp_image_buf((256, 256), color='blue')
tile_image2 = create_tmp_image_buf((256, 256), color='red')

class RiakCacheTestBase(TileCacheTestBase):
    always_loads_metadata = True
    def setup(self):
        if not os.environ.get(self.riak_url_env):
            raise SkipTest()
        
        riak_url = os.environ[self.riak_url_env]
        db_name = 'mapproxy_test_%d' % random.randint(0, 100000)
        
        TileCacheTestBase.setup(self)
        
        self.cache = RiakCache(riak_url, db_name, 'riak', tile_grid=tile_grid(3857, name='global-webmarcator'))

    def teardown(self):
        import riak
        bucket = self.cache.bucket
        for k in bucket.get_keys():
            riak.RiakObject(self.cache.connection, bucket, k).delete()
        TileCacheTestBase.teardown(self)
    
    def test_double_remove(self):
        tile = self.create_tile()
        self.create_cached_tile(tile)
        assert self.cache.remove_tile(tile)
        assert self.cache.remove_tile(tile)

class TestRiakCacheHTTP(RiakCacheTestBase):
    riak_url_env = 'MAPPROXY_TEST_RIAK_HTTP'

class TestRiakCachePBC(RiakCacheTestBase):
    riak_url_env = 'MAPPROXY_TEST_RIAK_PBC'