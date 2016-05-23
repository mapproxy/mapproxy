# This file is part of the MapProxy project.
# Copyright (C) 2016 Omniscale <http://omniscale.de>
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

from __future__ import with_statement
from mapproxy.request.wms import WMS111MapRequest
from mapproxy.request.wmts import WMTS100CapabilitiesRequest
from mapproxy.test.image import img_from_buf
from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config
from nose.tools import eq_

test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    module_setup(test_config, 'cache_band_merge.yaml', with_cache_data=True)

def teardown_module():
    module_teardown(test_config)


class TestCacheSource(SystemTest):

    # test various band merge configurations with
    # cached base tile 0/0/0.png (R: 50 G: 100 B: 200)

    config = test_config

    def setup(self):
        SystemTest.setup(self)
        self.common_cap_req = WMTS100CapabilitiesRequest(url='/service?', param=dict(service='WMTS',
             version='1.0.0', request='GetCapabilities'))
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
             version='1.1.1', bbox='-180,0,0,80', width='100', height='100',
             layers='dop_l', srs='EPSG:4326', format='image/png',
             styles='', request='GetMap'))

    def test_capabilities(self):
        req = str(self.common_cap_req)
        resp = self.app.get(req)
        eq_(resp.content_type, 'application/xml')

    def test_get_tile_021(self):
        resp = self.app.get('/wmts/dop_021/GLOBAL_WEBMERCATOR/0/0/0.png')
        eq_(resp.content_type, 'image/png')
        img = img_from_buf(resp.body)
        eq_(img.mode, 'RGB')
        eq_(img.getpixel((0, 0)), (50, 200, 100))

    def test_get_tile_l(self):
        resp = self.app.get('/wmts/dop_l/GLOBAL_WEBMERCATOR/0/0/0.png')
        eq_(resp.content_type, 'image/png')
        img = img_from_buf(resp.body)
        eq_(img.mode, 'L')
        eq_(img.getpixel((0, 0)), int(50*0.25+0.7*100+0.05*200))

    def test_get_tile_0(self):
        resp = self.app.get('/wmts/dop_0/GLOBAL_WEBMERCATOR/0/0/0.png')
        eq_(resp.content_type, 'image/png')
        img = img_from_buf(resp.body)
        eq_(img.mode, 'RGB') # forced with image.mode
        eq_(img.getpixel((0, 0)), (50, 50, 50))

    def test_get_tile_0122(self):
        resp = self.app.get('/wmts/dop_0122/GLOBAL_WEBMERCATOR/0/0/0.png')
        eq_(resp.content_type, 'image/png')
        img = img_from_buf(resp.body)
        eq_(img.mode, 'RGBA')
        eq_(img.getpixel((0, 0)), (50, 100, 200, 50))

    def test_get_map_l(self):
        resp = self.app.get(str(self.common_map_req))
        eq_(resp.content_type, 'image/png')
        img = img_from_buf(resp.body)
        eq_(img.mode, 'L')
        eq_(img.getpixel((0, 0)), int(50*0.25+0.7*100+0.05*200))

    def test_get_map_l_jpeg(self):
        self.common_map_req.params.format = 'image/jpeg'
        resp = self.app.get(str(self.common_map_req))
        eq_(resp.content_type, 'image/jpeg')
        img = img_from_buf(resp.body)
        eq_(img.mode, 'RGB')
        # L converted to RGB for jpeg
        eq_(img.getpixel((0, 0)), (92, 92, 92))
