# This file is part of the MapProxy project.
# Copyright (C) 2014 Omniscale <http://omniscale.de>
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

from mapproxy.request.wms import WMS111MapRequest, WMS111CapabilitiesRequest
from mapproxy.test.image import is_png, is_transparent
from mapproxy.test.image import tmp_image, assert_colors_equal, img_from_buf
from mapproxy.test.http import mock_httpd

from mapproxy.test.system import SysTest
from mapproxy.test.system.test_wms import bbox_srs_from_boundingbox

import pytest


@pytest.fixture(scope="module")
def config_file():
    return "wms_srs_extent.yaml"


class TestWMSSRSExtentTest(SysTest):

    def setup(self):
        self.common_req = WMS111MapRequest(
            url="/service?", param=dict(service="WMS", version="1.1.1")
        )

    def test_wms_capabilities(self, app):
        req = WMS111CapabilitiesRequest(url="/service?").copy_with_request_params(
            self.common_req
        )
        resp = app.get(req)
        assert resp.content_type == "application/vnd.ogc.wms_xml"
        xml = resp.lxml

        bboxs = xml.xpath("//Layer/Layer[1]/BoundingBox")
        bboxs = dict((e.attrib["SRS"], e) for e in bboxs)

        assert bbox_srs_from_boundingbox(bboxs["EPSG:31467"]) == pytest.approx(
            [2750000.0, 5000000.0, 4250000.0, 6500000.0]
        )
        assert bbox_srs_from_boundingbox(bboxs["EPSG:25832"]) == pytest.approx(
            [0.0, 3500000.0, 1000000.0, 8500000.0]
        )

        assert bbox_srs_from_boundingbox(bboxs["EPSG:3857"]) in (
            # world BBOX is transformed differently depending on PROJ version
            pytest.approx([-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428]),
            pytest.approx([-20037508.3428, -147730762.67, 20037508.3428, 147730762.67]),
        )
        assert bbox_srs_from_boundingbox(bboxs["EPSG:4326"]) == pytest.approx(
            [-180.0, -90.0, 180.0, 90.0]
        )

        # bboxes clipped to coverage
        bboxs = xml.xpath("//Layer/Layer[2]/BoundingBox")
        bboxs = dict((e.attrib["SRS"], e) for e in bboxs)
        assert bbox_srs_from_boundingbox(bboxs["EPSG:31467"]) == pytest.approx(
            [3213331.57335, 5540436.91132, 3571769.72263, 6104110.432],
            3,  # EPSG params changed with proj versions
        )
        assert bbox_srs_from_boundingbox(bboxs["EPSG:25832"]) == pytest.approx(
            [213372.048961, 5538660.64621, 571666.447504, 6102110.74547]
        )

        assert bbox_srs_from_boundingbox(bboxs["EPSG:3857"]) == pytest.approx(
            [556597.453966, 6446275.84102, 1113194.90793, 7361866.11305]
        )
        assert bbox_srs_from_boundingbox(bboxs["EPSG:4326"]) == pytest.approx(
            [5.0, 50.0, 10.0, 55.0]
        )

    def test_out_of_extent(self, app):
        resp = app.get(
            "http://localhost/service?SERVICE=WMS&REQUEST=GetMap"
            "&LAYERS=direct&STYLES="
            "&WIDTH=100&HEIGHT=100&FORMAT=image/png"
            "&BBOX=-10000,0,0,1000&SRS=EPSG:25832"
            "&VERSION=1.1.0&TRANSPARENT=TRUE"
        )
        # empty/transparent response
        assert resp.content_type == "image/png"
        assert is_png(resp.body)
        assert is_transparent(resp.body)

    def test_out_of_extent_bgcolor(self, app):
        resp = app.get(
            "http://localhost/service?SERVICE=WMS&REQUEST=GetMap"
            "&LAYERS=direct&STYLES="
            "&WIDTH=100&HEIGHT=100&FORMAT=image/png"
            "&BBOX=-10000,0,0,1000&SRS=EPSG:25832"
            "&VERSION=1.1.0&TRANSPARENT=FALSE&BGCOLOR=0xff0000"
        )
        # red response
        assert resp.content_type == "image/png"
        assert is_png(resp.body)
        assert_colors_equal(
            img_from_buf(resp.body).convert("RGBA"), [(100 * 100, [255, 0, 0, 255])]
        )

    def test_clipped(self, app):
        with tmp_image((256, 256), format="png", color=(255, 0, 0)) as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=bar&SERVICE=WMS&FORMAT=image%2Fpng"
                    "&REQUEST=GetMap&HEIGHT=100&SRS=EPSG%3A25832&styles="
                    "&VERSION=1.1.1&BBOX=0.0,3500000.0,150.0,3500100.0"
                    "&WIDTH=75"
                },
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
        with mock_httpd(("localhost", 42423), [expected_req]):
            resp = app.get(
                "http://localhost/service?SERVICE=WMS&REQUEST=GetMap"
                "&LAYERS=direct&STYLES="
                "&WIDTH=100&HEIGHT=100&FORMAT=image/png"
                "&BBOX=-50,3500000,150,3500100&SRS=EPSG:25832"
                "&VERSION=1.1.0&TRANSPARENT=TRUE"
            )
            assert resp.content_type == "image/png"
            assert is_png(resp.body)
            colors = sorted(img_from_buf(resp.body).convert("RGBA").getcolors())
            # quarter is clipped, check if it's transparent
            assert colors[0][0] == (25 * 100)
            assert colors[0][1][3] == 0
            assert colors[1] == (75 * 100, (255, 0, 0, 255))

    def test_clipped_bgcolor(self, app):
        with tmp_image((256, 256), format="png", color=(255, 0, 0)) as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=bar&SERVICE=WMS&FORMAT=image%2Fpng"
                    "&REQUEST=GetMap&HEIGHT=100&SRS=EPSG%3A25832&styles="
                    "&VERSION=1.1.1&BBOX=0.0,3500000.0,100.0,3500100.0"
                    "&WIDTH=50"
                },
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
        with mock_httpd(("localhost", 42423), [expected_req]):
            resp = app.get(
                "http://localhost/service?SERVICE=WMS&REQUEST=GetMap"
                "&LAYERS=direct&STYLES="
                "&WIDTH=100&HEIGHT=100&FORMAT=image/png"
                "&BBOX=-100,3500000,100,3500100&SRS=EPSG:25832"
                "&VERSION=1.1.0&TRANSPARENT=FALSE&BGCOLOR=0x00ff00"
            )
            assert resp.content_type == "image/png"
            assert is_png(resp.body)
            assert_colors_equal(
                img_from_buf(resp.body).convert("RGBA"),
                [(50 * 100, [255, 0, 0, 255]), (50 * 100, [0, 255, 0, 255])],
            )
