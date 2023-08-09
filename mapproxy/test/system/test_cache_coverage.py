# -:- encoding: utf8 -:-
# This file is part of the MapProxy project.
# Copyright (C) 2015 Omniscale <http://omniscale.de>
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

from mapproxy.request.wmts import WMTS100CapabilitiesRequest
from mapproxy.request.wms import WMS111CapabilitiesRequest
from mapproxy.test.helper import validate_with_xsd
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "cache_coverage.yaml"


ns_wmts = {
    "wmts": "http://www.opengis.net/wmts/1.0",
    "ows": "http://www.opengis.net/ows/1.1",
    "xlink": "http://www.w3.org/1999/xlink",
}


class TestCacheCoverage(SysTest):

    def setup(self):
        self.common_cap_req = WMTS100CapabilitiesRequest(
            url="/service?",
            param=dict(service="WMTS", version="1.0.0", request="GetCapabilities"),
        )

    def test_tms_capabilities_coverage(self, app):
        resp = app.get("/tms/1.0.0/")
        assert "http://localhost/tms/1.0.0/coverage_cache/EPSG4326" in resp
        xml = resp.lxml
        assert xml.xpath("count(//TileMap)") == 1
        
        resp = app.get("/tms/1.0.0/coverage_cache/EPSG4326")
        xml = resp.lxml
        
        assert xml.xpath("//TileMap/BoundingBox/@minx") == ["-50"]
        assert xml.xpath("//TileMap/BoundingBox/@miny") == ["-50"]
        assert xml.xpath("//TileMap/BoundingBox/@maxx") == ["50"]
        assert xml.xpath("//TileMap/BoundingBox/@maxy") == ["50"]

    def test_wmts_capabilities_coverage(self, app):
        req = str(self.common_cap_req)
        resp = app.get(req)
        assert resp.content_type == "application/xml"
        xml = resp.lxml

        assert validate_with_xsd(
            xml, xsd_name="wmts/1.0/wmtsGetCapabilities_response.xsd"
        )
        
        assert set(
            xml.xpath(
                "//wmts:Contents/wmts:Layer/ows:WGS84BoundingBox/ows:LowerCorner/text()",
                namespaces=ns_wmts,
            )
        ) == set(["-50 -50"])
        
        assert set(
            xml.xpath(
                "//wmts:Contents/wmts:Layer/ows:WGS84BoundingBox/ows:UpperCorner/text()",
                namespaces=ns_wmts,
            )
        ) == set(["50 50"])

    def test_wms_capabilities_coverage(self, app):
        req = WMS111CapabilitiesRequest(url="/service?")
        resp = app.get(req)
        assert resp.content_type == "application/vnd.ogc.wms_xml"
        xml = resp.lxml

        assert xml.xpath("//Layer/LatLonBoundingBox/@minx") == ["-50"]
        assert xml.xpath("//Layer/LatLonBoundingBox/@miny") == ["-50"]
        assert xml.xpath("//Layer/LatLonBoundingBox/@maxx") == ["50"]
        assert xml.xpath("//Layer/LatLonBoundingBox/@maxy") == ["50"]
