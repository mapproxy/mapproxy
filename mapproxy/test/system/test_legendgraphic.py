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

from __future__ import with_statement, division
from io import BytesIO

from mapproxy.compat.image import Image

from mapproxy.request.wms import (
    WMS111MapRequest, WMS111CapabilitiesRequest, WMS130CapabilitiesRequest,
    WMS111LegendGraphicRequest, WMS130LegendGraphicRequest
)

from mapproxy.test.system import module_setup, module_teardown, make_base_config, SystemTest
from mapproxy.test.image import is_png, tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.helper import validate_with_dtd, validate_with_xsd
from mapproxy.test.system.test_wms import is_111_capa, eq_xpath_wms130, ns130
from nose.tools import eq_

test_config = {}

def setup_module():
    module_setup(test_config, 'legendgraphic.yaml', with_cache_data=False)

def teardown_module():
    module_teardown(test_config)

base_config = make_base_config(test_config)


def is_130_capa(xml):
    return validate_with_xsd(xml, xsd_name='sld/1.1.0/sld_capabilities.xsd')


class TestWMS(SystemTest):
    config = test_config
    def setup(self):
        SystemTest.setup(self)
        self.common_req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
             version='1.1.1'))
        self.common_lg_req_111 = WMS111LegendGraphicRequest(url='/service?',
            param=dict(format='image/png', layer='wms_legend', sld_version='1.1.0'))
        self.common_lg_req_130 = WMS130LegendGraphicRequest(url='/service?',
            param=dict(format='image/png', layer='wms_legend', sld_version='1.1.0'))

    #test_00, test_01, test_02 need to run first in order to run the other tests properly
    def test_00_get_legendgraphic_multiple_sources_111(self):
        self.common_lg_req_111.params['layer'] = 'wms_mult_sources'
        with tmp_image((256, 256), format='png') as img:
            img_data = img.read()
            expected_req1 = ({'path': r'/service?LAYER=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                      '&REQUEST=GetLegendGraphic&'
                                      '&VERSION=1.1.1&SLD_VERSION=1.1.0'},
                             {'body': img_data, 'headers': {'content-type': 'image/png'}})
            expected_req2 = ({'path': r'/service?LAYER=bar&SERVICE=WMS&FORMAT=image%2Fpng'
                                      '&REQUEST=GetLegendGraphic&'
                                      '&VERSION=1.1.1&SLD_VERSION=1.1.0'},
                             {'body': img_data, 'headers': {'content-type': 'image/png'}})
            expected_req3 = ({'path': r'/service?LAYER=spam&SERVICE=WMS&FORMAT=image%2Fpng'
                                      '&REQUEST=GetLegendGraphic&'
                                      '&VERSION=1.1.1&SLD_VERSION=1.1.0'},
                            {'body': img_data, 'headers': {'content-type': 'image/png'}})
            with mock_httpd(('localhost', 42423), [expected_req1, expected_req2, expected_req3]):
                resp = self.app.get(self.common_lg_req_111)
                eq_(resp.content_type, 'image/png')
                data = BytesIO(resp.body)
                assert is_png(data)
                assert Image.open(data).size == (256,768)

    def test_01_get_legendgraphic_source_static_url(self):
        self.common_lg_req_111.params['layer'] = 'wms_source_static_url'
        with tmp_image((256, 256), format='png') as img:
            img_data = img.read()
            expected_req1 = ({'path': r'/staticlegend_source.png'},
                             {'body': img_data, 'headers': {'content-type': 'image/png'}})
            with mock_httpd(('localhost', 42423), [expected_req1]):
                resp = self.app.get(self.common_lg_req_111)
                eq_(resp.content_type, 'image/png')
                data = BytesIO(resp.body)
                assert is_png(data)
                assert Image.open(data).size == (256,256)

    def test_02_get_legendgraphic_layer_static_url(self):
        self.common_lg_req_111.params['layer'] = 'wms_layer_static_url'
        with tmp_image((256, 256), format='png') as img:
            img_data = img.read()
            expected_req1 = ({'path': r'/staticlegend_layer.png'},
                             {'body': img_data, 'headers': {'content-type': 'image/png'}})
            with mock_httpd(('localhost', 42423), [expected_req1]):
                resp = self.app.get(self.common_lg_req_111)
                eq_(resp.content_type, 'image/png')
                data = BytesIO(resp.body)
                assert is_png(data)
                assert Image.open(data).size == (256,256)

    def test_capabilities_111(self):
        req = WMS111CapabilitiesRequest(url='/service?').copy_with_request_params(self.common_req)
        resp = self.app.get(req)
        xml = resp.lxml
        eq_(xml.xpath('//Request/GetLegendGraphic')[0].tag, 'GetLegendGraphic')
        legend_sizes = (xml.xpath('//Layer/Style/LegendURL/@width'),
                        xml.xpath('//Layer/Style/LegendURL/@height'))
        assert legend_sizes == (['256', '256', '256', '256'],['512', '768', '256', '256'])
        layer_urls = xml.xpath('//Layer/Style/LegendURL/OnlineResource/@xlink:href',
                         namespaces=ns130)
        for layer_url in layer_urls:
            assert layer_url.startswith('http://')
            assert 'GetLegendGraphic' in layer_url
        assert is_111_capa(xml)

    def test_capabilities_130(self):
        req = WMS130CapabilitiesRequest(url='/service?').copy_with_request_params(self.common_req)
        resp = self.app.get(req)
        xml = resp.lxml
        eq_(xml.xpath('//wms:Request/sld:GetLegendGraphic', namespaces=ns130)[0].tag,
                      '{%s}GetLegendGraphic'%(ns130['sld']))
        layer_urls = xml.xpath('//Layer/Style/LegendURL/OnlineResource/@xlink:href',
                         namespaces=ns130)
        for layer_url in layer_urls:
            assert layer_url.startswith('http://')
            assert 'GetLegendGraphic' in layer_url
        assert is_130_capa(xml)

    def test_get_legendgraphic_111(self):
        self.common_lg_req_111.params['scale'] = '5.0'
        with tmp_image((256, 256), format='png') as img:
            img_data = img.read()
            expected_req1 = ({'path': r'/service?LAYER=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                      '&REQUEST=GetLegendGraphic&SCALE=5.0&'
                                      '&VERSION=1.1.1&SLD_VERSION=1.1.0'},
                             {'body': img_data, 'headers': {'content-type': 'image/png'}})
            expected_req2 = ({'path': r'/service?LAYER=bar&SERVICE=WMS&FORMAT=image%2Fpng'
                                      '&REQUEST=GetLegendGraphic&SCALE=5.0&'
                                      '&VERSION=1.1.1&SLD_VERSION=1.1.0'},
                             {'body': img_data, 'headers': {'content-type': 'image/png'}})
            with mock_httpd(('localhost', 42423), [expected_req1, expected_req2]):
                resp = self.app.get(self.common_lg_req_111)
                eq_(resp.content_type, 'image/png')
                data = BytesIO(resp.body)
                assert is_png(data)
                assert Image.open(data).size == (256,512)

    def test_get_legendgraphic_no_legend_111(self):
        self.common_lg_req_111.params['layer'] = 'wms_no_legend'
        resp = self.app.get(self.common_lg_req_111)
        eq_(resp.content_type, 'application/vnd.ogc.se_xml')
        xml = resp.lxml
        assert 'wms_no_legend has no legend graphic' in xml.xpath('//ServiceException/text()')[0]
        assert validate_with_dtd(xml, 'wms/1.1.1/exception_1_1_1.dtd')

    def test_get_legendgraphic_missing_params_111(self):
        req = str(self.common_lg_req_111).replace('sld_version', 'invalid').replace('format', 'invalid')
        resp = self.app.get(req)
        eq_(resp.content_type, 'application/vnd.ogc.se_xml')
        xml = resp.lxml
        assert 'missing parameters' in xml.xpath('//ServiceException/text()')[0]
        assert validate_with_dtd(xml, 'wms/1.1.1/exception_1_1_1.dtd')

    def test_get_legendgraphic_invalid_sld_version_111(self):
        req = str(self.common_lg_req_111).replace('sld_version=1.1.0', 'sld_version=1.0.0')
        resp = self.app.get(req)
        eq_(resp.content_type, 'application/vnd.ogc.se_xml')
        xml = resp.lxml
        assert 'invalid sld_version' in xml.xpath('//ServiceException/text()')[0]
        assert validate_with_dtd(xml, 'wms/1.1.1/exception_1_1_1.dtd')

    def test_get_legendgraphic_no_legend_130(self):
        self.common_lg_req_130.params['layer'] = 'wms_no_legend'
        resp = self.app.get(self.common_lg_req_130)
        eq_(resp.content_type, 'text/xml')
        xml = resp.lxml
        eq_xpath_wms130(xml, '/ogc:ServiceExceptionReport/@version', '1.3.0')
        eq_xpath_wms130(xml, '//ogc:ServiceException/text()', 'layer wms_no_legend has no legend graphic')
        assert validate_with_xsd(xml, xsd_name='wms/1.3.0/exceptions_1_3_0.xsd')

    def test_get_legendgraphic_missing_params_130(self):
        req = str(self.common_lg_req_130).replace('format', 'invalid')
        resp = self.app.get(req)
        eq_(resp.content_type, 'text/xml')
        xml = resp.lxml
        eq_xpath_wms130(xml, '/ogc:ServiceExceptionReport/@version', '1.3.0')
        eq_xpath_wms130(xml, '//ogc:ServiceException/text()', "missing parameters ['format']")
        assert validate_with_xsd(xml, xsd_name='wms/1.3.0/exceptions_1_3_0.xsd')

    def test_get_legendgraphic_invalid_sld_version_130(self):
        req = str(self.common_lg_req_130).replace('sld_version=1.1.0', 'sld_version=1.0.0')
        resp = self.app.get(req)
        eq_(resp.content_type, 'text/xml')
        xml = resp.lxml
        eq_xpath_wms130(xml, '/ogc:ServiceExceptionReport/@version', '1.3.0')
        eq_xpath_wms130(xml, '//ogc:ServiceException/text()', 'invalid sld_version 1.0.0')
        assert validate_with_xsd(xml, xsd_name='wms/1.3.0/exceptions_1_3_0.xsd')

