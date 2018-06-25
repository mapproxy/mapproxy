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
import sqlite3
import threading
import time

from io import BytesIO

from mapproxy.cache.geopackage import GeopackageCache, GeopackageLevelCache
from mapproxy.cache.tile import Tile
from mapproxy.grid import tile_grid, TileGrid
from mapproxy.image import ImageSource
from mapproxy.test.helper import assert_files_in_dir
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase


class TestGeopackageCache(TileCacheTestBase):

    always_loads_metadata = True

    def setup(self):
        TileCacheTestBase.setup(self)
        self.gpkg_file = os.path.join(self.cache_dir, 'tmp.gpkg')
        self.table_name = 'test_tiles'
        self.cache = GeopackageCache(
            self.gpkg_file,
            tile_grid=tile_grid(3857, name='global-webmarcator'),
            table_name=self.table_name,
        )

    def teardown(self):
        if self.cache:
            self.cache.cleanup()
        TileCacheTestBase.teardown(self)

    def test_new_geopackage(self):
        assert os.path.exists(self.gpkg_file)

        with sqlite3.connect(self.gpkg_file) as db:
            cur = db.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name=?''',
                             (self.table_name,))
            content = cur.fetchone()
            assert content[0] == self.table_name

        with sqlite3.connect(self.gpkg_file) as db:
            cur = db.execute('''SELECT table_name, data_type FROM gpkg_contents WHERE table_name = ?''',
                             (self.table_name,))
            content = cur.fetchone()
            assert content[0] == self.table_name
            assert content[1] == 'tiles'

        with sqlite3.connect(self.gpkg_file) as db:
            cur = db.execute('''SELECT table_name FROM gpkg_tile_matrix WHERE table_name = ?''',
                             (self.table_name,))
            content = cur.fetchall()
            assert len(content) == 20

        with sqlite3.connect(self.gpkg_file) as db:
            cur = db.execute('''SELECT table_name FROM gpkg_tile_matrix_set WHERE table_name = ?''',
                             (self.table_name,))
            content = cur.fetchone()
            assert content[0] == self.table_name

    def test_load_empty_tileset(self):
        assert self.cache.load_tiles([Tile(None)]) == True
        assert self.cache.load_tiles([Tile(None), Tile(None), Tile(None)]) == True

    def test_load_more_than_2000_tiles(self):
        # prepare data
        for i in range(0, 2010):
            assert self.cache.store_tile(Tile((i, 0, 10),  ImageSource(BytesIO(b'foo'))))

        tiles = [Tile((i, 0, 10)) for i in range(0, 2010)]
        assert self.cache.load_tiles(tiles)

    def test_timeouts(self):
        self.cache._db_conn_cache.db = sqlite3.connect(self.cache.geopackage_file, timeout=0.05)

        def block():
            # block database by delaying the commit
            db = sqlite3.connect(self.cache.geopackage_file)
            cur = db.cursor()
            stmt = "INSERT OR REPLACE INTO {0} (zoom_level, tile_column, tile_row, tile_data) " \
                   "VALUES (?,?,?,?)".format(self.table_name)
            cur.execute(stmt, (3, 1, 1, '1234'))
            time.sleep(0.2)
            db.commit()

        try:
            assert self.cache.store_tile(self.create_tile((0, 0, 1))) == True

            t = threading.Thread(target=block)
            t.start()
            time.sleep(0.05)
            assert self.cache.store_tile(self.create_tile((0, 0, 1))) == False
        finally:
            t.join()

        assert self.cache.store_tile(self.create_tile((0, 0, 1))) == True


class TestGeopackageLevelCache(TileCacheTestBase):

    always_loads_metadata = True

    def setup(self):
        TileCacheTestBase.setup(self)
        self.cache = GeopackageLevelCache(
            self.cache_dir,
            tile_grid=tile_grid(3857, name='global-webmarcator'),
            table_name='test_tiles',
        )

    def teardown(self):
        if self.cache:
            self.cache.cleanup()
        TileCacheTestBase.teardown(self)

    def test_level_files(self):
        if os.path.exists(self.cache_dir):
            assert_files_in_dir(self.cache_dir, [], glob='*.gpkg')

        self.cache.store_tile(self.create_tile((0, 0, 1)))
        assert_files_in_dir(self.cache_dir, ['1.gpkg'], glob='*.gpkg')

        self.cache.store_tile(self.create_tile((0, 0, 5)))
        assert_files_in_dir(self.cache_dir, ['1.gpkg', '5.gpkg'], glob='*.gpkg')

    def test_remove_level_files(self):
        self.cache.store_tile(self.create_tile((0, 0, 1)))
        self.cache.store_tile(self.create_tile((0, 0, 2)))
        assert_files_in_dir(self.cache_dir, ['1.gpkg', '2.gpkg'], glob='*.gpkg')

        self.cache.remove_level_tiles_before(1, timestamp=0)
        assert_files_in_dir(self.cache_dir, ['2.gpkg'], glob='*.gpkg')

    def test_remove_level_tiles_before(self):
        self.cache.store_tile(self.create_tile((0, 0, 1)))
        self.cache.store_tile(self.create_tile((0, 0, 2)))

        assert_files_in_dir(self.cache_dir, ['1.gpkg', '2.gpkg'], glob='*.gpkg')
        assert self.cache.is_cached(Tile((0, 0, 1)))

        self.cache.remove_level_tiles_before(1, timestamp=time.time() - 60)
        assert self.cache.is_cached(Tile((0, 0, 1)))

        self.cache.remove_level_tiles_before(1, timestamp=0)
        assert not self.cache.is_cached(Tile((0, 0, 1)))

        assert_files_in_dir(self.cache_dir, ['1.gpkg', '2.gpkg'], glob='*.gpkg')
        assert self.cache.is_cached(Tile((0, 0, 2)))


    def test_bulk_store_tiles_with_different_levels(self):
        self.cache.store_tiles([
            self.create_tile((0, 0, 1)),
            self.create_tile((0, 0, 2)),
            self.create_tile((1, 0, 2)),
            self.create_tile((1, 0, 1)),
        ])

        assert_files_in_dir(self.cache_dir, ['1.gpkg', '2.gpkg'], glob='*.gpkg')
        assert self.cache.is_cached(Tile((0, 0, 1)))
        assert self.cache.is_cached(Tile((1, 0, 1)))
        assert self.cache.is_cached(Tile((0, 0, 2)))
        assert self.cache.is_cached(Tile((1, 0, 2)))

class TestGeopackageCacheInitErrors(object):
    table_name = 'cache'

    def test_bad_config_geopackage_srs(self):
        error_msg = None
        gpkg_file = os.path.join(os.path.join(os.path.dirname(__file__),
                                                              'fixture'),
                                 'cache.gpkg')
        table_name = 'cache'
        try:
            GeopackageCache(gpkg_file, TileGrid(srs=4326), table_name)
        except ValueError as ve:
            error_msg = ve
        assert "srs is improperly configured." in str(error_msg)

    def test_bad_config_geopackage_tile(self):
        error_msg = None
        gpkg_file = os.path.join(os.path.join(os.path.dirname(__file__),
                                                              'fixture'),
                                 'cache.gpkg')
        table_name = 'cache'
        try:
            GeopackageCache(gpkg_file, TileGrid(srs=900913, tile_size=(512, 512)), table_name)
        except ValueError as ve:
            error_msg = ve
        assert "tile_size is improperly configured." in str(error_msg)

    def test_bad_config_geopackage_res(self):
        error_msg = None
        gpkg_file = os.path.join(os.path.join(os.path.dirname(__file__),
                                              'fixture'),
                                 'cache.gpkg')
        table_name = 'cache'
        try:
            GeopackageCache(gpkg_file, TileGrid(srs=900913, res=[1000, 100, 10]), table_name)
        except ValueError as ve:
            error_msg = ve
        assert "res is improperly configured." in str(error_msg)
