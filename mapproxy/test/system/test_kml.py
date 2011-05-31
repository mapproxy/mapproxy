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

from __future__ import with_statement
import os
import hashlib
from cStringIO import StringIO
from mapproxy.util.times import format_httpdate
from mapproxy.test.image import is_jpeg, tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.helper import validate_with_xsd
from nose.tools import eq_

ns = {'kml': 'http://www.opengis.net/kml/2.2'}

from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config

test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    module_setup(test_config, 'layer.yaml', with_cache_data=True)

def teardown_module():
    module_teardown(test_config)

class TestKML(SystemTest):
    config = test_config
        
    def test_get_out_of_bounds_tile(self):
        for coord in [(0, 0, -1), (-1, 0, 0), (0, -1, 0), (4, 2, 1), (1, 3, 0)]:
            yield self.check_out_of_bounds, coord
    
    def check_out_of_bounds(self, coord):
        x, y, z = coord
        url = '/kml/wms_cache/%d/%d/%d.kml' % (z, x, y)
        resp = self.app.get(url , status=404)
        assert 'outside the bounding box' in resp
        
    def test_invalid_layer(self):
        resp = self.app.get('/kml/inVAlid/0/0/0.png', status=404)
        eq_(resp.content_type, 'text/plain')
        assert 'unknown layer: inVAlid' in resp
    
    def test_invalid_format(self):
        resp = self.app.get('/kml/wms_cache/0/0/1.png', status=404)
        eq_(resp.content_type, 'text/plain')
        assert 'invalid format' in resp
    
    def test_get_tile_tile_source_error(self):
        resp = self.app.get('/kml/wms_cache/0/0/0.jpeg', status=500)
        eq_(resp.content_type, 'text/plain')
        assert 'No response from URL' in resp
    
    def _check_tile_resp(self, resp):
        eq_(resp.content_type, 'image/jpeg')
        eq_(resp.content_length, len(resp.body))
        data = StringIO(resp.body)
        assert is_jpeg(data)
    
    def _update_timestamp(self):
        timestamp = 1234567890.0
        size = 10214
        base_dir = base_config().cache.base_dir
        os.utime(os.path.join(base_dir,
                              'wms_cache_EPSG900913/01/000/000/000/000/000/001.jpeg'),
                 (timestamp, timestamp))
        max_age = base_config().tiles.expires_hours * 60 * 60
        etag = hashlib.md5(str(timestamp) + str(size)).hexdigest()
        return etag, max_age
    
    def _check_cache_control_headers(self, resp, etag, max_age, timestamp=1234567890.0):
        eq_(resp.headers['ETag'], etag)
        if timestamp is None:
            assert 'Last-modified' not in resp.headers
        else:
            eq_(resp.headers['Last-modified'], format_httpdate(timestamp))
        eq_(resp.headers['Cache-control'], 'max-age=%d public' % max_age)
    
    def test_get_cached_tile(self):
        etag, max_age = self._update_timestamp()
        resp = self.app.get('/kml/wms_cache/1/0/1.jpeg')
        self._check_cache_control_headers(resp, etag, max_age)
        self._check_tile_resp(resp)
    
    def test_if_none_match(self):
        etag, max_age = self._update_timestamp()
        resp = self.app.get('/kml/wms_cache/1/0/1.jpeg',
                            headers={'If-None-Match': etag})
        eq_(resp.status, '304 Not Modified')
        self._check_cache_control_headers(resp, etag, max_age)
    
        resp = self.app.get('/kml/wms_cache/1/0/1.jpeg',
                            headers={'If-None-Match': etag + 'foo'})
        self._check_cache_control_headers(resp, etag, max_age)
        eq_(resp.status, '200 OK')
        self._check_tile_resp(resp)
    
    def test_get_kml(self):
        resp = self.app.get('/kml/wms_cache/0/0/0.kml')
        xml = resp.lxml
        assert validate_with_xsd(xml, 'kml/2.2.0/ogckml22.xsd')
        eq_(xml.xpath('/kml:kml/kml:Document/kml:GroundOverlay/kml:Icon/kml:href/text()',
                      namespaces=ns),
            ['http://localhost/kml/wms_cache/EPSG900913/1/0/1.jpeg',
             'http://localhost/kml/wms_cache/EPSG900913/1/1/1.jpeg',
             'http://localhost/kml/wms_cache/EPSG900913/1/0/0.jpeg',
             'http://localhost/kml/wms_cache/EPSG900913/1/1/0.jpeg']
        )
        eq_(xml.xpath('/kml:kml/kml:Document/kml:NetworkLink/kml:Link/kml:href/text()',
                      namespaces=ns),
              ['http://localhost/kml/wms_cache/EPSG900913/1/0/1.kml',
               'http://localhost/kml/wms_cache/EPSG900913/1/1/1.kml',
               'http://localhost/kml/wms_cache/EPSG900913/1/0/0.kml',
               'http://localhost/kml/wms_cache/EPSG900913/1/1/0.kml']
        )
        
        etag = hashlib.md5(resp.body).hexdigest()
        max_age = base_config().tiles.expires_hours * 60 * 60
        self._check_cache_control_headers(resp, etag, max_age, None)
        
        resp = self.app.get('/kml/wms_cache/0/0/0.kml',
                            headers={'If-None-Match': etag})
        eq_(resp.status, '304 Not Modified')
    
    def test_get_kml2(self):
        resp = self.app.get('/kml/wms_cache/1/0/1.kml')
        xml = resp.lxml
        assert validate_with_xsd(xml, 'kml/2.2.0/ogckml22.xsd')
    
    def test_get_kml_multi_layer(self):
        resp = self.app.get('/kml/wms_cache_multi/1/0/0.kml')
        xml = resp.lxml
        assert validate_with_xsd(xml, 'kml/2.2.0/ogckml22.xsd')
        eq_(xml.xpath('/kml:kml/kml:Document/kml:GroundOverlay/kml:Icon/kml:href/text()',
                      namespaces=ns),
            ['http://localhost/kml/wms_cache_multi/EPSG4326/2/0/1.jpeg',
             'http://localhost/kml/wms_cache_multi/EPSG4326/2/1/1.jpeg',
             'http://localhost/kml/wms_cache_multi/EPSG4326/2/0/0.jpeg',
             'http://localhost/kml/wms_cache_multi/EPSG4326/2/1/0.jpeg']
        )
        eq_(xml.xpath('/kml:kml/kml:Document/kml:NetworkLink/kml:Link/kml:href/text()',
                      namespaces=ns),
          ['http://localhost/kml/wms_cache_multi/EPSG4326/2/0/1.kml',
           'http://localhost/kml/wms_cache_multi/EPSG4326/2/1/1.kml',
           'http://localhost/kml/wms_cache_multi/EPSG4326/2/0/0.kml',
           'http://localhost/kml/wms_cache_multi/EPSG4326/2/1/0.kml']
        )
    
    def test_get_tile(self):
        with tmp_image((256, 256), format='jpeg') as img:
            expected_req = ({'path': r'/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles='
                                      '&VERSION=1.1.1&BBOX=-20037508.3428,-20037508.3428,0.0,0.0'
                                      '&WIDTH=256'},
                            {'body': img.read(), 'headers': {'content-type': 'image/jgeg'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                resp = self.app.get('/kml/wms_cache/1/0/0.jpeg')
                eq_(resp.content_type, 'image/jpeg')
                self.created_tiles.append('wms_cache_EPSG900913/01/000/000/000/000/000/000.jpeg')
    
    def created_tiles_filenames(self):
        base_dir = base_config().cache.base_dir
        for filename in self.created_tiles:
            yield os.path.join(base_dir, filename)
    
    def test_created_tiles(self):
        for filename in self.created_tiles_filenames():
            if not os.path.exists(filename):
                assert False, "didn't found tile " + filename
    
    def teardown(self):
        for filename in self.created_tiles_filenames():
            if os.path.exists(filename):
                os.remove(filename)