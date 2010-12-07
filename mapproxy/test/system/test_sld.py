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
import os
import tempfile
from urllib import quote

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.test.system import module_setup, module_teardown, make_base_config, SystemTest
from mapproxy.test.http import mock_httpd

test_config = {}

def setup_module():
    test_config['base_dir'] = tempfile.mkdtemp()
    with open(os.path.join(test_config['base_dir'], 'mysld.xml'), 'w') as f:
        f.write('<sld>')
    module_setup(test_config, 'sld.yaml')

def teardown_module():
    module_teardown(test_config)

base_config = make_base_config(test_config)

TESTSERVER_ADDRESS = 'localhost', 42423

class TestWMS(SystemTest):
    config = test_config
    def setup(self):
        SystemTest.setup(self)
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
             version='1.1.1', bbox='0,0,10,10', width='200', height='200',
             srs='EPSG:4326', format='image/png', styles='', request='GetMap'))
        self.common_wms_url = ("/service?styles=&srs=EPSG%3A4326&version=1.1.1&"
            "bbox=0.0,0.0,10.0,10.0&service=WMS&format=image%2Fpng&request=GetMap"
            "&width=200&height=200")
    
    def test_sld_url(self):
        self.common_map_req.params['layers'] = 'sld_url'
        with mock_httpd(TESTSERVER_ADDRESS, [
          ({'path': self.common_wms_url + '&sld=' +quote('http://example.org/sld.xml'),
            'method': 'GET'},
           {'body': ''})]):
            self.app.get(self.common_map_req)

    def test_sld_file(self):
        self.common_map_req.params['layers'] = 'sld_file'
        with mock_httpd(TESTSERVER_ADDRESS, [
          ({'path': self.common_wms_url + '&sld_body=' +quote('<sld>'), 'method': 'GET'},
           {'body': ''})]):
            self.app.get(self.common_map_req)

    def test_sld_body(self):
        self.common_map_req.params['layers'] = 'sld_body'
        with mock_httpd(TESTSERVER_ADDRESS, [
          ({'path': self.common_wms_url + '&sld_body=' +quote('<sld:StyledLayerDescriptor />'),
            'method': 'POST'},
           {'body': ''})]):
            self.app.get(self.common_map_req)
    

