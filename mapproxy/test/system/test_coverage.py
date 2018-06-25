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
from mapproxy.test.image import is_png, tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "coverage.yaml"


class TestCoverageWMS(SysTest):

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
            ),
        )

    def test_capababilities(self, app):
        resp = app.get("/service?request=GetCapabilities&service=WMS&version=1.1.1")
        xml = resp.lxml
        # First: combined root, second: wms_cache, third: tms_cache, last: seed_only
        assert xml.xpath("//LatLonBoundingBox/@minx") == ["10", "10", "12", "14"]
        assert xml.xpath("//LatLonBoundingBox/@miny") == ["10", "15", "10", "13"]
        assert xml.xpath("//LatLonBoundingBox/@maxx") == ["35", "30", "35", "24"]
        assert xml.xpath("//LatLonBoundingBox/@maxy") == ["31", "31", "30", "23"]

    def test_get_map_outside(self, app):
        self.common_map_req.params.bbox = -90, 0, 0, 90
        self.common_map_req.params["bgcolor"] = "0xff0005"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        assert img.mode == "RGB"
        assert img.getcolors() == [(200 * 200, (255, 0, 5))]

    def test_get_map_outside_transparent(self, app):
        self.common_map_req.params.bbox = -90, 0, 0, 90
        self.common_map_req.params.transparent = True
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        assert img.mode == "RGBA"
        assert img.getcolors()[0][0] == 200 * 200
        assert img.getcolors()[0][1][3] == 0  # transparent

    def test_get_map_intersection(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=91&SRS=EPSG%3A4326&styles="
                    "&VERSION=1.1.1&BBOX=10,15,30,31"
                    "&WIDTH=114"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                self.common_map_req.params.bbox = 0, 0, 40, 40
                self.common_map_req.params.transparent = True
                resp = app.get(self.common_map_req)
                assert resp.content_type == "image/png"
                data = BytesIO(resp.body)
                assert is_png(data)
                assert Image.open(data).mode == "RGBA"
        assert cache_dir.join(
            "wms_cache_EPSG4326/03/000/000/004/000/000/002.jpeg"
        ).check()


class TestCoverageTMS(SysTest):

    def test_get_tile_intersections(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=25&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=1113194.90793,1689200.13961,3339584.7238,3632749.14338"
                    "&WIDTH=28"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tms/1.0.0/wms_cache/0/1/1.jpeg")
                assert resp.content_type == "image/jpeg"
        cache_dir.join("wms_cache_EPSG900913/01/000/000/001/000/000/001.jpeg").check()

    def test_get_tile_intersection_tms(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {"path": r"/tms/1.0.0/foo/1/1/1.jpeg"},
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tms/1.0.0/tms_cache/0/1/1.jpeg")
                assert resp.content_type == "image/jpeg"
        cache_dir.join("tms_cache_EPSG900913/01/000/000/001/000/000/001.jpeg").check()
