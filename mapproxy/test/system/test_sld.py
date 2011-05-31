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
    

