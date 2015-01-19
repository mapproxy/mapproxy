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
from mapproxy.request.wms import (
    WMS111MapRequest, WMS111FeatureInfoRequest, WMS111CapabilitiesRequest
)
from mapproxy.test.image import is_jpeg
from mapproxy.test.helper import validate_with_dtd
from mapproxy.test.system.test_wms import is_111_exception
from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config
from nose.tools import eq_

test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    module_setup(test_config, 'layer.yaml', with_cache_data=True)

def teardown_module():
    module_teardown(test_config)

class TestWMSC(SystemTest):
    config = test_config
    def setup(self):
        SystemTest.setup(self)
        self.common_cap_req = WMS111CapabilitiesRequest(url='/service?', param=dict(service='WMS',
             version='1.1.1'))
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
             version='1.1.1', bbox='-20037508,0.0,0.0,20037508', width='256', height='256',
             layers='wms_cache', srs='EPSG:900913', format='image/jpeg',
             styles='', request='GetMap'))
        self.common_fi_req = WMS111FeatureInfoRequest(url='/service?',
            param=dict(x='10', y='20', width='200', height='200', layers='wms_cache',
                       format='image/png', query_layers='wms_cache', styles='',
                       bbox='1000,400,2000,1400', srs='EPSG:900913'))

    def test_capabilities(self):
        req = str(self.common_cap_req) + '&tiled=true'
        resp = self.app.get(req)
        xml = resp.lxml
        assert validate_with_dtd(xml, dtd_name='wmsc/1.1.1/WMS_MS_Capabilities.dtd')
        srs = set([e.text for e in xml.xpath('//TileSet/SRS')])
        eq_(srs, set(['EPSG:4326', 'EPSG:900913']))
        eq_(len(xml.xpath('//TileSet')), 11)

    def test_get_tile(self):
        resp = self.app.get(str(self.common_map_req) + '&tiled=true')
        assert 'public' in resp.headers['Cache-Control']
        eq_(resp.content_type, 'image/jpeg')
        data = BytesIO(resp.body)
        assert is_jpeg(data)

    def test_get_tile_w_rounded_bbox(self):
        self.common_map_req.params.bbox = '-20037400,0.0,0.0,20037400'
        resp = self.app.get(str(self.common_map_req) + '&tiled=true')
        assert 'public' in resp.headers['Cache-Control']
        eq_(resp.content_type, 'image/jpeg')
        data = BytesIO(resp.body)
        assert is_jpeg(data)

    def test_get_tile_wrong_bbox(self):
        self.common_map_req.params.bbox = '-20037508,0.0,200000.0,20037508'
        resp = self.app.get(str(self.common_map_req) + '&tiled=true')
        assert 'Cache-Control' not in resp.headers
        is_111_exception(resp.lxml, re_msg='.*invalid bbox')

    def test_get_tile_wrong_fromat(self):
        self.common_map_req.params.format = 'image/png'
        resp = self.app.get(str(self.common_map_req) + '&tiled=true')
        assert 'Cache-Control' not in resp.headers
        is_111_exception(resp.lxml, re_msg='Invalid request: invalid.*format.*jpeg')

    def test_get_tile_wrong_size(self):
        self.common_map_req.params.size = (256, 255)
        resp = self.app.get(str(self.common_map_req) + '&tiled=true')
        assert 'Cache-Control' not in resp.headers
        is_111_exception(resp.lxml, re_msg='Invalid request: invalid.*size.*256x256')
