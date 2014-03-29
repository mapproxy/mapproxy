from __future__ import with_statement

import re
import glob
import os
import time
import random

from nose.plugins.skip import SkipTest
from pycassa.system_manager import SystemManager, SIMPLE_STRATEGY
from mapproxy.cache.cassandra import CassandraCache

from mapproxy.cache.couchdb import CouchDBCache, CouchDBMDTemplate
from mapproxy.cache.tile import Tile
from mapproxy.grid import tile_grid
from mapproxy.test.image import create_tmp_image_buf

from mapproxy.test.unit.test_cache_tile import TileCacheTestBase

from nose.tools import assert_almost_equal, eq_

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


