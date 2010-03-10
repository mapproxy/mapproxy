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

from __future__ import with_statement
import os
import hashlib
from cStringIO import StringIO
from webtest import TestApp
import mapproxy.core.config
from mapproxy.core.app import make_wsgi_app
from mapproxy.core.timeutils import format_httpdate

from mapproxy.tests.image import is_jpeg, tmp_image
from mapproxy.tests.http import mock_httpd
from mapproxy.tests.helper import validate_with_xsd
from nose.tools import eq_

ns = {'kml': 'http://www.opengis.net/kml/2.2'}

global_app = None

def setup_module():
    fixture_dir = os.path.join(os.path.dirname(__file__), 'fixture')
    fixture_layer_conf = os.path.join(fixture_dir, 'layer.yaml')
    fixture_cache_data = os.path.join(fixture_dir, 'cache_data')
    mapproxy.core.config.base_config().services_conf = fixture_layer_conf
    mapproxy.core.config.base_config().cache.meta_size = (1, 1)
    mapproxy.core.config.base_config().cache.meta_buffer = 0
    mapproxy.core.config.base_config().cache.base_dir = fixture_cache_data
    
    global global_app
    global_app = TestApp(make_wsgi_app(init_logging=False))

def teardown_module():
    mapproxy.core.config._config = None
    mapproxy.core.config._service_config = None
    

class TestKML(object):
    def setup(self):
        self.app = global_app
        self.created_tiles = []
        
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
        base_dir = mapproxy.core.config.base_config().cache.base_dir
        os.utime(os.path.join(base_dir,
                              'wms_cache_EPSG900913/01/000/000/000/000/000/001.jpeg'),
                 (timestamp, timestamp))
        max_age = mapproxy.core.config.base_config().tiles.expires_hours * 60 * 60
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
                      namespaces=ns)[0],
            'http://localhost:80/kml/wms_cache/EPSG900913/0/0/0.jpeg')
        eq_(xml.xpath('/kml:kml/kml:Document/kml:NetworkLink[1]/kml:Link/kml:href/text()',
                      namespaces=ns)[0],
            'http://localhost:80/kml/wms_cache/EPSG900913/1/0/0.kml')
        
        timestamp = os.stat(mapproxy.core.config.base_config().services_conf).st_mtime
        etag = hashlib.md5(resp.body).hexdigest()
        max_age = mapproxy.core.config.base_config().tiles.expires_hours * 60 * 60
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
                      namespaces=ns)[0],
            'http://localhost:80/kml/wms_cache_multi/EPSG4326/1/0/0.jpeg')
        eq_(xml.xpath('/kml:kml/kml:Document/kml:NetworkLink[1]/kml:Link/kml:href/text()',
                      namespaces=ns)[0],
            'http://localhost:80/kml/wms_cache_multi/EPSG4326/2/0/0.kml')
    
    
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
        base_dir = mapproxy.core.config.base_config().cache.base_dir
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