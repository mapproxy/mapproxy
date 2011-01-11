# This file is part of the MapProxy project.
# Copyright (C) 2010, 2011 Omniscale <http://omniscale.de>
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

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.test.image import is_transparent, create_tmp_image, bgcolor_ratio
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import module_setup, module_teardown, SystemTest
from mapproxy.test.system.test_wms import is_111_exception
from nose.tools import eq_

test_config = {}

def setup_module():
    module_setup(test_config, 'source_errors.yaml')

def teardown_module():
    module_teardown(test_config)


transp = create_tmp_image((200, 200), mode='RGBA', color=(0, 0, 0, 0))

class TestWMS(SystemTest):
    config = test_config
    def setup(self):
        SystemTest.setup(self)
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS', 
             version='1.1.1', bbox='9,50,10,51', width='200', height='200',
             layers='online', srs='EPSG:4326', format='image/png',
             styles='', request='GetMap', transparent=True))
    
    def test_online(self):
        common_params = (r'?SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0'
                                  '&WIDTH=200&transparent=True')
        
        expected_req = [({'path': '/service_a' + common_params + '&layers=a_one'},
                         {'body': transp, 'headers': {'content-type': 'image/png'}}),
                        ]
                         
        with mock_httpd(('localhost', 42423), expected_req):
            self.common_map_req.params.layers = 'online'
            resp = self.app.get(self.common_map_req)
            eq_(resp.content_type, 'image/png')
            assert is_transparent(resp.body)

    def test_mixed_layer_source(self):
        common_params = (r'?SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0'
                                  '&WIDTH=200&transparent=True')
        
        expected_req = [({'path': '/service_a' + common_params + '&layers=a_one'},
                         {'body': transp, 'headers': {'content-type': 'image/png'}}),
                        ]
                         
        with mock_httpd(('localhost', 42423), expected_req):
            self.common_map_req.params.layers = 'mixed'
            resp = self.app.get(self.common_map_req)
            eq_(resp.content_type, 'image/png')
            assert 0.99 > bgcolor_ratio(resp.body) > 0.95

    def test_mixed_sources(self):
        common_params = (r'?SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0'
                                  '&WIDTH=200&transparent=True')
        
        expected_req = [({'path': '/service_a' + common_params + '&layers=a_one'},
                         {'body': transp, 'headers': {'content-type': 'image/png'}}),
                        ]
                         
        with mock_httpd(('localhost', 42423), expected_req):
            self.common_map_req.params.layers = 'online,all_offline'
            resp = self.app.get(self.common_map_req)
            eq_(resp.content_type, 'image/png')
            assert 0.99 > bgcolor_ratio(resp.body) > 0.95
            # open('/tmp/foo.png', 'wb').write(resp.body)
    
    def test_all_offline(self):
        self.common_map_req.params.layers = 'all_offline'
        resp = self.app.get(self.common_map_req)
        eq_(resp.content_type, 'application/vnd.ogc.se_xml')
        is_111_exception(resp.lxml, re_msg='no response from url')


