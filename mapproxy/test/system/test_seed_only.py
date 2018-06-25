# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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

from io import BytesIO

import pytest

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.compat.image import Image
from mapproxy.test.image import is_png, is_jpeg
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "seedonly.yaml"


class TestSeedOnlyWMS(SysTest):

    def setup(self):
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-180,0,0,80",
                width="200",
                height="200",
                layers="wms_cache",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
                transparent=True,
            ),
        )

    def test_get_map_cached(self, app, fixture_cache_data):
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        assert img.mode == "RGB"
        # cached image has more that 256 colors, getcolors -> None
        assert img.getcolors() == None

    def test_get_map_uncached(self, app):
        self.common_map_req.params["bbox"] = "10,10,20,20"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        assert img.mode == "RGBA"
        assert img.getcolors() == [(200 * 200, (255, 255, 255, 0))]


class TestSeedOnlyTMS(SysTest):

    def test_get_tile_cached(self, app, fixture_cache_data):
        resp = app.get("/tms/1.0.0/wms_cache/0/0/1.jpeg")
        assert resp.content_type == "image/jpeg"
        data = BytesIO(resp.body)
        assert is_jpeg(data)
        img = Image.open(data)
        assert img.mode == "RGB"
        # cached image has more that 256 colors, getcolors -> None
        assert img.getcolors() == None

    def test_get_tile_uncached(self, app):
        resp = app.get("/tms/1.0.0/wms_cache/0/0/0.jpeg")
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        assert img.mode == "RGBA"
        assert img.getcolors() == [(256 * 256, (255, 255, 255, 0))]
