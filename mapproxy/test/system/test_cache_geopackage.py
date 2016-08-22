# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

from __future__ import with_statement, division

import os
import shutil

from io import BytesIO

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.test.http import MockServ
from mapproxy.test.image import is_png, create_tmp_image
from mapproxy.test.system import prepare_env, create_app, module_teardown, SystemTest
from mapproxy.cache.tile import Tile
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase
from mapproxy.cache.geopackage import GeopackageCache, GeopackageLevelCache
from mapproxy.config.loader import load_configuration
from mapproxy.image import ImageSource
from mapproxy.grid import TileGrid
import time, threading
from nose.tools import eq_
import sqlite3

test_config = {}


def setup_module():
    prepare_env(test_config, 'cache_geopackage.yaml')

    shutil.copy(os.path.join(test_config['fixture_dir'], 'cache.gpkg'),
        test_config['base_dir'])
    create_app(test_config)


def teardown_module():
    module_teardown(test_config)


class TestGeopackageCache(SystemTest, TileCacheTestBase):
    config = test_config
    table_name = 'cache'

    def setup(self):
        configuration = load_configuration(self.config.get('config_file'))
        TileCacheTestBase.setup(self)
        self.cache = GeopackageCache(os.path.join(self.cache_dir, 'tmp.geopackage'),
                                     configuration.grids.get('GLOBAL_GEODETIC').tile_grid(),
                                     self.table_name)

    def teardown(self):
        if self.cache:
            self.cache.cleanup()
        TileCacheTestBase.teardown(self)

    def test_get_map_cached(self):
        prepare_env(test_config, 'cache_geopackage.yaml')
        create_app(test_config)
        SystemTest.setup(self)
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
                                                                           version='1.1.1', bbox='-180,-80,0,0',
                                                                           width='200', height='200',
                                                                           layers='gpkg', srs='EPSG:4326',
                                                                           format='image/png',
                                                                           styles='', request='GetMap'))
        resp = self.app.get(self.common_map_req)
        eq_(resp.content_type, 'image/png')
        data = BytesIO(resp.body)
        assert is_png(data)

    def test_get_map_uncached(self):
        prepare_env(test_config, 'cache_geopackage.yaml')
        create_app(test_config)
        SystemTest.setup(self)
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
                                                                           version='1.1.1', bbox='-180,-80,0,0',
                                                                           width='200', height='200',
                                                                           layers='gpkg', srs='EPSG:4326',
                                                                           format='image/png',
                                                                           styles='', request='GetMap'))
        assert os.path.exists(os.path.join(test_config['base_dir'], 'cache.gpkg')) # already created on startup

        self.common_map_req.params.bbox = '-180,0,0,80'
        serv = MockServ(port=42423)
        serv.expects('/tiles/01/000/000/000/000/000/001.png')
        serv.returns(create_tmp_image((256, 256)))
        with serv:
            resp = self.app.get(self.common_map_req)
            eq_(resp.content_type, 'image/png')
            data = BytesIO(resp.body)
            assert is_png(data)

        # now cached
        resp = self.app.get(self.common_map_req)
        eq_(resp.content_type, 'image/png')
        data = BytesIO(resp.body)
        assert is_png(data)

    def test_bad_config_geopackage_no_gpkg_contents(self):
        gpkg_file = os.path.join(test_config['base_dir'], 'cache.gpkg')
        table_name = 'no_gpkg_contents'

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name=?''',
                             (table_name,))
            content = cur.fetchone()
            assert content[0] == table_name

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute('''SELECT table_name FROM gpkg_contents WHERE table_name=?''',
                             (table_name,))
            content = cur.fetchone()
            assert not content

        GeopackageCache(gpkg_file, TileGrid(srs=4326), table_name=table_name)

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute('''SELECT table_name FROM gpkg_contents WHERE table_name=?''',
                             (table_name,))
            content = cur.fetchone()
            assert content[0] == table_name

    def test_bad_config_geopackage_no_spatial_ref_sys(self):
        gpkg_file = os.path.join(test_config['base_dir'], 'cache.gpkg')
        organization_coordsys_id = 3785
        table_name='no_gpkg_spatial_ref_sys'

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute('''SELECT organization_coordsys_id FROM gpkg_spatial_ref_sys WHERE organization_coordsys_id=?''',
                             (organization_coordsys_id,))
            content = cur.fetchone()
            assert not content

        GeopackageCache(gpkg_file, TileGrid(srs=3785), table_name=table_name)

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute(
                '''SELECT organization_coordsys_id FROM gpkg_spatial_ref_sys WHERE organization_coordsys_id=?''',
                (organization_coordsys_id,))
            content = cur.fetchone()
            assert content[0] == organization_coordsys_id

    def test_new_geopackage(self):
        SystemTest.setup(self)
        gpkg_file = os.path.join(test_config['base_dir'], 'cache_new.gpkg')
        table_name = 'cache'
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
                                                                           version='1.1.1', bbox='-180,-80,0,0',
                                                                           width='200', height='200',
                                                                           layers="gpkg_new", srs='EPSG:4326',
                                                                           format='image/png',
                                                                           styles='', request='GetMap'))
        assert os.path.exists(gpkg_file)

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name=?''',
                             (table_name,))
            content = cur.fetchone()
            assert content[0] == table_name

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute('''SELECT table_name, data_type FROM gpkg_contents WHERE table_name = ?''',
                             (table_name,))
            content = cur.fetchone()
            assert content[0] == table_name
            assert content[1] == 'tiles'

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute('''SELECT table_name FROM gpkg_tile_matrix WHERE table_name = ?''',
                             (table_name,))
            content = cur.fetchall()
            assert len(content) == 20

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute('''SELECT table_name FROM gpkg_tile_matrix_set WHERE table_name = ?''',
                             (table_name,))
            content = cur.fetchone()
            assert content[0] == table_name

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


