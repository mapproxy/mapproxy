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

from __future__ import division

import os
import shutil
import sqlite3

from io import BytesIO

import pytest

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.test.http import MockServ
from mapproxy.test.image import is_png, create_tmp_image
from mapproxy.test.system import SysTest
from mapproxy.cache.geopackage import GeopackageCache
from mapproxy.grid import TileGrid


@pytest.fixture(scope="module")
def config_file():
    return "cache_geopackage.yaml"


@pytest.fixture(scope="class")
def fixture_gpkg(base_dir):
    shutil.copy(
        os.path.join(os.path.dirname(__file__), "fixture", "cache.gpkg"),
        base_dir.strpath,
    )


@pytest.mark.usefixtures("fixture_gpkg")
class TestGeopackageCache(SysTest):

    def setup(self):
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-180,-80,0,0",
                width="200",
                height="200",
                layers="gpkg",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
            ),
        )

    def test_get_map_cached(self, app):
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)

    def test_get_map_uncached(self, app, base_dir):
        assert base_dir.join("cache.gpkg").check()
        # already created on startup

        self.common_map_req.params.bbox = "-180,0,0,80"
        serv = MockServ(port=42423)
        serv.expects("/tiles/01/000/000/000/000/000/001.png")
        serv.returns(create_tmp_image((256, 256)))
        with serv:
            resp = app.get(self.common_map_req)
            assert resp.content_type == "image/png"
            data = BytesIO(resp.body)
            assert is_png(data)

        # now cached
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)

    def test_bad_config_geopackage_no_gpkg_contents(self, app, base_dir):
        gpkg_file = base_dir.join("cache.gpkg").strpath
        table_name = "no_gpkg_contents"

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name=?""",
                (table_name,),
            )
            content = cur.fetchone()
            assert content[0] == table_name

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute(
                """SELECT table_name FROM gpkg_contents WHERE table_name=?""",
                (table_name,),
            )
            content = cur.fetchone()
            assert not content

        GeopackageCache(gpkg_file, TileGrid(srs=4326), table_name=table_name)

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute(
                """SELECT table_name FROM gpkg_contents WHERE table_name=?""",
                (table_name,),
            )
            content = cur.fetchone()
            assert content[0] == table_name

    def test_bad_config_geopackage_no_spatial_ref_sys(self, base_dir):
        gpkg_file = base_dir.join("cache.gpkg").strpath
        organization_coordsys_id = 3785
        table_name = "no_gpkg_spatial_ref_sys"

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute(
                """SELECT organization_coordsys_id FROM gpkg_spatial_ref_sys WHERE organization_coordsys_id=?""",
                (organization_coordsys_id,),
            )
            content = cur.fetchone()
            assert not content

        GeopackageCache(gpkg_file, TileGrid(srs=3785), table_name=table_name)

        with sqlite3.connect(gpkg_file) as db:
            cur = db.execute(
                """SELECT organization_coordsys_id FROM gpkg_spatial_ref_sys WHERE organization_coordsys_id=?""",
                (organization_coordsys_id,),
            )
            content = cur.fetchone()
            assert content[0] == organization_coordsys_id
