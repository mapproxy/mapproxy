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

from io import BytesIO

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.test.http import MockServ
from mapproxy.test.image import is_png, create_tmp_image
from mapproxy.test.system import SysTest

import pytest


@pytest.fixture(scope="module")
def config_file():
    return "cache_mbtiles.yaml"


@pytest.fixture(scope="class")
def fixture_gpkg(base_dir):
    shutil.copy(
        os.path.join(os.path.dirname(__file__), "fixture", "cache.mbtiles"),
        base_dir.strpath,
    )


@pytest.mark.usefixtures("fixture_gpkg")
class TestMBTilesCache(SysTest):

    def setup_method(self):
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-180,-80,0,0",
                width="200",
                height="200",
                layers="mb",
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

    def test_get_map_uncached(self, app):
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