class TestGeopackageLevelCache(SystemTest, TileCacheTestBase):
    config = test_config
    table_name = 'cache'
    cache_dir = None
    cache = None

    def setup(self):
        configuration = load_configuration(self.config.get('config_file'))
        TileCacheTestBase.setup(self)
        self.cache_dir = os.path.join(self.cache_dir, 'tmp.geopackage')
        self.cache = GeopackageLevelCache(self.cache_dir,
                                         configuration.grids.get('GLOBAL_GEODETIC').tile_grid(),
                                         self.table_name)

    def teardown(self):
        if self.cache:
            self.cache.cleanup()
        TileCacheTestBase.teardown(self)

    def test_level_files(self):
        if os.path.exists(self.cache_dir):
            eq_(os.listdir(self.cache_dir), [])

        self.cache.store_tile(self.create_tile((0, 0, 1)))
        eq_(os.listdir(self.cache_dir), ['1.gpkg'])

        self.cache.store_tile(self.create_tile((0, 0, 5)))
        eq_(sorted(os.listdir(self.cache_dir)), ['1.gpkg', '5.gpkg'])

    def test_remove_level_files(self):
        self.cache.store_tile(self.create_tile((0, 0, 1)))
        self.cache.store_tile(self.create_tile((0, 0, 2)))
        eq_(sorted(os.listdir(self.cache_dir)), ['1.gpkg', '2.gpkg'])

        self.cache.remove_level_tiles_before(1, timestamp=0)
        eq_(os.listdir(self.cache_dir), ['2.gpkg'])

    def test_remove_level_tiles_before(self):
        self.cache.store_tile(self.create_tile((0, 0, 1)))
        self.cache.store_tile(self.create_tile((0, 0, 2)))

        eq_(sorted(os.listdir(self.cache_dir)), ['1.gpkg', '2.gpkg'])
        assert self.cache.is_cached(Tile((0, 0, 1)))

        self.cache.remove_level_tiles_before(1, timestamp=time.time() - 60)
        assert self.cache.is_cached(Tile((0, 0, 1)))

        self.cache.remove_level_tiles_before(1, timestamp=0)
        assert not self.cache.is_cached(Tile((0, 0, 1)))

        eq_(sorted(os.listdir(self.cache_dir)), ['1.gpkg', '2.gpkg'])
        assert self.cache.is_cached(Tile((0, 0, 2)))
