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

import pytest

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.request.wmts import WMTS100CapabilitiesRequest
from mapproxy.test.image import img_from_buf
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "cache_band_merge.yaml"


@pytest.mark.usefixtures("fixture_cache_data")
class TestCacheSource(SysTest):

    # test various band merge configurations with
    # cached base tile 0/0/0.png (R: 50 G: 100 B: 200)

    def setup(self):
        self.common_cap_req = WMTS100CapabilitiesRequest(
            url="/service?",
            param=dict(service="WMTS", version="1.0.0", request="GetCapabilities"),
        )
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-180,0,0,80",
                width="100",
                height="100",
                layers="dop_l",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
            ),
        )

    def test_capabilities(self, app):
        req = str(self.common_cap_req)
        resp = app.get(req)
        assert resp.content_type == "application/xml"

    def test_get_tile_021(self, app):
        resp = app.get("/wmts/dop_021/GLOBAL_WEBMERCATOR/0/0/0.png")
        assert resp.content_type == "image/png"
        img = img_from_buf(resp.body)
        assert img.mode == "RGB"
        assert img.getpixel((0, 0)) == (50, 200, 100)

    def test_get_tile_l(self, app):
        resp = app.get("/wmts/dop_l/GLOBAL_WEBMERCATOR/0/0/0.png")
        assert resp.content_type == "image/png"
        img = img_from_buf(resp.body)
        assert img.mode == "L"
        assert img.getpixel((0, 0)) == int(50 * 0.25 + 0.7 * 100 + 0.05 * 200)

    def test_get_tile_0(self, app):
        resp = app.get("/wmts/dop_0/GLOBAL_WEBMERCATOR/0/0/0.png")
        assert resp.content_type == "image/png"
        img = img_from_buf(resp.body)
        assert img.mode == "RGB"  # forced with image.mode
        assert img.getpixel((0, 0)) == (50, 50, 50)

    def test_get_tile_0122(self, app):
        resp = app.get("/wmts/dop_0122/GLOBAL_WEBMERCATOR/0/0/0.png")
        assert resp.content_type == "image/png"
        img = img_from_buf(resp.body)
        assert img.mode == "RGBA"
        assert img.getpixel((0, 0)) == (50, 100, 200, 50)

    def test_get_map_l(self, app):
        resp = app.get(str(self.common_map_req))
        assert resp.content_type == "image/png"
        img = img_from_buf(resp.body)
        assert img.mode == "L"
        assert img.getpixel((0, 0)) == int(50 * 0.25 + 0.7 * 100 + 0.05 * 200)

    def test_get_map_l_jpeg(self, app):
        self.common_map_req.params.format = "image/jpeg"
        resp = app.get(str(self.common_map_req))
        assert resp.content_type == "image/jpeg"
        img = img_from_buf(resp.body)
        assert img.mode == "RGB"
        # L converted to RGB for jpeg
        assert img.getpixel((0, 0)) == (92, 92, 92)
