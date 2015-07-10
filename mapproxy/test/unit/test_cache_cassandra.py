from __future__ import with_statement
import os

from cassandra.cluster import Cluster
from nose.plugins.skip import SkipTest

from mapproxy.cache.cassandra_cql import CassandraCache
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
        self.host = os.environ[cassandra_server_env]

        self.cluster = Cluster([self.host])
        self.session = self.cluster.connect()

        self.session.execute("create keyspace if not exists testspace with replication = "
                             "{'class': 'SimpleStrategy', 'replication_factor': 1}")
        self.session.set_keyspace('testspace')
        self.session.execute("create table if not exists testtable (key text primary key, img blob, created bigint, length bigint)")

        TileCacheTestBase.setup(self)

        self.cache = CassandraCache([{'host': self.host},], '9042', 'testspace', 'testtable', self.cache_dir)

    def teardown(self):
        self.session.execute("drop keyspace testspace")

