# This file is part of the MapProxy project.
# Copyright (C) 2010-2012 Omniscale <http://omniscale.de>
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
import os

try:
    import json; json
except ImportError:
    # test skipped later
    json = None

from mapproxy.test.image import img_from_buf
from mapproxy.test.http import mock_single_req_httpd
from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config
from mapproxy.request.wms import WMS111MapRequest, WMS111FeatureInfoRequest, WMS111CapabilitiesRequest
from mapproxy.test.helper import validate_with_dtd
from mapproxy.test.http import mock_httpd
from mapproxy.test.image import create_tmp_image
from mapproxy.test.system.test_wms import is_111_exception
from mapproxy.util.fs import ensure_directory
from mapproxy.cache.renderd import has_renderd_support

from nose.tools import eq_
from nose.plugins.skip import SkipTest

test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    if not has_renderd_support():
        raise SkipTest("requests required")

    module_setup(test_config, 'renderd_client.yaml', with_cache_data=True)

def teardown_module():
    module_teardown(test_config)

try:
    from http.server import BaseHTTPRequestHandler
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler


class TestWMS111(SystemTest):
    config = test_config

    def setup(self):
        SystemTest.setup(self)
        self.common_req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
             version='1.1.1'))
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
             version='1.1.1', bbox='-180,0,0,80', width='200', height='200',
             layers='wms_cache', srs='EPSG:4326', format='image/png',
             exceptions='xml',
             styles='', request='GetMap'))
        self.common_fi_req = WMS111FeatureInfoRequest(url='/service?',
            param=dict(x='10', y='20', width='200', height='200', layers='wms_cache',
                       format='image/png', query_layers='wms_cache', styles='',
                       bbox='1000,400,2000,1400', srs='EPSG:900913'))

    def test_wms_capabilities(self):
        req = WMS111CapabilitiesRequest(url='/service?').copy_with_request_params(self.common_req)
        resp = self.app.get(req)
        eq_(resp.content_type, 'application/vnd.ogc.wms_xml')
        xml = resp.lxml
        eq_(xml.xpath('//GetMap//OnlineResource/@xlink:href',
                      namespaces=dict(xlink="http://www.w3.org/1999/xlink"))[0],
            'http://localhost/service?')

        layer_names = set(xml.xpath('//Layer/Layer/Name/text()'))
        expected_names = set(['direct', 'wms_cache',
            'tms_cache'])
        eq_(layer_names, expected_names)
        assert validate_with_dtd(xml, dtd_name='wms/1.1.1/WMS_MS_Capabilities.dtd')

    def test_get_map(self):
        test_self = self
        class req_handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers['content-length'])
                json_data = self.rfile.read(length)
                task = json.loads(json_data.decode('utf-8'))
                eq_(task['command'], 'tile')
                # request main tile of metatile
                eq_(task['tiles'], [[15, 17, 5]])
                eq_(task['cache_identifier'], 'wms_cache_GLOBAL_MERCATOR')
                eq_(task['priority'], 100)
                # this id should not change for the same tile/cache_identifier combination
                eq_(task['id'], 'aeb52b506e4e82d0a1edf649d56e0451cfd5862c')

                # manually create tile renderd should create
                tile_filename = os.path.join(test_self.config['cache_dir'],
                    'wms_cache_EPSG900913/05/000/000/016/000/000/016.jpeg')
                ensure_directory(tile_filename)
                with open(tile_filename, 'wb') as f:
                    f.write(create_tmp_image((256, 256), format='jpeg', color=(255, 0, 100)))

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')

            def log_request(self, code, size=None):
                pass

        with mock_single_req_httpd(('localhost', 42423), req_handler):
            self.common_map_req.params['bbox'] = '0,0,9,9'
            resp = self.app.get(self.common_map_req)

            img = img_from_buf(resp.body)
            main_color = sorted(img.convert('RGBA').getcolors())[-1]
            # check for red color (jpeg/png conversion requires fuzzy comparision)
            assert main_color[0] == 40000
            assert main_color[1][0] > 250
            assert main_color[1][1] < 5
            assert 95 < main_color[1][2] < 105
            assert main_color[1][3] == 255

            eq_(resp.content_type, 'image/png')
            self.created_tiles.append('wms_cache_EPSG900913/05/000/000/016/000/000/016.jpeg')

    def test_get_map_error(self):
        class req_handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers['content-length'])
                json_data = self.rfile.read(length)
                task = json.loads(json_data.decode('utf-8'))
                eq_(task['command'], 'tile')
                # request main tile of metatile
                eq_(task['tiles'], [[15, 17, 5]])
                eq_(task['cache_identifier'], 'wms_cache_GLOBAL_MERCATOR')
                eq_(task['priority'], 100)
                # this id should not change for the same tile/cache_identifier combination
                eq_(task['id'], 'aeb52b506e4e82d0a1edf649d56e0451cfd5862c')

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "error", "error_message": "barf"}')

            def log_request(self, code, size=None):
                pass

        with mock_single_req_httpd(('localhost', 42423), req_handler):
            self.common_map_req.params['bbox'] = '0,0,9,9'
            resp = self.app.get(self.common_map_req)

            eq_(resp.content_type, 'application/vnd.ogc.se_xml')
            is_111_exception(resp.lxml, re_msg='Error from renderd: barf')

    def test_get_map_connection_error(self):
        self.common_map_req.params['bbox'] = '0,0,9,9'
        resp = self.app.get(self.common_map_req)

        eq_(resp.content_type, 'application/vnd.ogc.se_xml')
        is_111_exception(resp.lxml, re_msg='Error while communicating with renderd:')

    def test_get_map_non_json_response(self):
        class req_handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers['content-length'])
                json_data = self.rfile.read(length)
                json.loads(json_data.decode('utf-8'))

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"invalid')

            def log_request(self, code, size=None):
                pass

        with mock_single_req_httpd(('localhost', 42423), req_handler):
            self.common_map_req.params['bbox'] = '0,0,9,9'
            resp = self.app.get(self.common_map_req)

        eq_(resp.content_type, 'application/vnd.ogc.se_xml')
        is_111_exception(resp.lxml, re_msg='Error while communicating with renderd: invalid JSON')


    def test_get_featureinfo(self):
        expected_req = ({'path': r'/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913'
                                  '&VERSION=1.1.1&BBOX=1000.0,400.0,2000.0,1400.0&styles='
                                  '&WIDTH=200&QUERY_LAYERS=foo,bar&X=10&Y=20&feature_count=100'},
                        {'body': b'info', 'headers': {'content-type': 'text/plain'}})
        with mock_httpd(('localhost', 42423), [expected_req]):
            self.common_fi_req.params['feature_count'] = 100
            resp = self.app.get(self.common_fi_req)
            eq_(resp.content_type, 'text/plain')
            eq_(resp.body, b'info')

