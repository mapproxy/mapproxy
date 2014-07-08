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
from mapproxy.request.wms import WMS111MapRequest
from mapproxy.compat.image import Image
from mapproxy.test.image import is_png, is_jpeg
from mapproxy.test.system import module_setup, module_teardown, SystemTest
from nose.tools import eq_

test_config = {}

def setup_module():
    module_setup(test_config, 'seedonly.yaml', with_cache_data=True)

def teardown_module():
    module_teardown(test_config)

class TestSeedOnlyWMS(SystemTest):
    config = test_config
    def setup(self):
        SystemTest.setup(self)
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
             version='1.1.1', bbox='-180,0,0,80', width='200', height='200',
             layers='wms_cache', srs='EPSG:4326', format='image/png',
             styles='', request='GetMap', transparent=True))

    def test_get_map_cached(self):
        resp = self.app.get(self.common_map_req)
        eq_(resp.content_type, 'image/png')
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        eq_(img.mode, 'RGB')
        # cached image has more that 256 colors, getcolors -> None
        eq_(img.getcolors(), None)

    def test_get_map_uncached(self):
        self.common_map_req.params['bbox'] = '10,10,20,20'
        resp = self.app.get(self.common_map_req)
        eq_(resp.content_type, 'image/png')
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        eq_(img.mode, 'RGBA')
        eq_(img.getcolors(), [(200*200, (255, 255, 255, 0))])

class TestSeedOnlyTMS(SystemTest):
    config = test_config

    def test_get_tile_cached(self):
        resp = self.app.get('/tms/1.0.0/wms_cache/0/0/1.jpeg')
        eq_(resp.content_type, 'image/jpeg')
        data = BytesIO(resp.body)
        assert is_jpeg(data)
        img = Image.open(data)
        eq_(img.mode, 'RGB')
        # cached image has more that 256 colors, getcolors -> None
        eq_(img.getcolors(), None)

    def test_get_tile_uncached(self):
        resp = self.app.get('/tms/1.0.0/wms_cache/0/0/0.jpeg')
        eq_(resp.content_type, 'image/png')
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        eq_(img.mode, 'RGBA')
        eq_(img.getcolors(), [(256*256, (255, 255, 255, 0))])