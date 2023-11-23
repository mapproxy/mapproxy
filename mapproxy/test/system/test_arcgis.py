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

from mapproxy.request.wms import WMS111FeatureInfoRequest
from mapproxy.test.image import is_png, create_tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "arcgis.yaml"


transp = create_tmp_image((512, 512), mode="RGBA", color=(0, 0, 0, 0))


class TestArcgisSource(SysTest):

    def setup_method(self):
        self.common_fi_req = WMS111FeatureInfoRequest(
            url="/service?",
            param=dict(
                x="10",
                y="20",
                width="200",
                height="200",
                layers="app2_with_layers_fi_layer",
                format="image/png",
                query_layers="app2_with_layers_fi_layer",
                styles="",
                bbox="1000,400,2000,1400",
                srs="EPSG:3857",
                info_format="application/json",
            ),
        )

    def test_get_tile(self, app):
        expected_req = [
            (
                {
                    "path": "/arcgis/rest/services/ExampleLayer/ImageServer/exportImage?f=image&format=png&imageSR=900913&bboxSR=900913&bbox=-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244&size=512,512"
                },
                {"body": transp, "headers": {"content-type": "image/png"}},
            )
        ]

        with mock_httpd(
            ("localhost", 42423), expected_req, bbox_aware_query_comparator=True
        ):
            resp = app.get("/tms/1.0.0/app2_layer/0/0/1.png")
            assert resp.content_type == "image/png"
            assert resp.content_length == len(resp.body)
            data = BytesIO(resp.body)
            assert is_png(data)

    def test_get_tile_with_layer(self, app):
        expected_req = [
            (
                {
                    "path": "/arcgis/rest/services/ExampleLayer/MapServer/export?f=image&format=png&layers=show:0,1&imageSR=900913&bboxSR=900913&bbox=-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244&size=512,512"
                },
                {"body": transp, "headers": {"content-type": "image/png"}},
            )
        ]

        with mock_httpd(
            ("localhost", 42423), expected_req, bbox_aware_query_comparator=True
        ):
            resp = app.get("/tms/1.0.0/app2_with_layers_layer/0/0/1.png")
            assert resp.content_type == "image/png"
            assert resp.content_length == len(resp.body)
            data = BytesIO(resp.body)
            assert is_png(data)

    def test_get_tile_from_missing_arcgis_layer(self, app):
        expected_req = [
            (
                {
                    "path": "/arcgis/rest/services/NonExistentLayer/ImageServer/exportImage?f=image&format=png&imageSR=900913&bboxSR=900913&bbox=-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244&size=512,512"
                },
                {"body": b"", "status": 400},
            )
        ]

        with mock_httpd(
            ("localhost", 42423), expected_req, bbox_aware_query_comparator=True
        ):
            resp = app.get("/tms/1.0.0/app2_wrong_url_layer/0/0/1.png", status=500)
            assert resp.status_code == 500

    def test_identify(self, app):
        expected_req = [
            (
                {
                    "path": "/arcgis/rest/services/ExampleLayer/MapServer/identify?f=json&"
                    "geometry=1050.000000,1300.000000&returnGeometry=true&imageDisplay=200,200,96"
                    "&mapExtent=1000.0,400.0,2000.0,1400.0&layers=show:1,2,3"
                    "&tolerance=10&geometryType=esriGeometryPoint&sr=3857"
                },
                {
                    "body": b'{"results": []}',
                    "headers": {"content-type": "application/json"},
                },
            )
        ]

        with mock_httpd(
            ("localhost", 42423), expected_req, bbox_aware_query_comparator=True
        ):
            resp = app.get(self.common_fi_req)
            assert resp.content_type == "application/json"
            assert resp.content_length == len(resp.body)
            assert resp.body == b'{"results": []}'

    def test_transformed_identify(self, app):
        expected_req = [
            (
                {
                    "path": "/arcgis/rest/services/ExampleLayer/MapServer/identify?f=json&"
                    "geometry=573295.377585,6927820.884193&returnGeometry=true&imageDisplay=200,321,96"
                    "&mapExtent=556597.453966,6446275.84102,890555.926346,6982997.92039&layers=show:1,2,3"
                    "&tolerance=10&geometryType=esriGeometryPoint&sr=3857"
                },
                {
                    "body": b'{"results": []}',
                    "headers": {"content-type": "application/json"},
                },
            )
        ]

        with mock_httpd(("localhost", 42423), expected_req):
            self.common_fi_req.params.bbox = "5,50,8,53"
            self.common_fi_req.params.srs = "EPSG:4326"
            resp = app.get(self.common_fi_req)
            assert resp.content_type == "application/json"
            assert resp.content_length == len(resp.body)
            assert resp.body == b'{"results": []}'
