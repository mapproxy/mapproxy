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
from mapproxy.test.image import is_png, tmp_image, create_tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import module_setup, module_teardown, SystemTest
from nose.tools import eq_

test_config = {}

def setup_module():
    module_setup(test_config, 'combined_sources.yaml')

def teardown_module():
    module_teardown(test_config)

class TestCoverageWMS(SystemTest):
    config = test_config
    def setup(self):
        SystemTest.setup(self)
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
             version='1.1.1', bbox='9,50,10,51', width='200', height='200',
             layers='combinable', srs='EPSG:4326', format='image/png',
             styles='', request='GetMap'))

    def test_combined(self):
        common_params = (r'?SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0'
                                  '&WIDTH=200&transparent=True')

        with tmp_image((200, 200), format='png') as img:
            img = img.read()
            expected_req = [({'path': '/service_a' + common_params + '&layers=a_one,a_two,a_three,a_four'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                            ({'path': '/service_b' + common_params + '&layers=b_one'},
                             {'body': img, 'headers': {'content-type': 'image/png'}})
                            ]

            with mock_httpd(('localhost', 42423), expected_req):
                self.common_map_req.params.layers = 'combinable'
                resp = self.app.get(self.common_map_req)
                eq_(resp.content_type, 'image/png')
                data = BytesIO(resp.body)
                assert is_png(data)

    def test_uncombined(self):
        common_params = (r'?SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0'
                                  '&WIDTH=200&transparent=True')

        with tmp_image((200, 200), format='png') as img:
            img = img.read()
            expected_req = [({'path': '/service_a' + common_params + '&layers=a_one'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                            ({'path': '/service_b' + common_params + '&layers=b_one'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                            ({'path': '/service_a' + common_params + '&layers=a_two,a_three'},
                             {'body': img, 'headers': {'content-type': 'image/png'}})
                            ]

            with mock_httpd(('localhost', 42423), expected_req):
                self.common_map_req.params.layers = 'uncombinable'
                resp = self.app.get(self.common_map_req)
                eq_(resp.content_type, 'image/png')
                data = BytesIO(resp.body)
                assert is_png(data)

    def test_combined_layers(self):
        common_params = (r'?SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0'
                                  '&WIDTH=200&transparent=True')

        with tmp_image((200, 200), format='png') as img:
            img = img.read()
            expected_req = [
                            ({'path': '/service_a' + common_params + '&layers=a_one'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                            ({'path': '/service_b' + common_params + '&layers=b_one'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                            ({'path': '/service_a' + common_params + '&layers=a_two,a_three,a_four'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                            ]

            with mock_httpd(('localhost', 42423), expected_req):
                self.common_map_req.params.layers = 'uncombinable,single'
                resp = self.app.get(self.common_map_req)
                eq_(resp.content_type, 'image/png')
                data = BytesIO(resp.body)
                assert is_png(data)

    def test_layers_with_opacity(self):
        # overlay with opacity -> request should not be combined
        common_params = (r'?SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0'
                                  '&WIDTH=200')

        img_bg = create_tmp_image((200, 200), color=(0, 0, 0))
        img_fg = create_tmp_image((200, 200), color=(255, 0, 128))

        expected_req = [
                        ({'path': '/service_a' + common_params + '&layers=a_one'},
                         {'body': img_bg, 'headers': {'content-type': 'image/png'}}),
                        ({'path': '/service_a' + common_params + '&layers=a_two'},
                         {'body': img_fg, 'headers': {'content-type': 'image/png'}}),
                        ]

        with mock_httpd(('localhost', 42423), expected_req):
            self.common_map_req.params.layers = 'opacity_base,opacity_overlay'
            resp = self.app.get(self.common_map_req)
            eq_(resp.content_type, 'image/png')
            data = BytesIO(resp.body)
            assert is_png(data)
            img = Image.open(data)
            eq_(img.getcolors()[0], ((200*200),(127, 0, 64)))

    def test_combined_transp_color(self):
        # merged to one request because both layers share the same transparent_color
        common_params = (r'?SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0'
                                  '&WIDTH=200&transparent=True')

        with tmp_image((200, 200), color=(255, 0, 0), format='png') as img:
            img = img.read()
            expected_req = [({'path': '/service_a' + common_params + '&layers=a_iopts_one,a_iopts_two'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                            ]

            with mock_httpd(('localhost', 42423), expected_req):
                self.common_map_req.params.layers = 'layer_image_opts1,layer_image_opts2'
                self.common_map_req.params.transparent = True
                resp = self.app.get(self.common_map_req)
                resp.content_type = 'image/png'
                data = BytesIO(resp.body)
                assert is_png(data)
                img = Image.open(data)
                eq_(img.getcolors()[0], ((200*200),(255, 0, 0, 0)))

    def test_combined_mixed_transp_color(self):
        # not merged to one request because only one layer has transparent_color
        common_params = (r'?SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0'
                                  '&WIDTH=200&transparent=True')

        with tmp_image((200, 200), color=(255, 0, 0), format='png') as img:
            img = img.read()
            expected_req = [({'path': '/service_a' + common_params + '&layers=a_four'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                            ({'path': '/service_a' + common_params + '&layers=a_iopts_one'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                            ]

            with mock_httpd(('localhost', 42423), expected_req):
                self.common_map_req.params.layers = 'single,layer_image_opts1'
                self.common_map_req.params.transparent = True
                resp = self.app.get(self.common_map_req)
                resp.content_type = 'image/png'
                data = BytesIO(resp.body)
                assert is_png(data)

    def test_combined_same_fwd_req_params(self):
        # merged to one request because all layers share the same time param in
        # fwd_req_params config
        with tmp_image((200, 200), format='png') as img:
            img = img.read()
            expected_req = [({'path': '/service_a?SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0'
                                  '&WIDTH=200&transparent=True&TIME=20041012'
                                  '&layers=a_one,a_two,a_three,a_four'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                            ]

            with mock_httpd(('localhost', 42423), expected_req):
                self.common_map_req.params.layers = 'layer_fwdparams1,layer_fwdparams2'
                self.common_map_req.params['time'] = '20041012'
                self.common_map_req.params.transparent = True
                resp = self.app.get(self.common_map_req)
                resp.content_type = 'image/png'
                data = BytesIO(resp.body)
                assert is_png(data)

    def test_combined_no_fwd_req_params(self):
        # merged to one request because no vendor param is set
        with tmp_image((200, 200), format='png') as img:
            img = img.read()
            expected_req = [({'path': '/service_a?SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0'
                                  '&WIDTH=200&transparent=True'
                                  '&layers=a_one,a_two,a_four'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                            ]

            with mock_httpd(('localhost', 42423), expected_req):
                self.common_map_req.params.layers = 'layer_fwdparams1,single'
                self.common_map_req.params.transparent = True
                resp = self.app.get(self.common_map_req)
                resp.content_type = 'image/png'
                data = BytesIO(resp.body)
                assert is_png(data)

    def test_combined_mixed_fwd_req_params(self):
        # not merged to one request because fwd_req_params are different
        common_params = (r'/service_a?SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0'
                                  '&WIDTH=200&transparent=True')

        with tmp_image((200, 200), format='png') as img:
            img = img.read()
            expected_req = [({'path': common_params + '&layers=a_one&TIME=20041012'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                             ({'path': common_params + '&layers=a_two&TIME=20041012&VENDOR=foo'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                             ({'path': common_params + '&layers=a_four'},
                             {'body': img, 'headers': {'content-type': 'image/png'}}),
                            ]

            with mock_httpd(('localhost', 42423), expected_req):
                self.common_map_req.params.layers = 'layer_fwdparams1,single'
                self.common_map_req.params['time'] = '20041012'
                self.common_map_req.params['vendor'] = 'foo'
                self.common_map_req.params.transparent = True
                resp = self.app.get(self.common_map_req)
                resp.content_type = 'image/png'
                data = BytesIO(resp.body)
                assert is_png(data)

