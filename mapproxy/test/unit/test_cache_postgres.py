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

from __future__ import division

import os
import psycopg2
import threading
import time

from io import BytesIO

from mapproxy.cache.postgres import TileCachePostgres
from mapproxy.cache.tile import Tile
from mapproxy.grid import tile_grid, TileGrid
from mapproxy.image import ImageSource
from mapproxy.test.helper import assert_files_in_dir
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase


class TestCachePostgres(TileCacheTestBase):

    always_loads_metadata = True

    def setup(self):
        """
        Create common setup across all tests
        """
        TileCacheTestBase.setup(self)
        self.table_name = 'test_tiles'
        self.cache = TileCachePostgres(
            tile_grid=tile_grid(3857, name='global-webmarcator'),
            table_name=self.table_name,
        )

    def teardown(self):
        """
        Cleanup following the completion of all tests
        """
        if self.cache:
            self.cache.cleanup()
        TileCacheTestBase.teardown(self)

    def test_new_postgres(self):
        """
        Test a new Postgres Cache to check connection and see if iy id organized properly
        """
        return None

    def test_load_empty_tileset(self):
        """
        load an empty set of tiles
        """
        assert self.cache.load_tiles([Tile(None)]) == True
        assert self.cache.load_tiles([Tile(None), Tile(None), Tile(None)]) == True

    def test_load_more_than_2000_tiles(self):
        """
        Test loading of a large number of tiles to make sure tiles are still loaded in properly
        """
        return None

    def test_timeouts(self):
        """
        Test timing out
        """
        self.assertTrue(False)


class TestPostgresLevelCache(TileCacheTestBase):

    always_loads_metadata = True

    def setup(self):
        """
        Setup for common requirements across all tests within the PostgresLevelCache
        """
        TileCacheTestBase.setup(self)


    def teardown(self):
        """
        Cleanup following the completion of tests
        """
        if self.cache:
            self.cache.cleanup()
        TileCacheTestBase.teardown(self)


