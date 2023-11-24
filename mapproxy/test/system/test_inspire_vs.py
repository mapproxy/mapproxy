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

from __future__ import print_function, division

import functools

import pytest

from mapproxy.request.wms import WMS130CapabilitiesRequest
from mapproxy.test.helper import validate_with_xsd
from mapproxy.test.system import SysTest


def is_inpire_vs_capa(xml):
    return validate_with_xsd(xml, xsd_name="inspire/inspire_vs/1.0/inspire_vs.xsd")


def bbox_srs_from_boundingbox(bbox_elem):
    return [
        float(bbox_elem.attrib["minx"]),
        float(bbox_elem.attrib["miny"]),
        float(bbox_elem.attrib["maxx"]),
        float(bbox_elem.attrib["maxy"]),
    ]


ns130 = {
    "wms": "http://www.opengis.net/wms",
    "ogc": "http://www.opengis.net/ogc",
    "sld": "http://www.opengis.net/sld",
    "xlink": "http://www.w3.org/1999/xlink",
    "ic": "http://inspire.ec.europa.eu/schemas/common/1.0",
    "iv": "http://inspire.ec.europa.eu/schemas/inspire_vs/1.0",
}


def assert_xpath(xml, xpath, expected, namespaces=None):
    elems = xml.xpath(xpath, namespaces=namespaces)
    assert len(elems) == 1, elems
    assert elems[0] == expected


def xpath_130(xml, xpath):
    return xml.xpath(xpath, namespaces=ns130)


assert_xpath_wms130 = functools.partial(assert_xpath, namespaces=ns130)


class TestLinkedMD(SysTest):

    @pytest.fixture(scope="class")
    def config_file(self):
        return "inspire.yaml"

    def test_wms_capabilities(self, app):
        req = WMS130CapabilitiesRequest(url="/service?")
        resp = app.get(req)
        assert resp.content_type == "text/xml"
        print(resp.body)
        xml = resp.lxml
        assert is_inpire_vs_capa(xml)

        ext_cap = xpath_130(
            xml, "/wms:WMS_Capabilities/wms:Capability/iv:ExtendedCapabilities"
        )

        assert len(ext_cap) == 1, ext_cap
        ext_cap = ext_cap[0]

        assert_xpath_wms130(
            ext_cap, "./ic:MetadataUrl/ic:URL/text()", u"http://example.org/metadata"
        )
        assert_xpath_wms130(
            ext_cap,
            "./ic:MetadataUrl/ic:MediaType/text()",
            u"application/vnd.iso.19139+xml",
        )

        assert_xpath_wms130(
            ext_cap,
            "./ic:SupportedLanguages/ic:DefaultLanguage/ic:Language/text()",
            u"eng",
        )
        assert_xpath_wms130(ext_cap, "./ic:ResponseLanguage/ic:Language/text()", u"eng")

        # test for extended layer metadata
        assert_xpath_wms130(
            xml,
            "/wms:WMS_Capabilities/wms:Capability/wms:Layer/wms:Attribution/wms:Title/text()",
            u"My attribution title",
        )

        layer_names = set(xml.xpath("//wms:Layer/wms:Name/text()", namespaces=ns130))
        expected_names = set(["inspire_example"])
        assert layer_names == expected_names


class TestFullMD(SysTest):

    @pytest.fixture(scope="class")
    def config_file(self):
        return "inspire_full.yaml"

    def test_wms_capabilities(self, app):
        req = WMS130CapabilitiesRequest(url="/service?")
        resp = app.get(req)
        assert resp.content_type == "text/xml"
        print(resp.body)

        xml = resp.lxml
        assert is_inpire_vs_capa(xml)

        ext_cap = xpath_130(
            xml, "/wms:WMS_Capabilities/wms:Capability/iv:ExtendedCapabilities"
        )

        assert len(ext_cap) == 1, ext_cap
        ext_cap = ext_cap[0]

        assert_xpath_wms130(
            ext_cap,
            "./ic:ResourceLocator/ic:URL/text()",
            u"http://example.org/metadata",
        )
        assert_xpath_wms130(
            ext_cap,
            "./ic:ResourceLocator/ic:MediaType/text()",
            u"application/vnd.iso.19139+xml",
        )

        assert_xpath_wms130(
            ext_cap,
            "./ic:Keyword/ic:OriginatingControlledVocabulary/ic:Title/text()",
            u"GEMET - INSPIRE themes",
        )

        assert_xpath_wms130(
            ext_cap,
            "./ic:SupportedLanguages/ic:DefaultLanguage/ic:Language/text()",
            u"eng",
        )
        assert_xpath_wms130(ext_cap, "./ic:ResponseLanguage/ic:Language/text()", u"eng")

        # check dates from string and datetime
        assert_xpath_wms130(
            ext_cap, "./ic:TemporalReference/ic:DateOfCreation/text()", u"2015-05-01"
        )
        assert_xpath_wms130(ext_cap, "./ic:MetadataDate/text()", u"2015-07-23")

        # test for extended layer metadata
        assert_xpath_wms130(
            xml,
            "/wms:WMS_Capabilities/wms:Capability/wms:Layer/wms:Attribution/wms:Title/text()",
            u"My attribution title",
        )

        layer_names = set(xml.xpath("//wms:Layer/wms:Name/text()", namespaces=ns130))
        expected_names = set(["inspire_example"])
        assert layer_names == expected_names
