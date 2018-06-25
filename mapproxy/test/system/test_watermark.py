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

from io import BytesIO

import pytest

from mapproxy.compat.image import Image
from mapproxy.request.wms import WMS111MapRequest
from mapproxy.test.http import mock_httpd
from mapproxy.test.image import tmp_image
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "watermark.yaml"


class TestWatermark(SysTest):

    def setup(self):
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-180,0,0,80",
                width="200",
                height="200",
                layers="watermark",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
            ),
        )

    def test_watermark_tile(self, app):
        with tmp_image((256, 256), format="png", color=(0, 0, 0)) as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=blank&SERVICE=WMS&FORMAT=image%2Fpng"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&styles="
                    "&VERSION=1.1.1&BBOX=-180.0,-90.0,0.0,90.0"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                resp = app.get("/tms/1.0.0/watermark/EPSG4326/0/0/0.png")
                assert resp.content_type == "image/png"
                img = Image.open(BytesIO(resp.body))
                colors = img.getcolors()
                assert len(colors) >= 2
                assert sorted(colors)[-1][1] == (0, 0, 0)

    def test_transparent_watermark_tile(self, app):
        with tmp_image(
            (256, 256), format="png", color=(0, 0, 0, 0), mode="RGBA"
        ) as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=blank&SERVICE=WMS&FORMAT=image%2Fpng"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&styles="
                    "&VERSION=1.1.1&BBOX=-180.0,-90.0,0.0,90.0"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                resp = app.get("/tms/1.0.0/watermark_transp/EPSG4326/0/0/0.png")
                assert resp.content_type == "image/png"
                img = Image.open(BytesIO(resp.body))
                colors = img.getcolors()
                assert len(colors) >= 2
                assert sorted(colors)[-1][1] == (0, 0, 0, 0)
