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

from cStringIO import StringIO
from mapproxy.request.wms import WMS111MapRequest
from mapproxy.platform.image import Image
from mapproxy.test.image import is_png, tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import module_setup, module_teardown, SystemTest
from nose.tools import eq_

test_config = {}

def setup_module():
    module_setup(test_config, 'coverage.yaml')

def teardown_module():
    module_teardown(test_config)

class TestCoverageWMS(SystemTest):
    config = test_config
    def setup(self):
        SystemTest.setup(self)
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS', 
             version='1.1.1', bbox='-180,0,0,80', width='200', height='200',
             layers='wms_cache', srs='EPSG:4326', format='image/png',
             styles='', request='GetMap'))
    
    def test_capababilities(self):
        resp = self.app.get('/service?request=GetCapabilities&service=WMS&version=1.1.1')
        xml = resp.lxml
        # First: combined root, second: wms_cache, third: tms_cache
        eq_(xml.xpath('//LatLonBoundingBox/@minx'), ['10', '10', '12'])
        eq_(xml.xpath('//LatLonBoundingBox/@miny'), ['10', '15', '10'])
        eq_(xml.xpath('//LatLonBoundingBox/@maxx'), ['35', '30', '35'])
        eq_(xml.xpath('//LatLonBoundingBox/@maxy'), ['31', '31', '30'])

    def test_get_map_outside(self):
        self.common_map_req.params.bbox = -90, 0, 0, 90
        self.common_map_req.params['bgcolor'] = '0xff0005'
        resp = self.app.get(self.common_map_req)
        eq_(resp.content_type, 'image/png')
        data = StringIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        eq_(img.mode, 'RGB')
        eq_(img.getcolors(), [(200*200, (255, 0, 5))])
    
    def test_get_map_outside_transparent(self):
        self.common_map_req.params.bbox = -90, 0, 0, 90
        self.common_map_req.params.transparent = True
        resp = self.app.get(self.common_map_req)
        eq_(resp.content_type, 'image/png')
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
                eq_(resp.content_type, 'image/png')
                data = StringIO(resp.body)
                assert is_png(data)
                eq_(Image.open(data).mode, 'RGB')

class TestCoverageTMS(SystemTest):
    config = test_config
    
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

