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

import pytest

from mapproxy.test.image import tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "extra_params.yaml"


class TestExtraParams(SysTest):

    wms_source_url = (
        r"/service?LAYERS=bar&SERVICE=WMS&FORMAT=image%2Fpng"
        "&REQUEST=GetMap&WIDTH=256&HEIGHT=256&SRS=EPSG%3A3857&styles="
        "&VERSION=1.1.1"
        "&BBOX=-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244"
        # The key should be present in the request to the source
        "&key=123456"
    )

    tile_source_url = r"/tile.png?key=123456"

    def test_tms_request_to_tile_source(self, app, cache_dir):
        with tmp_image((256, 256), format="png") as img:
            expected_req = (
                {"path": self.tile_source_url},
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                app.get("/tms/1.0.0/tile_layer/EPSG3857/0/0/0.png?key=123456")

    def test_tile_request_to_tile_source(self, app, cache_dir):
        with tmp_image((256, 256), format="png") as img:
            expected_req = (
                {"path": self.tile_source_url},
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                app.get("/tiles/tile_layer/EPSG3857/0/0/0.png?key=123456")

    def test_wmts_kvp_request_to_tile_source(self, app, cache_dir):
        with tmp_image((256, 256), format="png") as img:
            expected_req = (
                {"path": self.tile_source_url},
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                url = (
                    "/service?layer=tile_layer&style=&tilematrixset=webmercator&Service=WMTS&"
                    "Request=GetTile&Version=1.0.0&Format=png&TileMatrix=0&TileCol=0&TileRow=0&key=123456"
                )
                app.get(url)

    def test_wmts_rest_request_to_tile_source(self, app, cache_dir):
        with tmp_image((256, 256), format="png") as img:
            expected_req = (
                {"path": self.tile_source_url},
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                app.get("/wmts/tile_layer/webmercator/0/0/0.png?key=123456")

    def test_wms_request_to_tile_source(self, app, cache_dir):
        with tmp_image((256, 256), format="png") as img:
            expected_req = (
                {"path": self.wms_source_url},
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                url = (
                    "/service?service=WMS&version=1.1.1"
                    "&bbox=-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244"
                    "&width=256&height=256&layers=wms_layer&srs=EPSG%3A3857&format=image%2Fpng"
                    "&styles=&request=GetMap&key=123456"
                )
                app.get(url)

    def test_tiles_request_to_wms_source(self, app, cache_dir):
        with tmp_image((256, 256), format="png") as img:
            expected_req = (
                {"path": self.wms_source_url},
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                app.get("/tiles/wms_layer/EPSG3857/0/0/0.png?key=123456")

    def test_wmts_kvp_request_to_wms_source(self, app, cache_dir):
        with tmp_image((256, 256), format="png") as img:
            expected_req = (
                {"path": self.wms_source_url},
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                url = (
                    "/service?layer=wms_layer&style=&tilematrixset=webmercator&Service=WMTS&"
                    "Request=GetTile&Version=1.0.0&Format=png&TileMatrix=0&TileCol=0&TileRow=0&key=123456"
                )
                app.get(url)

    def test_wmts_rest_request_to_wms_source(self, app, cache_dir):
        with tmp_image((256, 256), format="png") as img:
            expected_req = (
                {"path": self.wms_source_url},
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                app.get("/wmts/wms_layer/webmercator/0/0/0.png?key=123456")

    def test_wms_request_to_wms_source(self, app, cache_dir):
        with tmp_image((256, 256), format="png") as img:
            expected_req = (
                {
                    "path": self.wms_source_url
                },
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req]
            ):
                url = (
                    "/service?service=WMS&version=1.1.1"
                    "&bbox=-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244"
                    "&width=256&height=256&layers=wms_layer&srs=EPSG%3A3857&format=image%2Fpng"
                    "&styles=&request=GetMap&key=123456"
                )
                app.get(url)

    def test_wms_request_to_wms_source_direct(self, app, cache_dir):
        with tmp_image((256, 256), format="png") as img:
            expected_req = (
                {
                    "path": self.wms_source_url
                },
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req]
            ):
                url = (
                    "/service?service=WMS&version=1.1.1"
                    "&bbox=-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244"
                    "&width=256&height=256&layers=wms_direct_layer&srs=EPSG%3A3857&format=image%2Fpng"
                    "&styles=&request=GetMap&key=123456"
                )
                app.get(url)
