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
from mapproxy.cache.geopackage import GeopackageCache
from mapproxy.grid import TileGrid
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


class TestGeopackageCache(SystemTest):
    config = test_config
    table_name = 'cache'

    def setup(self):
        SystemTest.setup(self)
        self.common_map_req = WMS111MapRequest(url='/service?',
            param=dict(service='WMS',
                       version='1.1.1', bbox='-180,-80,0,0',
                       width='200', height='200',
                       layers='gpkg', srs='EPSG:4326',
                       format='image/png',
                       styles='', request='GetMap'))

    def test_get_map_cached(self):
        resp = self.app.get(self.common_map_req)
        eq_(resp.content_type, 'image/png')
        data = BytesIO(resp.body)
        assert is_png(data)

    def test_get_map_uncached(self):
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
