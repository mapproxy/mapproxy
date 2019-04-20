# -:- encoding: utf8 -:-
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

import re
import functools

from io import BytesIO

import pytest

from mapproxy.request.wmts import (
    WMTS100TileRequest,
    WMTS100FeatureInfoRequest,
    WMTS100CapabilitiesRequest,
)
from mapproxy.test.image import is_jpeg, create_tmp_image
from mapproxy.test.http import MockServ
from mapproxy.test.helper import validate_with_xsd
from mapproxy.test.system import SysTest


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


@pytest.fixture
def fi_req():
    return WMTS100FeatureInfoRequest(
        url="/service?",
        param=dict(
            service="WMTS",
            version="1.0.0",
            tilerow="0",
            tilecol="0",
            tilematrix="00",
            tilematrixset="GLOBAL_MERCATOR",
            layer="wms_cache",
            format="image/png",
            infoformat="application/json",
            style="",
            request="GetFeatureInfo",
            i="17",
            j="27"
        ),
    )

@pytest.fixture
def fi_req_with_featurecount():
    return WMTS100FeatureInfoRequest(
        url="/service?",
        param=dict(
            service="WMTS",
            version="1.0.0",
            tilerow="0",
            tilecol="0",
            tilematrix="00",
            tilematrixset="GLOBAL_MERCATOR",
            layer="wms_cache",
            format="image/png",
            infoformat="application/json",
            style="",
            request="GetFeatureInfo",
            i="17",
            j="27",
            feature_count="5"
        ),
    )


