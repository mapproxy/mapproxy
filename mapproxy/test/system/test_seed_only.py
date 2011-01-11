# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement, division

from cStringIO import StringIO
from mapproxy.request.wms import WMS111MapRequest
from mapproxy.platform.image import Image
from mapproxy.test.image import is_png
from mapproxy.test.system import module_setup, module_teardown, SystemTest
from nose.tools import eq_

test_config = {}

def setup_module():
    module_setup(test_config, 'seedonly.yaml', with_cache_data=True)

def teardown_module():
    module_teardown(test_config)

class TestCoverageWMS(SystemTest):
    config = test_config
    def setup(self):
        SystemTest.setup(self)
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS', 
             version='1.1.1', bbox='-180,0,0,80', width='200', height='200',
             layers='wms_cache', srs='EPSG:4326', format='image/png',
             styles='', request='GetMap', transparent=True))
            
    def test_get_map_cached(self):
        resp = self.app.get(self.common_map_req)
        resp.content_type = 'image/png'
        data = StringIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        eq_(img.mode, 'RGB')
        # cached image has more that 256 colors, getcolors -> None
        eq_(img.getcolors(), None)

    def test_get_map_uncached(self):
        self.common_map_req.params['bbox'] = '10,10,20,20'
        resp = self.app.get(self.common_map_req)
        resp.content_type = 'image/png'
        data = StringIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        eq_(img.mode, 'RGBA')
        eq_(img.getcolors(), [(200*200, (255, 255, 255, 0))])