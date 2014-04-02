from __future__ import with_statement
import os
from string import split

from pycassa.system_manager import SystemManager, SIMPLE_STRATEGY
from nose.plugins.skip import SkipTest

from mapproxy.cache.cassandra import CassandraCache
from mapproxy.test.image import create_tmp_image_buf
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase


tile_image = create_tmp_image_buf((256, 256), color='blue')
tile_image2 = create_tmp_image_buf((256, 256), color='red')


class TestCassandraCache(TileCacheTestBase):
    always_loads_metadata = True

    def setup(self):
        cassandra_server_env = 'CASSANDRA_SERVER'
        if not os.environ.get(cassandra_server_env):
            raise SkipTest()
        self.server = os.environ[cassandra_server_env]
        host, port = split(self.server, ':')
        self.nodes = [{'host': host, 'port': port}]
        self.keyspace = 'TESTSPACE'
        self.columnfamily = 'Testfamily'

        self.sys = SystemManager(self.server)
        self.sys.create_keyspace(self.keyspace, SIMPLE_STRATEGY, {'replication_factor': '1'})
        self.sys.create_column_family(self.keyspace, self.columnfamily)

        TileCacheTestBase.setup(self)

        self.cache = CassandraCache(self.nodes, self.keyspace, self.columnfamily, self.cache_dir)

    def teardown(self):
        self.sys.drop_keyspace(self.keyspace)
        self.sys.close()


