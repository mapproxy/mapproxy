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
from mapproxy.test.image import is_jpeg, tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config
from nose.tools import eq_

test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    module_setup(test_config, 'layer.yaml', with_cache_data=True)

def teardown_module():
    module_teardown(test_config)

class TestTMS(SystemTest):
    config = test_config
    
    def test_tms_capabilities(self):
        resp = self.app.get('/tms/1.0.0/')
        assert 'WMS Cache Layer' in resp
        assert 'WMS Cache Multi Layer' in resp
        assert 'TMS Cache Layer' in resp
        xml = resp.lxml
        assert xml.xpath('count(//TileMap)') == 9
        
        # without trailing space
        resp2 = self.app.get('/tms/1.0.0')
        eq_(resp.body, resp2.body)

    def test_tms_layer_capabilities(self):
        resp = self.app.get('/tms/1.0.0/wms_cache')
        assert 'WMS Cache Layer' in resp
        xml = resp.lxml
        eq_(xml.xpath('count(//TileSet)'), 19)
    
    def test_tms_get_out_of_bounds_tile(self):
        for coord in [(0, 0, -1), (-1, 0, 0), (0, -1, 0), (4, 2, 1), (1, 3, 0)]:
            yield self.check_out_of_bounds, coord
    
    def check_out_of_bounds(self, coord):
        x, y, z = coord
        url = '/tms/1.0.0/wms_cache/%d/%d/%d.jpeg' % (z, x, y)
        resp = self.app.get(url , status=404)
        xml = resp.lxml
        assert ('outside the bounding box' 
                in xml.xpath('/TileMapServerError/Message/text()')[0])
    
    def test_invalid_layer(self):
        resp = self.app.get('/tms/1.0.0/inVAlid/0/0/0.png', status=404)
        xml = resp.lxml
        assert ('unknown layer: inVAlid' 
                in xml.xpath('/TileMapServerError/Message/text()')[0])
    
    def test_invalid_format(self):
        resp = self.app.get('/tms/1.0.0/wms_cache/0/0/1.png', status=404)
        xml = resp.lxml
        assert ('invalid format' 
                 in xml.xpath('/TileMapServerError/Message/text()')[0])
    
    def test_get_tile_tile_source_error(self):
        resp = self.app.get('/tms/1.0.0/wms_cache/0/0/0.jpeg', status=500)
        xml = resp.lxml
        assert ('No response from URL' 
                in xml.xpath('/TileMapServerError/Message/text()')[0])
    
    def test_get_cached_tile(self):
        resp = self.app.get('/tms/1.0.0/wms_cache/0/0/1.jpeg')
        eq_(resp.content_type, 'image/jpeg')
        eq_(resp.content_length, len(resp.body))
        data = StringIO(resp.body)
        assert is_jpeg(data)
    
    def test_get_tile(self):
        with tmp_image((256, 256), format='jpeg') as img:
            expected_req = ({'path': r'/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles='
                                      '&VERSION=1.1.1&BBOX=-20037508.3428,-20037508.3428,0.0,0.0'
                                      '&WIDTH=256'},
                            {'body': img.read(), 'headers': {'content-type': 'image/jgeg'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                resp = self.app.get('/tms/1.0.0/wms_cache/0/0/0.jpeg')
                eq_(resp.content_type, 'image/jpeg')
                self.created_tiles.append('wms_cache_EPSG900913/01/000/000/000/000/000/000.jpeg')
    
    def test_get_tile_from_cache_with_tile_source(self):
        with tmp_image((256, 256), format='jpeg') as img:
            expected_req = ({'path': r'/tiles/01/000/000/000/000/000/001.png'},
                            {'body': img.read(), 'headers': {'content-type': 'image/png'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                resp = self.app.get('/tms/1.0.0/tms_cache/0/0/1.png')
                eq_(resp.content_type, 'image/png')
                self.created_tiles.append('tms_cache_EPSG900913/01/000/000/000/000/000/001.png')
    
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

class TestTileService(SystemTest):
    config = test_config
    
    def test_get_out_of_bounds_tile(self):
        for coord in [(0, 0, -1), (-1, 0, 0), (0, -1, 0), (4, 2, 1), (1, 3, 0)]:
            yield self.check_out_of_bounds, coord
    
    def check_out_of_bounds(self, coord):
        x, y, z = coord
        url = '/tiles/wms_cache/%d/%d/%d.jpeg' % (z, x, y)
        resp = self.app.get(url , status=404)
        assert 'outside the bounding box' in resp
        
    def test_invalid_layer(self):
        resp = self.app.get('/tiles/inVAlid/0/0/0.png', status=404)
        eq_(resp.content_type, 'text/plain')
        assert 'unknown layer: inVAlid' in resp
    
    def test_invalid_format(self):
        resp = self.app.get('/tiles/wms_cache/0/0/1.png', status=404)
        eq_(resp.content_type, 'text/plain')
        assert 'invalid format' in resp
    
    def test_get_tile_tile_source_error(self):
        resp = self.app.get('/tiles/wms_cache/0/0/0.jpeg', status=500)
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
    
    def _check_cache_control_headers(self, resp, etag, max_age):
        eq_(resp.headers['ETag'], etag)
        eq_(resp.headers['Last-modified'], 'Fri, 13 Feb 2009 23:31:30 GMT')
        eq_(resp.headers['Cache-control'], 'max-age=%d public' % max_age)
        
    def test_get_cached_tile(self):
        etag, max_age = self._update_timestamp()
        resp = self.app.get('/tiles/wms_cache/1/0/1.jpeg')
        self._check_cache_control_headers(resp, etag, max_age)
        self._check_tile_resp(resp)
        
    def test_get_cached_tile_flipped_y(self):
        etag, max_age = self._update_timestamp()
        resp = self.app.get('/tiles/wms_cache/1/0/0.jpeg?origin=nw')
        self._check_cache_control_headers(resp, etag, max_age)
        self._check_tile_resp(resp)
        
    def test_if_none_match(self):
        etag, max_age = self._update_timestamp()
        resp = self.app.get('/tiles/wms_cache/1/0/1.jpeg',
                            headers={'If-None-Match': etag})
        eq_(resp.status, '304 Not Modified')
        self._check_cache_control_headers(resp, etag, max_age)
    
        resp = self.app.get('/tiles/wms_cache/1/0/1.jpeg',
                            headers={'If-None-Match': etag + 'foo'})
        self._check_cache_control_headers(resp, etag, max_age)
        eq_(resp.status, '200 OK')
        self._check_tile_resp(resp)
    
    def test_if_modified_since(self):
        etag, max_age = self._update_timestamp()
        for date, modified in (
                ('Fri, 15 Feb 2009 23:31:30 GMT', False),
                ('Fri, 13 Feb 2009 23:31:31 GMT', False),
                ('Fri, 13 Feb 2009 23:31:30 GMT', False),
                ('Fri, 13 Feb 2009 23:31:29 GMT', True),
                ('Fri, 11 Feb 2009 23:31:29 GMT', True),
                ('Friday, 13-Feb-09 23:31:30 GMT', False),
                ('Friday, 13-Feb-09 23:31:29 GMT', True),
                ('Fri Feb 13 23:31:30 2009', False),
                ('Fri Feb 13 23:31:29 2009', True),
                # and some invalid ones
                ('Fri Foo 13 23:31:29 2009', True),
                ('1234567890', True),
                ):
            yield self.check_modified_response, date, modified, etag, max_age
    
    def check_modified_response(self, date, modified, etag, max_age):
        resp = self.app.get('/tiles/wms_cache/1/0/1.jpeg', headers={
                            'If-Modified-Since': date})
        self._check_cache_control_headers(resp, etag, max_age)
        if modified:
            eq_(resp.status, '200 OK')
            self._check_tile_resp(resp)
        else:
            eq_(resp.status, '304 Not Modified')
    
    def test_get_tile(self):
        with tmp_image((256, 256), format='jpeg') as img:
            expected_req = ({'path': r'/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles='
                                      '&VERSION=1.1.1&BBOX=-20037508.3428,-20037508.3428,0.0,0.0'
                                      '&WIDTH=256'},
                            {'body': img.read(), 'headers': {'content-type': 'image/jgeg'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                resp = self.app.get('/tiles/wms_cache/1/0/0.jpeg')
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