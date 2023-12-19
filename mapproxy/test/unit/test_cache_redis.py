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

import os
import time

import pytest

try:
    import redis
except ImportError:
    redis = None

from mapproxy.cache.redis import RedisCache
from mapproxy.cache.tile import Tile
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase


@pytest.mark.skipif(not redis or not os.environ.get('MAPPROXY_TEST_REDIS'),
                    reason="redis package and MAPPROXY_TEST_REDIS env required")
class TestRedisCache(TileCacheTestBase):
    always_loads_metadata = False

    def setup_method(self):
        redis_host = os.environ['MAPPROXY_TEST_REDIS']
        self.host, self.port = redis_host.split(':')
        if os.environ.get('MAPPROXY_TEST_REDIS_TLS'):
            redis_host_tls = os.environ['MAPPROXY_TEST_REDIS_TLS']
            self.tls_host, self.tls_port = redis_host_tls.split(':')
        if os.environ.get('MAPPROXY_TEST_REDIS_AUTH'):
            redis_host_tls = os.environ['MAPPROXY_TEST_REDIS_AUTH']
            self.auth_host, self.auth_port = redis_host_tls.split(':')

        TileCacheTestBase.setup_method(self)

        self.cache = RedisCache(self.host, int(self.port), prefix='mapproxy-test', db=1)

    def teardown_method(self):
        for k in self.cache.r.keys('mapproxy-test-*'):
            self.cache.r.delete(k)
    
    def test_default_coverage(self):
        assert self.cache.coverage is None

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

    @pytest.mark.skipif(not redis or not os.environ.get('MAPPROXY_TEST_REDIS_TLS'),
                    reason="MAPPROXY_TEST_REDIS_TLS is required")
    def test_tls_authentication_enabled(self):
        print(os.curdir)
        ssl_certfile = 'mapproxy/test/unit/fixture/redis-client.crt'
        ssl_keyfile = 'mapproxy/test/unit/fixture/redis-client.key'
        ssl_ca_certs = 'mapproxy/test/unit/fixture/ca.crt'
        cache = RedisCache(self.tls_host, int(self.tls_port), prefix='mapproxy-test', db=1, ssl_certfile=ssl_certfile, ssl_keyfile=ssl_keyfile, ssl_ca_certs=ssl_ca_certs)
        assert cache.r.connection_pool.connection_kwargs['ssl_certfile'] == ssl_certfile
        assert cache.r.connection_pool.connection_kwargs['ssl_keyfile'] == ssl_keyfile
        assert cache.r.connection_pool.connection_kwargs['ssl_ca_certs'] == ssl_ca_certs
        t1 = self.create_tile(coord=(5382, 3234, 9))
        assert cache.store_tile(t1)
        time.sleep(0.1)
        t2 = Tile(t1.coord)
        assert cache.is_cached(t2)


    @pytest.mark.skipif(not redis or not os.environ.get('MAPPROXY_TEST_REDIS_TLS'),
                    reason="MAPPROXY_TEST_REDIS_TLS is required")
    def test_tls_authentication_disabled(self):
        cache = RedisCache(self.tls_host, int(self.tls_port), prefix='mapproxy-test', db=1)
        assert 'ssl_certfile' not in cache.r.connection_pool.connection_kwargs
        assert 'ssl_keyfile' not in cache.r.connection_pool.connection_kwargs
        assert 'ssl_ca_certs' not in cache.r.connection_pool.connection_kwargs
        assert not cache.r.connection_pool.connection_kwargs.get('ssl', False)
        t1 = self.create_tile(coord=(5382, 4234, 9))
        assert not cache.store_tile(t1)
        time.sleep(0.1)
        t2 = Tile(t1.coord)
        assert not cache.is_cached(t2)


    @pytest.mark.skipif(not redis or not os.environ.get('MAPPROXY_TEST_REDIS_AUTH'),
                    reason="MAPPROXY_TEST_REDIS_AUTH is required to test authentication")
    def test_user_password_authentication(self):
        username = 'test'
        password = 'pw4test'
        cache = RedisCache(self.auth_host, int(self.auth_port), prefix='mapproxy-test', db=1, username=username, password=password)
        assert cache.r.connection_pool.connection_kwargs['username'] == username
        assert cache.r.connection_pool.connection_kwargs['password'] == password
        t1 = self.create_tile(coord=(5382, 5234, 9))
        assert cache.store_tile(t1)
        t2 = Tile(t1.coord)
        assert cache.is_cached(t2)
