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

from __future__ import with_statement, division

import functools

from mapproxy.test.image import create_tmp_image
from mapproxy.test.http import MockServ
from mapproxy.test.helper import validate_with_xsd
from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config
from nose.tools import eq_

test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    module_setup(test_config, 'wmts_dimensions.yaml', with_cache_data=True)

def teardown_module():
    module_teardown(test_config)

ns_wmts = {
    'wmts': 'http://www.opengis.net/wmts/1.0',
    'ows': 'http://www.opengis.net/ows/1.1',
    'xlink': 'http://www.w3.org/1999/xlink'
}

def eq_xpath(xml, xpath, expected, namespaces=None):
    eq_(xml.xpath(xpath, namespaces=namespaces)[0], expected)

eq_xpath_wmts = functools.partial(eq_xpath, namespaces=ns_wmts)

DIMENSION_LAYER_BASE_REQ = (
    '/service1?styles=&format=image%2Fpng&height=256'
    '&bbox=-20037508.3428,0.0,0.0,20037508.3428'
    '&layers=foo,bar&service=WMS&srs=EPSG%3A900913'
    '&request=GetMap&width=256&version=1.1.1'
)
NO_DIMENSION_LAYER_BASE_REQ = DIMENSION_LAYER_BASE_REQ.replace('/service1?', '/service2?')

WMTS_KVP_URL = (
    '/service?service=wmts&request=GetTile&version=1.0.0'
    '&tilematrixset=GLOBAL_MERCATOR&tilematrix=01&tilecol=0&tilerow=0&format=png&style='
)

TEST_TILE = create_tmp_image((256, 256))

