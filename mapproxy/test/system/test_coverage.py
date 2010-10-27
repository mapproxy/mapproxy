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
from mapproxy.platform.image import Image

from cStringIO import StringIO
from webtest import TestApp
import mapproxy.config
from mapproxy.wsgiapp import make_wsgi_app 
from mapproxy.request.wms import WMS111MapRequest
from mapproxy.test.image import is_png, tmp_image
from mapproxy.test.http import mock_httpd
from nose.tools import eq_

global_app = None

def setup_module():
    fixture_dir = os.path.join(os.path.dirname(__file__), 'fixture')
    fixture_layer_conf = os.path.join(fixture_dir, 'coverage.yaml')
    fixture_cache_data = os.path.join(fixture_dir, 'cache_data')
    mapproxy.config.base_config().debug_mode = True
    mapproxy.config.base_config().services_conf = fixture_layer_conf
    mapproxy.config.base_config().cache.base_dir = fixture_cache_data
    mapproxy.config.base_config().image.paletted = False
    mapproxy.config._service_config = None
    
    global global_app
    global_app = TestApp(make_wsgi_app(fixture_layer_conf), use_unicode=False)

def teardown_module():
    mapproxy.config._config = None
    mapproxy.config._service_config = None


class WMSTest(object):
    def setup(self):
        self.app = global_app
        self.created_tiles = []
    
    def created_tiles_filenames(self):
        base_dir = mapproxy.config.base_config().cache.base_dir
        for filename in self.created_tiles:
            yield os.path.join(base_dir, filename)
    
    def _test_created_tiles(self):
        for filename in self.created_tiles_filenames():
            if not os.path.exists(filename):
                assert False, "didn't found tile " + filename
    
    def teardown(self):
        self._test_created_tiles()
        for filename in self.created_tiles_filenames():
            if os.path.exists(filename):
                os.remove(filename)

class TestWMS(WMSTest):
    def setup(self):
        WMSTest.setup(self)
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS', 
             version='1.1.1', bbox='-180,0,0,80', width='200', height='200',
             layers='wms_cache', srs='EPSG:4326', format='image/png',
             styles='', request='GetMap'))
    
    def test_get_map_outside(self):
        self.common_map_req.params.bbox = -90, 0, 0, 90
        self.common_map_req.params['bgcolor'] = '0xff0005'
        resp = self.app.get(self.common_map_req)
        resp.content_type = 'image/png'
        data = StringIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        eq_(img.mode, 'RGB')
        eq_(img.getcolors(), [(200*200, (255, 0, 5))])
    
    def test_get_map_outside_transparent(self):
        self.common_map_req.params.bbox = -90, 0, 0, 90
        self.common_map_req.params.transparent = True
        resp = self.app.get(self.common_map_req)
        resp.content_type = 'image/png'
        data = StringIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        eq_(img.mode, 'RGBA')
        eq_(img.getcolors()[0][0], 200*200)
        eq_(img.getcolors()[0][1][3], 0) # transparent
    
    def test_get_map_intersection(self):
        self.created_tiles.append('wms_cache_EPSG4326/03/000/000/004/000/000/002.jpeg')
        with tmp_image((256, 256), format='jpeg') as img:
            expected_req = ({'path': r'/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&styles='
                                      '&VERSION=1.1.1&BBOX=0.0,0.0,45.0,45.0'
                                      '&WIDTH=256'},
                            {'body': img.read(), 'headers': {'content-type': 'image/jpeg'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                self.common_map_req.params.bbox = 0, 0, 40, 40
                self.common_map_req.params.transparent = True
                resp = self.app.get(self.common_map_req)
                resp.content_type = 'image/png'
                data = StringIO(resp.body)
                assert is_png(data)
                assert Image.open(data).mode == 'RGBA'

class TestTMS(object):
    def setup(self):
        self.app = global_app
        self.created_tiles = []
    
    def test_get_tile_intersections(self):
        with tmp_image((256, 256), format='jpeg') as img:
            expected_req = ({'path': r'/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles='
                                      '&VERSION=1.1.1&BBOX=0.0,0.0,20037508.3428,20037508.3428'
                                      '&WIDTH=256'},
                            {'body': img.read(), 'headers': {'content-type': 'image/jgeg'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                resp = self.app.get('/tms/1.0.0/wms_cache/0/1/1.jpeg')
                eq_(resp.content_type, 'image/jpeg')
                self.created_tiles.append('wms_cache_EPSG900913/01/000/000/001/000/000/001.jpeg')
    
    def test_get_tile_intersection_tms(self):
        with tmp_image((256, 256), format='jpeg') as img:
            expected_req = ({'path': r'/tms/1.0.0/foo/1/1/1.jpeg'},
                            {'body': img.read(), 'headers': {'content-type': 'image/jgeg'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                resp = self.app.get('/tms/1.0.0/tms_cache/0/1/1.jpeg')
                eq_(resp.content_type, 'image/jpeg')
                self.created_tiles.append('tms_cache_EPSG900913/01/000/000/001/000/000/001.jpeg')

    
    def created_tiles_filenames(self):
        base_dir = mapproxy.config.base_config().cache.base_dir
        for filename in self.created_tiles:
            yield os.path.join(base_dir, filename)
    
    def teardown(self):
        for filename in self.created_tiles_filenames():
            if os.path.exists(filename):
                os.remove(filename)