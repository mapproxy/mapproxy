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
        self.conn = psycopg2.connect("dbname=postgres user=postgres password=postgres")  # WIP
        self.cursor = self.conn.cursor()
        self.cache = TileCachePostgres(
            db_name='postgres',
            tile_grid=tile_grid(3857, name='global-webmarcator'),
            db_initialised=True,
            req_session=self.conn
        )

    def teardown(self):
        """
        Cleanup following the completion of all tests
        """
        self.cursor.close()
        self.conn.close()
        TileCacheTestBase.teardown(self)

    def test_load_empty_tileset(self):
        """
        Test insertion of empty tiles
        """
        assert self.cache.load_tiles([Tile(None)]) == True
        assert self.cache.load_tiles([Tile(None), Tile(None), Tile(None)]) == True

    def test_new_postgres(self):
        """
        Test a newly created postgres connection
        """
        should_be_empty = self.conn.cursor.execute('''SELECT * FROM tiles''').fetchall()
        assert len(should_be_empty) == 0

    def test_postgis(self):
        """
        Assure that postgis extends postgres instance
        """
        extens = self.conn.cursor.execute('''SELECT extname FROM pg_extension''').fetchall()
        assert extens.contains('postgis') == True

    def test_bulk_load(self):
        """
        Test loading many tiles at once
        """
        tiles = []
        for i in range(1, 200):
            tiles.append(self.create_tile((0, i, 0)))
        assert self.cache.store_tiles(tiles) == True

    def test_store_bulk_with_overwrite(self):
        """
        Testing inserting many tiles and some with overwrites
        """
        tiles = []
        for i in range(1, 200):
            tiles.append(self.create_tile((0, i, 0)))
        tiles2 = []
        for i in range(1, 100):
            tiles2.append(self.create_tile((0, i, 0)))
        assert self.cache.store_tiles(tiles) == True
        assert self.cache.store_tiles(tiles2) == True

    def test_config(self):
        """
        Test to see if database is configured properly
        """
        self.conn.cursor.execute('''SELECT table_name FROM pg_catalog.pg_tables WHERE schemaname = \'public\'''')
        tables = self.conn.cursor.fetchall()
        assert tables.contains('tiles')
        self.conn.cursor.execute('''SELECT indexdef FROM pg_indexes WHERE tablename = \'tiles\' ''')
        indexes = self.conn.cursor.fetchall()
        assert indexes.contains("CREATE INDEX land_polygons_z1_geom_geom_idx ON public.land_polygons_z1 "
                                "USING gist (geom)")
