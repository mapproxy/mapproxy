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

import pytest

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.test.system import SysTest
from mapproxy.test.http import mock_httpd
from mapproxy.test.image import create_tmp_image


@pytest.fixture(scope="module")
def config_file():
    return "sld.yaml"


TESTSERVER_ADDRESS = "localhost", 42423


class TestWMS(SysTest):

    @pytest.fixture(scope="class")
    def additional_files(self, base_dir):
        base_dir.join("mysld.xml").write("<sld>")

    def setup_method(self):
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="0,0,10,10",
                width="200",
                height="200",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
                exceptions="xml",
            ),
        )
        self.common_wms_url = (
            "/service?styles=&srs=EPSG%3A4326&version=1.1.1&"
            "bbox=0.0,0.0,10.0,10.0&service=WMS&format=image%2Fpng&request=GetMap"
            "&width=200&height=200"
        )

    def test_sld_url(self, app):
        self.common_map_req.params["layers"] = "sld_url"
        with mock_httpd(
            TESTSERVER_ADDRESS,
            [
                (
                    {
                        "path": self.common_wms_url
                        + "&sld="
                        + quote("http://example.org/sld.xml"),
                        "method": "GET",
                    },
                    {"body": create_tmp_image((200, 200), format="png")},
                )
            ],
        ):
            resp = app.get(self.common_map_req)
            assert resp.content_type == "image/png"

    def test_sld_file(self, app):
        self.common_map_req.params["layers"] = "sld_file"
        with mock_httpd(
            TESTSERVER_ADDRESS,
            [
                (
                    {
                        "path": self.common_wms_url + "&sld_body=" + quote("<sld>"),
                        "method": "GET",
                    },
                    {"body": create_tmp_image((200, 200), format="png")},
                )
            ],
        ):
            resp = app.get(self.common_map_req)
            assert resp.content_type == "image/png"

    def test_sld_body(self, app):
        self.common_map_req.params["layers"] = "sld_body"
        with mock_httpd(
            TESTSERVER_ADDRESS,
            [
                (
                    {
                        "path": self.common_wms_url
                        + "&sld_body="
                        + quote("<sld:StyledLayerDescriptor />"),
                        "method": "POST",
                    },
                    {"body": create_tmp_image((200, 200), format="png")},
                )
            ],
        ):
            resp = app.get(self.common_map_req)
            assert resp.content_type == "image/png"
