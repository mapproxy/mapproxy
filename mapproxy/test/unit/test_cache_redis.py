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
from unittest import mock

import pytest

try:
    import redis
except ImportError:
    redis = None

from mapproxy.cache.redis import RedisCache
from mapproxy.cache.tile import Tile
from mapproxy.image import ImageResult
from mapproxy.image.opts import ImageOptions
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase, tile_image


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
        cache = RedisCache(
            self.tls_host, int(self.tls_port), prefix='mapproxy-test', db=1, ssl_certfile=ssl_certfile,
            ssl_keyfile=ssl_keyfile, ssl_ca_certs=ssl_ca_certs)
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
        cache = RedisCache(
            self.auth_host, int(self.auth_port), prefix='mapproxy-test', db=1, username=username, password=password)
        assert cache.r.connection_pool.connection_kwargs['username'] == username
        assert cache.r.connection_pool.connection_kwargs['password'] == password
        t1 = self.create_tile(coord=(5382, 5234, 9))
        assert cache.store_tile(t1)
        t2 = Tile(t1.coord)
        assert cache.is_cached(t2)


@pytest.mark.skipif(not redis, reason="redis package required")
class TestRedisErrorHandling:
    """An unavailable Redis (timeout/connection error) must fall back gracefully
    — return False / not crash the worker — so MapProxy can use the next cache.
    Any other exception indicates a real defect and must propagate.

    StrictRedis connects lazily, so these run without a live server: we build a
    RedisCache and swap in a fake client that raises on every operation.
    """

    def _cache_with_client(self, client):
        cache = RedisCache('localhost', 6379, prefix='mapproxy-test', db=1)
        cache.r = client
        return cache

    def _stored_tile(self):
        return Tile((0, 0, 1),
                    ImageResult(tile_image, image_opts=ImageOptions(format='image/png')))

    def _client_raising(self, exc):
        client = mock.Mock()
        client.exists.side_effect = exc
        client.get.side_effect = exc
        client.set.side_effect = exc
        client.delete.side_effect = exc
        pipe = mock.Mock()
        pipe.execute.side_effect = exc
        client.pipeline.return_value = pipe
        return client

    @pytest.mark.parametrize('exc', [
        redis.exceptions.TimeoutError if redis else None,
        redis.exceptions.ConnectionError if redis else None,
    ])
    def test_unavailable_redis_falls_back(self, exc):
        cache = self._cache_with_client(self._client_raising(exc()))
        assert cache.is_cached(Tile((0, 0, 1))) is False
        assert cache.load_tile(Tile((0, 0, 1))) is False
        tile = self._stored_tile()
        assert cache.store_tile(tile) is False
        # a failed store must not leave the tile marked stored, otherwise a
        # fallback cache in a cascade would skip it
        assert tile.stored is False
        assert cache.remove_tile(Tile((0, 0, 1))) is False
        # metadata loading must not raise
        cache.load_tile_metadata(Tile((0, 0, 1)))

    def test_other_exception_propagates(self):
        cache = self._cache_with_client(self._client_raising(ValueError("boom")))
        with pytest.raises(ValueError):
            cache.is_cached(Tile((0, 0, 1)))
        with pytest.raises(ValueError):
            cache.load_tile(Tile((0, 0, 1)))
        with pytest.raises(ValueError):
            cache.store_tile(self._stored_tile())
        with pytest.raises(ValueError):
            cache.remove_tile(Tile((0, 0, 1)))
        with pytest.raises(ValueError):
            cache.load_tile_metadata(Tile((0, 0, 1)))