class TestWMTS(SystemTest):
    config = test_config
    def setup(self):
        SystemTest.setup(self)

    def test_capabilities(self):
        resp = self.app.get('/wmts/myrest/1.0.0/WMTSCapabilities.xml')
        xml = resp.lxml
        assert validate_with_xsd(xml, xsd_name='wmts/1.0/wmtsGetCapabilities_response.xsd')

        eq_(len(xml.xpath('//wmts:Layer', namespaces=ns_wmts)), 2)
        eq_(len(xml.xpath('//wmts:Contents/wmts:TileMatrixSet', namespaces=ns_wmts)), 1)

        eq_(set(xml.xpath('//wmts:Contents/wmts:Layer/wmts:ResourceURL/@template', namespaces=ns_wmts)),
            set(['http://localhost/wmts/myrest/dimension_layer/{TileMatrixSet}/{Time}/{Elevation}/{TileMatrix}/{TileCol}/{TileRow}.png',
             'http://localhost/wmts/myrest/no_dimension_layer/{TileMatrixSet}/{Time}/{Elevation}/{TileMatrix}/{TileCol}/{TileRow}.png']))

        # check dimension values for dimension_layer
        dimension_elems = xml.xpath(
            '//wmts:Layer/ows:Identifier[text()="dimension_layer"]/following-sibling::wmts:Dimension',
            namespaces=ns_wmts,
        )
        dimensions = {}
        for elem in dimension_elems:
            dim = elem.find('{http://www.opengis.net/ows/1.1}Identifier').text
            default = elem.find('{http://www.opengis.net/wmts/1.0}Default').text
            values = [e.text for e in elem.findall('{http://www.opengis.net/wmts/1.0}Value')]
            dimensions[dim] = (values, default)

        eq_(dimensions['Time'][0],
            ["2012-11-12T00:00:00", "2012-11-13T00:00:00",
             "2012-11-14T00:00:00", "2012-11-15T00:00:00"]
        )
        eq_(dimensions['Time'][1], '2012-11-15T00:00:00')
        eq_(dimensions['Elevation'][1], '0')
        eq_(dimensions['Elevation'][0],
            ["0", "1000", "3000"]
        )


    def test_get_tile_valid_dimension(self):
        serv = MockServ(42423, bbox_aware_query_comparator=True)
        serv.expects(DIMENSION_LAYER_BASE_REQ + '&Time=2012-11-15T00:00:00&elevation=1000').returns(TEST_TILE)
        with serv:
            resp = self.app.get('/wmts/dimension_layer/GLOBAL_MERCATOR/2012-11-15T00:00:00/1000/01/0/0.png')
        eq_(resp.content_type, 'image/png')

    def test_get_tile_invalid_dimension(self):
        self.check_invalid_parameter('/wmts/dimension_layer/GLOBAL_MERCATOR/2042-11-15T00:00:00/default/01/0/0.png')

    def test_get_tile_default_dimension(self):
        serv = MockServ(42423, bbox_aware_query_comparator=True)
        serv.expects(DIMENSION_LAYER_BASE_REQ + '&Time=2012-11-15T00:00:00&elevation=0').returns(TEST_TILE)
        with serv:
            resp = self.app.get('/wmts/dimension_layer/GLOBAL_MERCATOR/default/default/01/0/0.png')
        eq_(resp.content_type, 'image/png')

    def test_get_tile_invalid_no_dimension_source(self):
        # unsupported dimension need to be 'default' in RESTful request
        self.check_invalid_parameter('/wmts/no_dimension_layer/GLOBAL_MERCATOR/2042-11-15T00:00:00/default/01/0/0.png')

    def test_get_tile_default_no_dimension_source(self):
        # check if dimensions are ignored
        serv = MockServ(42423, bbox_aware_query_comparator=True)
        serv.expects(NO_DIMENSION_LAYER_BASE_REQ).returns(TEST_TILE)
        with serv:
            resp = self.app.get('/wmts/no_dimension_layer/GLOBAL_MERCATOR/default/default/01/0/0.png')
        eq_(resp.content_type, 'image/png')


    def test_get_tile_kvp_valid_dimension(self):
        serv = MockServ(42423, bbox_aware_query_comparator=True)
        serv.expects(DIMENSION_LAYER_BASE_REQ + '&Time=2012-11-14T00:00:00&elevation=3000').returns(TEST_TILE)
        with serv:
            resp = self.app.get(WMTS_KVP_URL + '&layer=dimension_layer&timE=2012-11-14T00:00:00&ELEvatioN=3000')
        eq_(resp.content_type, 'image/png')

    def test_get_tile_kvp_valid_dimension_defaults(self):
        serv = MockServ(42423, bbox_aware_query_comparator=True)
        serv.expects(DIMENSION_LAYER_BASE_REQ + '&Time=2012-11-15T00:00:00&elevation=0').returns(TEST_TILE)
        with serv:
            resp = self.app.get(WMTS_KVP_URL + '&layer=dimension_layer')
        eq_(resp.content_type, 'image/png')

    def test_get_tile_kvp_invalid_dimension(self):
        self.check_invalid_parameter(WMTS_KVP_URL + '&layer=dimension_layer&elevation=500')


    def test_get_tile_kvp_default_no_dimension_source(self):
        # check if dimensions are ignored
        serv = MockServ(42423, bbox_aware_query_comparator=True)
        serv.expects(NO_DIMENSION_LAYER_BASE_REQ).returns(TEST_TILE)
        with serv:
            resp = self.app.get(WMTS_KVP_URL + '&layer=no_dimension_layer&Time=2012-11-14T00:00:00&Elevation=3000')
        eq_(resp.content_type, 'image/png')

    def check_invalid_parameter(self, url):
        resp = self.app.get(url, status=400)
        xml = resp.lxml
        eq_(resp.content_type, 'text/xml')
        assert validate_with_xsd(xml, xsd_name='ows/1.1.0/owsExceptionReport.xsd')
        eq_xpath_wmts(xml, '/ows:ExceptionReport/ows:Exception/@exceptionCode',
            'InvalidParameterValue')

