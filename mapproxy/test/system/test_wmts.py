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

from __future__ import with_statement, division

import re
import os
import shutil
import functools

from io import BytesIO
from mapproxy.request.wmts import (
    WMTS100TileRequest, WMTS100CapabilitiesRequest
)
from mapproxy.test.image import is_jpeg, create_tmp_image
from mapproxy.test.http import MockServ
from mapproxy.test.helper import validate_with_xsd
from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config
from nose.tools import eq_

test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    module_setup(test_config, 'wmts.yaml', with_cache_data=True)

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


class TestWMTS(SystemTest):
    config = test_config
    def setup(self):
        SystemTest.setup(self)
        self.common_cap_req = WMTS100CapabilitiesRequest(url='/service?', param=dict(service='WMTS',
             version='1.0.0', request='GetCapabilities'))
        self.common_tile_req = WMTS100TileRequest(url='/service?', param=dict(service='WMTS',
             version='1.0.0', tilerow='0', tilecol='0', tilematrix='01', tilematrixset='GLOBAL_MERCATOR',
             layer='wms_cache', format='image/jpeg', style='', request='GetTile'))

    def test_endpoints(self):
        for endpoint in ('service', 'ows'):
            req = WMTS100CapabilitiesRequest(url='/%s?' % endpoint).copy_with_request_params(self.common_cap_req)
            resp = self.app.get(req)
            eq_(resp.content_type, 'application/xml')
            xml = resp.lxml
            assert validate_with_xsd(xml, xsd_name='wmts/1.0/wmtsGetCapabilities_response.xsd')

    def test_capabilities(self):
        req = str(self.common_cap_req)
        resp = self.app.get(req)
        eq_(resp.content_type, 'application/xml')
        xml = resp.lxml
        assert validate_with_xsd(xml, xsd_name='wmts/1.0/wmtsGetCapabilities_response.xsd')
        eq_(xml.xpath('//wmts:Layer/ows:Identifier/text()', namespaces=ns_wmts),
            ['wms_cache','wms_cache_multi','tms_cache','tms_cache_ul','gk3_cache'],
        )
        eq_(len(xml.xpath('//wmts:Contents/wmts:TileMatrixSet', namespaces=ns_wmts)), 5)

        goog_matrixset = xml.xpath('//wmts:Contents/wmts:TileMatrixSet[./ows:Identifier/text()="GoogleMapsCompatible"]', namespaces=ns_wmts)[0]
        eq_(goog_matrixset.findtext('ows:Identifier', namespaces=ns_wmts), 'GoogleMapsCompatible')
        # top left corner: min X first then max Y
        assert re.match('-20037508\.\d+ 20037508\.\d+', goog_matrixset.findtext('./wmts:TileMatrix[1]/wmts:TopLeftCorner', namespaces=ns_wmts))

        gk_matrixset = xml.xpath('//wmts:Contents/wmts:TileMatrixSet[./ows:Identifier/text()="gk3"]', namespaces=ns_wmts)[0]
        eq_(gk_matrixset.findtext('ows:Identifier', namespaces=ns_wmts), 'gk3')
        # Gauß-Krüger uses "reverse" axis order -> top left corner: max Y first then min X
        assert re.match('6000000.0+ 3000000.0+', gk_matrixset.findtext('./wmts:TileMatrix[1]/wmts:TopLeftCorner', namespaces=ns_wmts))

    def test_get_tile(self):
        resp = self.app.get(str(self.common_tile_req))
        eq_(resp.content_type, 'image/jpeg')
        data = BytesIO(resp.body)
        assert is_jpeg(data)

    def test_get_tile_flipped_axis(self):
        # test default tile lock directory
        tiles_lock_dir = os.path.join(test_config['base_dir'], 'cache_data', 'tile_locks')
        # make sure default tile_lock_dir was not created by other tests
        shutil.rmtree(tiles_lock_dir, ignore_errors=True)
        assert not os.path.exists(tiles_lock_dir)

        self.common_tile_req.params['layer'] = 'tms_cache_ul'
        self.common_tile_req.params['tilematrixset'] = 'ulgrid'
        self.common_tile_req.params['format'] = 'image/png'
        self.common_tile_req.tile = (0, 0, '01')
        serv = MockServ(port=42423)
        # source is ll, cache/service ul
        serv.expects('/tiles/01/000/000/000/000/000/001.png')
        serv.returns(create_tmp_image((256, 256)))
        with serv:
            resp = self.app.get(str(self.common_tile_req), status=200)
            eq_(resp.content_type, 'image/png')

        # test default tile lock directory was created
        assert os.path.exists(tiles_lock_dir)


    def test_get_tile_source_error(self):
        self.common_tile_req.params['layer'] = 'tms_cache'
        self.common_tile_req.params['format'] = 'image/png'
        resp = self.app.get(str(self.common_tile_req), status=500)
        xml = resp.lxml
        assert validate_with_xsd(xml, xsd_name='ows/1.1.0/owsExceptionReport.xsd')
        eq_xpath_wmts(xml, '/ows:ExceptionReport/ows:Exception/@exceptionCode',
            'NoApplicableCode')

    def test_get_tile_out_of_range(self):
        self.common_tile_req.params.coord = -1, 1, 1
        resp = self.app.get(str(self.common_tile_req), status=400)
        xml = resp.lxml
        eq_(resp.content_type, 'text/xml')
        assert validate_with_xsd(xml, xsd_name='ows/1.1.0/owsExceptionReport.xsd')
        eq_xpath_wmts(xml, '/ows:ExceptionReport/ows:Exception/@exceptionCode',
            'TileOutOfRange')

    def test_get_tile_invalid_format(self):
        self.common_tile_req.params['format'] = 'image/png'
        self.check_invalid_parameter()

    def test_get_tile_invalid_layer(self):
        self.common_tile_req.params['layer'] = 'unknown'
        self.check_invalid_parameter()

    def test_get_tile_invalid_matrixset(self):
        self.common_tile_req.params['tilematrixset'] = 'unknown'
        self.check_invalid_parameter()

    def check_invalid_parameter(self):
        resp = self.app.get(str(self.common_tile_req), status=400)
        xml = resp.lxml
        eq_(resp.content_type, 'text/xml')
        assert validate_with_xsd(xml, xsd_name='ows/1.1.0/owsExceptionReport.xsd')
        eq_xpath_wmts(xml, '/ows:ExceptionReport/ows:Exception/@exceptionCode',
            'InvalidParameterValue')