class TestTiles(SystemTest):
    config = test_config

    def test_get_tile(self):
        test_self = self
        class req_handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers['content-length'])
                json_data = self.rfile.read(length)
                task = json.loads(json_data.decode('utf-8'))
                eq_(task['command'], 'tile')
                eq_(task['tiles'], [[10, 20, 6]])
                eq_(task['cache_identifier'], 'tms_cache_GLOBAL_MERCATOR')
                eq_(task['priority'], 100)
                # this id should not change for the same tile/cache_identifier combination
                eq_(task['id'], 'cf35c1c927158e188d8fbe0db380c1772b536da9')

                # manually create tile renderd should create
                tile_filename = os.path.join(test_self.config['cache_dir'],
                    'tms_cache_EPSG900913/06/000/000/010/000/000/020.png')
                ensure_directory(tile_filename)
                with open(tile_filename, 'wb') as f:
                    f.write(b"foobaz")

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')

            def log_request(self, code, size=None):
                pass

        with mock_single_req_httpd(('localhost', 42423), req_handler):
            resp = self.app.get('/tiles/tms_cache/EPSG900913/6/10/20.png')

            eq_(resp.content_type, 'image/png')
            eq_(resp.body, b'foobaz')
            self.created_tiles.append('tms_cache_EPSG900913/06/000/000/010/000/000/020.png')

    def test_get_tile_error(self):
        class req_handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers['content-length'])
                json_data = self.rfile.read(length)
                task = json.loads(json_data.decode('utf-8'))
                eq_(task['command'], 'tile')
                eq_(task['tiles'], [[10, 20, 7]])
                eq_(task['cache_identifier'], 'tms_cache_GLOBAL_MERCATOR')
                eq_(task['priority'], 100)
                # this id should not change for the same tile/cache_identifier combination
                eq_(task['id'], 'c24b8c3247afec34fd0a53e5d3706e977877ef47')

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "error", "error_message": "you told me to fail"}')

            def log_request(self, code, size=None):
                pass

        with mock_single_req_httpd(('localhost', 42423), req_handler):
            resp = self.app.get('/tiles/tms_cache/EPSG900913/7/10/20.png', status=500)
            eq_(resp.content_type, 'text/plain')
            eq_(resp.body, b'Error from renderd: you told me to fail')
