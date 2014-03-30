from __future__ import with_statement

from pycassa.system_manager import SystemManager, SIMPLE_STRATEGY
from nose.tools import nottest

from mapproxy.cache.cassandra import CassandraCache
from mapproxy.cache.tile import Tile
from mapproxy.test.image import create_tmp_image_buf
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase


tile_image = create_tmp_image_buf((256, 256), color='blue')
tile_image2 = create_tmp_image_buf((256, 256), color='red')


class CassandraCacheTestBase(TileCacheTestBase):
    always_loads_metadata = True

    def setup(self):
        self.server = ['localhost:9160']
        self.keyspace = 'TESTSPACE'
        self.columnfamily = 'Testfamily'

        self.sys = SystemManager(self.server[0])
        self.sys.create_keyspace(self.keyspace, SIMPLE_STRATEGY, {'replication_factor': '1'})
        self.sys.create_column_family(self.keyspace, self.columnfamily)

        TileCacheTestBase.setup(self)

        self.cache = CassandraCache(self.server, self.keyspace, self.columnfamily, self.cache_dir, self.readonly)

    def teardown(self):
        self.sys.drop_keyspace(self.keyspace)
        self.sys.close()


class TestCassandraCache(CassandraCacheTestBase):
    readonly = False


class TestCassandraCacheReadonly(CassandraCacheTestBase):
    readonly = True

    @nottest
    def test_overwrite_tile(self):
        pass

    @nottest
    def test_is_cached_hit(self):
        pass

    @nottest
    def test_load_stored_tile(self):
        pass

    @nottest
    def test_load_tile_cached(self):
        pass

    @nottest
    def test_load_tiles_cached(self):
        pass

    @nottest
    def test_load_tiles_mixed(self):
        pass

    def test_remove(self):
        tile = self.create_tile((1, 0, 4))
        self.cache.store_tile(tile)
        assert not self.cache.is_cached(Tile((1, 0, 4)))
        assert self.cache.remove_tile(Tile((1, 0, 4)))

    def test_store_tiles(self):
        tiles = [self.create_tile((x, 0, 4)) for x in range(4)]
        assert not self.cache.store_tiles(tiles)
        tiles = [Tile((x, 0, 4)) for x in range(4)]
        for tile in tiles:
            assert not self.cache.is_cached(tile)

    @nottest
    def test_store_tile_already_stored(self):
        pass
