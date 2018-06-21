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

import functools

from io import BytesIO

import pytest

from mapproxy.test.image import is_jpeg, create_tmp_image
from mapproxy.test.http import MockServ
from mapproxy.test.helper import validate_with_xsd
from mapproxy.test.system import SysTest

from mapproxy.test.helper import skip_with_nosetest

skip_with_nosetest()


@pytest.fixture(scope="module")
def config_file():
    return "wmts.yaml"


ns_wmts = {
    "wmts": "http://www.opengis.net/wmts/1.0",
    "ows": "http://www.opengis.net/ows/1.1",
    "xlink": "http://www.w3.org/1999/xlink",
}


def assert_xpath(xml, xpath, expected, namespaces=None):
    assert xml.xpath(xpath, namespaces=namespaces)[0] == expected


assert_xpath_wmts = functools.partial(assert_xpath, namespaces=ns_wmts)


class TestWMTS(SysTest):

    def test_capabilities(self, app):
        resp = app.get("/wmts/myrest/1.0.0/WMTSCapabilities.xml")
        xml = resp.lxml
        assert validate_with_xsd(
            xml, xsd_name="wmts/1.0/wmtsGetCapabilities_response.xsd"
        )
        assert len(xml.xpath("//wmts:Layer", namespaces=ns_wmts)) == 5
        assert (
            len(xml.xpath("//wmts:Contents/wmts:TileMatrixSet", namespaces=ns_wmts))
            == 5
        )

    def test_get_tile(self, app, fixture_cache_data):
        resp = app.get("/wmts/myrest/wms_cache/GLOBAL_MERCATOR/01/0/0.jpeg")
        assert resp.content_type == "image/jpeg"
        data = BytesIO(resp.body)
        assert is_jpeg(data)
        # test without leading 0 in level
        resp = app.get("/wmts/myrest/wms_cache/GLOBAL_MERCATOR/1/0/0.jpeg")
        assert resp.content_type == "image/jpeg"
        data = BytesIO(resp.body)
        assert is_jpeg(data)

    def test_get_tile_flipped_axis(self, app):
        serv = MockServ(port=42423)
        # source is ll, cache/service ul
        serv.expects("/tiles/01/000/000/000/000/000/001.png")
        serv.returns(create_tmp_image((256, 256)))
        with serv:
            resp = app.get("/wmts/myrest/tms_cache_ul/ulgrid/01/0/0.png", status=200)
            assert resp.content_type == "image/png"
            # test without leading 0 in level
            resp = app.get("/wmts/myrest/tms_cache_ul/ulgrid/1/0/0.png", status=200)
            assert resp.content_type == "image/png"

    def test_get_tile_source_error(self, app):
        resp = app.get("/wmts/myrest/tms_cache/GLOBAL_MERCATOR/01/0/0.png", status=500)
        xml = resp.lxml
        assert validate_with_xsd(xml, xsd_name="ows/1.1.0/owsExceptionReport.xsd")
        assert_xpath_wmts(
            xml, "/ows:ExceptionReport/ows:Exception/@exceptionCode", "NoApplicableCode"
        )

    def test_get_tile_out_of_range(self, app):
        resp = app.get(
            "/wmts/myrest/wms_cache/GLOBAL_MERCATOR/01/-1/0.jpeg", status=400
        )
        xml = resp.lxml
        assert resp.content_type == "text/xml"
        assert validate_with_xsd(xml, xsd_name="ows/1.1.0/owsExceptionReport.xsd")
        assert_xpath_wmts(
            xml, "/ows:ExceptionReport/ows:Exception/@exceptionCode", "TileOutOfRange"
        )

    def test_get_tile_invalid_format(self, app):
        url = "/wmts/myrest/wms_cache/GLOBAL_MERCATOR/01/0/0.png"
        self.check_invalid_parameter(app, url)

    def test_get_tile_invalid_layer(self, app):
        url = "/wmts/myrest/unknown/GLOBAL_MERCATOR/01/0/0.jpeg"
        self.check_invalid_parameter(app, url)

    def test_get_tile_invalid_matrixset(self, app):
        url = "/wmts/myrest/wms_cache/unknown/01/0/0.jpeg"
        self.check_invalid_parameter(app, url)

    def check_invalid_parameter(self, app, url):
        resp = app.get(url, status=400)
        xml = resp.lxml
        assert resp.content_type == "text/xml"
        assert validate_with_xsd(xml, xsd_name="ows/1.1.0/owsExceptionReport.xsd")
        assert_xpath_wmts(
            xml,
            "/ows:ExceptionReport/ows:Exception/@exceptionCode",
            "InvalidParameterValue",
        )