class TestWMTS(SysTest):

    def setup(self):
        self.common_cap_req = WMTS100CapabilitiesRequest(
            url="/service?",
            param=dict(service="WMTS", version="1.0.0", request="GetCapabilities"),
        )
        self.common_tile_req = WMTS100TileRequest(
            url="/service?",
            param=dict(
                service="WMTS",
                version="1.0.0",
                tilerow="0",
                tilecol="0",
                tilematrix="01",
                tilematrixset="GLOBAL_MERCATOR",
                layer="wms_cache",
                format="image/jpeg",
                style="",
                request="GetTile",
            ),
        )

    def test_endpoints(self, app):
        for endpoint in ("service", "ows"):
            req = WMTS100CapabilitiesRequest(
                url="/%s?" % endpoint
            ).copy_with_request_params(self.common_cap_req)
            resp = app.get(req)
            assert resp.content_type == "application/xml"
            xml = resp.lxml
            assert validate_with_xsd(
                xml, xsd_name="wmts/1.0/wmtsGetCapabilities_response.xsd"
            )

    def test_capabilities(self, app):
        req = str(self.common_cap_req)
        resp = app.get(req)
        assert resp.content_type == "application/xml"
        xml = resp.lxml
        assert validate_with_xsd(
            xml, xsd_name="wmts/1.0/wmtsGetCapabilities_response.xsd"
        )
        assert xml.xpath("//wmts:Layer/ows:Identifier/text()", namespaces=ns_wmts) == [
            "wms_cache",
            "wms_cache_multi",
            "tms_cache",
            "tms_cache_ul",
            "gk3_cache",
        ]
        assert (
            len(xml.xpath("//wmts:Contents/wmts:TileMatrixSet", namespaces=ns_wmts))
            == 5
        )

        # check InfoFormat for queryable layers
        for layer in xml.xpath("//wmts:Layer", namespaces=ns_wmts):
            if layer.findtext("ows:Identifier", namespaces=ns_wmts) in (
                "wms_cache",
                "wms_cache_multi",
                "gk3_cache",
                "tms_cache",
            ):
                assert layer.xpath("wmts:InfoFormat/text()", namespaces=ns_wmts) == [
                    "application/gml+xml; version=3.1",
                    "application/json",
                ]
            else:
                assert layer.xpath("wmts:InfoFormat/text()", namespaces=ns_wmts) == []

        goog_matrixset = xml.xpath(
            '//wmts:Contents/wmts:TileMatrixSet[./ows:Identifier/text()="GoogleMapsCompatible"]',
            namespaces=ns_wmts,
        )[0]
        assert (
            goog_matrixset.findtext("ows:Identifier", namespaces=ns_wmts)
            == "GoogleMapsCompatible"
        )
        # top left corner: min X first then max Y
        assert re.match(
            r"-20037508\.\d+ 20037508\.\d+",
            goog_matrixset.findtext(
                "./wmts:TileMatrix[1]/wmts:TopLeftCorner", namespaces=ns_wmts
            ),
        )

        gk_matrixset = xml.xpath(
            '//wmts:Contents/wmts:TileMatrixSet[./ows:Identifier/text()="gk3"]',
            namespaces=ns_wmts,
        )[0]
        assert gk_matrixset.findtext("ows:Identifier", namespaces=ns_wmts) == "gk3"
        # Gauß-Krüger uses "reverse" axis order -> top left corner: max Y first then min X
        assert re.match(
            "6000000.0+ 3000000.0+",
            gk_matrixset.findtext(
                "./wmts:TileMatrix[1]/wmts:TopLeftCorner", namespaces=ns_wmts
            ),
        )

    def test_get_tile(self, app, fixture_cache_data):
        resp = app.get(str(self.common_tile_req))
        assert resp.content_type == "image/jpeg"
        data = BytesIO(resp.body)
        assert is_jpeg(data)

        # test with integer tilematrix
        url = str(self.common_tile_req).replace("=01", "=1")
        resp = app.get(url)
        assert resp.content_type == "image/jpeg"
        data = BytesIO(resp.body)
        assert is_jpeg(data)

    def test_get_tile_flipped_axis(self, app, cache_dir, fixture_cache_data):
        # test default tile lock directory
        tiles_lock_dir = cache_dir.join("tile_locks")
        assert not tiles_lock_dir.check()

        self.common_tile_req.params["layer"] = "tms_cache_ul"
        self.common_tile_req.params["tilematrixset"] = "ulgrid"
        self.common_tile_req.params["format"] = "image/png"
        self.common_tile_req.tile = (0, 0, "01")
        serv = MockServ(port=42423)
        # source is ll, cache/service ul
        serv.expects("/tiles/01/000/000/000/000/000/001.png")
        serv.returns(create_tmp_image((256, 256)))
        with serv:
            resp = app.get(str(self.common_tile_req), status=200)
            assert resp.content_type == "image/png"

        # test default tile lock directory was created
        assert tiles_lock_dir.check()

    def test_get_tile_source_error(self, app):
        self.common_tile_req.params["layer"] = "tms_cache"
        self.common_tile_req.params["format"] = "image/png"
        resp = app.get(str(self.common_tile_req), status=500)
        xml = resp.lxml
        assert validate_with_xsd(xml, xsd_name="ows/1.1.0/owsExceptionReport.xsd")
        assert_xpath_wmts(
            xml, "/ows:ExceptionReport/ows:Exception/@exceptionCode", "NoApplicableCode"
        )

    def test_get_tile_out_of_range(self, app):
        self.common_tile_req.params.coord = -1, 1, 1
        resp = app.get(str(self.common_tile_req), status=400)
        xml = resp.lxml
        assert resp.content_type == "text/xml"
        assert validate_with_xsd(xml, xsd_name="ows/1.1.0/owsExceptionReport.xsd")
        assert_xpath_wmts(
            xml, "/ows:ExceptionReport/ows:Exception/@exceptionCode", "TileOutOfRange"
        )

    def test_get_tile_invalid_format(self, app):
        self.common_tile_req.params["format"] = "image/png"
        self.check_invalid_parameter(app)

    def test_get_tile_invalid_layer(self, app):
        self.common_tile_req.params["layer"] = "unknown"
        self.check_invalid_parameter(app)

    def test_get_tile_invalid_matrixset(self, app):
        self.common_tile_req.params["tilematrixset"] = "unknown"
        self.check_invalid_parameter(app)

    def check_invalid_parameter(self, app):
        resp = app.get(str(self.common_tile_req), status=400)
        xml = resp.lxml
        assert resp.content_type == "text/xml"
        assert validate_with_xsd(xml, xsd_name="ows/1.1.0/owsExceptionReport.xsd")
        assert_xpath_wmts(
            xml,
            "/ows:ExceptionReport/ows:Exception/@exceptionCode",
            "InvalidParameterValue",
        )

    def test_getfeatureinfo(self, app, fi_req):
        serv = MockServ(port=42423)
        serv.expects(
            "/service?layers=foo,bar"
            + "&bbox=-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244"
            + "&width=256&height=256&x=17&y=27&query_layers=foo,bar&format=image%2Fpng&srs=EPSG%3A900913"
            + "&request=GetFeatureInfo&version=1.1.1&service=WMS&styles=&info_format=application/json"
        )
        serv.returns(b'{"data": 43}')
        with serv:
            resp = app.get(str(fi_req), status=200)
            assert resp.content_type == "application/json"


    def test_getfeatureinfo_coverage(self, app, fi_req):
        fi_req.params['layer'] = 'tms_cache'
        fi_req.params['i'] = '250'
        fi_req.params['j'] = '50'
        resp = app.get(str(fi_req), status=200)
        assert resp.content_type == "application/json"

        fi_req.params['i'] = '150'
        serv = MockServ(port=42423)
        serv.expects(
            "/service?layers=fi"
            + "&bbox=-20037508.3428,-20037508.3428,20037508.3428,20037508.3428"
            + "&width=256&height=256&x=150&y=50&query_layers=fi&format=image%2Fpng&srs=EPSG%3A900913"
            + "&request=GetFeatureInfo&version=1.1.1&service=WMS&styles=&info_format=application/json"
        )
        serv.returns(b'{"data": 43}')
        with serv:
            resp = app.get(str(fi_req), status=200)
            assert resp.content_type == "application/json"

    def test_getfeatureinfo_featurecount(self, app, fi_req_with_featurecount):
        serv = MockServ(port=42423)
        serv.expects(
            "/service?layers=foo,bar"
            + "&bbox=-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244"
            + "&width=256&height=256&x=17&y=27&query_layers=foo,bar&format=image%2Fpng&srs=EPSG%3A900913"
            + "&request=GetFeatureInfo&version=1.1.1&service=WMS&styles=&info_format=application/json&feature_count=5"
        )
        serv.returns(b'{"data": 43}')
        with serv:
            resp = app.get(str(fi_req_with_featurecount), status=200)
            assert resp.content_type == "application/json"

    def test_getfeatureinfo_xml(self, app, fi_req):
        fi_req.params["infoformat"] = "application/gml+xml; version=3.1"
        serv = MockServ(port=42423)
        serv.expects(
            "/service?layers=foo,bar"
            + "&bbox=-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244"
            + "&width=256&height=256&x=17&y=27&query_layers=foo,bar&format=image%2Fpng&srs=EPSG%3A900913"
            + "&request=GetFeatureInfo&version=1.1.1&service=WMS&styles=&info_format=application/gml%2bxml%3b%20version=3.1"
        )
        serv.returns(b"<root />")
        with serv:
            resp = app.get(str(fi_req), status=200)
            assert resp.headers["Content-type"] == "application/gml+xml; version=3.1"
