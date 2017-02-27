# This file is part of the MapProxy project.
# Copyright (C) 2017 Omniscale <http://omniscale.de>
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

try:
    import redis
except ImportError:
    redis = None

import time
import os

from nose.plugins.skip import SkipTest

from mapproxy.cache.tile import Tile
from mapproxy.cache.redis import RedisCache

from mapproxy.test.unit.test_cache_tile import TileCacheTestBase

class TestRedisCache(TileCacheTestBase):
    always_loads_metadata = False
    def setup(self):
        if not redis:
            raise SkipTest("redis required for Redis tests")

        redis_host = os.environ.get('MAPPROXY_TEST_REDIS')
        if not redis_host:
            raise SkipTest()
        self.host, self.port = redis_host.split(':')

        TileCacheTestBase.setup(self)

        self.cache = RedisCache(self.host, int(self.port), prefix='mapproxy-test', db=1)

    def teardown(self):
        for k in self.cache.r.keys('mapproxy-test-*'):
            self.cache.r.delete(k)

    def test_expire(self):
        cache = RedisCache(self.host, int(self.port), prefix='mapproxy-test', db=1, ttl=0)
        t1 = self.create_tile(coord=(9382, 1234, 9))
        assert cache.store_tile(t1)
        time.sleep(0.1)
        t2 = Tile(t1.coord)
        assert cache.is_cached(t2)

        cache = RedisCache(self.host, int(self.port), prefix='mapproxy-test', db=1, ttl=0.05)
        t1 = self.create_tile(coord=(5382, 2234, 9))
        assert cache.store_tile(t1)
        time.sleep(0.1)
        t2 = Tile(t1.coord)
        assert not cache.is_cached(t2)

    def test_double_remove(self):
        tile = self.create_tile()
        self.create_cached_tile(tile)
        assert self.cache.remove_tile(tile)
        assert self.cache.remove_tile(tile)
