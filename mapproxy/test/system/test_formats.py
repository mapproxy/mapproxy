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
import sys
import tempfile
import shutil
from mapproxy.platform.image import Image
import functools

from cStringIO import StringIO
from webtest import TestApp
import mapproxy.config
from mapproxy.srs import SRS
from mapproxy.wsgiapp import make_wsgi_app 
from mapproxy.request.wms import WMS100MapRequest, WMS111MapRequest, WMS130MapRequest, \
                                 WMS111FeatureInfoRequest, WMS111CapabilitiesRequest, \
                                 WMS130CapabilitiesRequest, WMS100CapabilitiesRequest, \
                                 WMS100FeatureInfoRequest, WMS130FeatureInfoRequest
from mapproxy.test.unit.test_grid import assert_almost_equal_bbox
from mapproxy.test.image import is_jpeg, is_png, tmp_image, check_format
from mapproxy.test.http import mock_httpd
from mapproxy.test.helper import validate_with_dtd, validate_with_xsd
from nose.tools import eq_, assert_almost_equal

global_app = None
tmp_cache_dir = tempfile.mkdtemp()

def setup_module():
    fixture_dir = os.path.join(os.path.dirname(__file__), 'fixture')
    fixture_layer_conf = os.path.join(fixture_dir, 'formats.yaml')
    fixture_cache_data = tmp_cache_dir
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
    shutil.rmtree(tmp_cache_dir)

class TilesTest(object):
    def setup(self):
        self.app = global_app
        self.created_tiles = []
    
    def created_tiles_filenames(self):
        base_dir = mapproxy.config.base_config().cache.base_dir
        for filename, format in self.created_tiles:
            yield os.path.join(base_dir, filename), format
    
    def _test_created_tiles(self):
        for filename, format in self.created_tiles_filenames():
            if not os.path.exists(filename):
                assert False, "didn't found tile " + filename
            else:
                check_format(open(filename, 'rb'), format)
            
    def teardown(self):
        self._test_created_tiles()
        for filename, _format in self.created_tiles_filenames():
            if os.path.exists(filename):
                os.remove(filename)


class TestWMS111(TilesTest):
    def setup(self):
        TilesTest.setup(self)
        self.common_req = WMS111MapRequest(url='/service?', param=dict(service='WMS', 
             version='1.1.1'))
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS', 
             version='1.1.1', bbox='0,0,180,80', width='200', height='200',
             layers='wms_cache', srs='EPSG:4326', format='image/png',
             styles='', request='GetMap'))
        self.common_direct_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS', 
             version='1.1.1', bbox='0,0,10,10', width='200', height='200',
             layers='wms_cache', srs='EPSG:4326', format='image/png',
             styles='', request='GetMap'))
        self.common_fi_req = WMS111FeatureInfoRequest(url='/service?',
            param=dict(x='10', y='20', width='200', height='200', layers='wms_cache',
                       format='image/png', query_layers='wms_cache', styles='',
                       bbox='1000,400,2000,1400', srs='EPSG:900913'))
        self.expected_base_path = '/service?SERVICE=WMS&REQUEST=GetMap&HEIGHT=256' \
            '&SRS=EPSG%3A900913&styles=&VERSION=1.1.1&WIDTH=256' \
            '&BBOX=0.0,0.0,20037508.3428,20037508.3428'
        self.expected_direct_base_path = '/service?SERVICE=WMS&REQUEST=GetMap&HEIGHT=200' \
            '&SRS=EPSG%3A4326&styles=&VERSION=1.1.1&WIDTH=200' \
            '&BBOX=0.0,0.0,10.0,10.0'
                
    def test_cache_formats(self):
        yield self.check_get_cached, 'jpeg_cache_tiff_source', 'tiffsource', 'png', 'jpeg', 'tiff'
        yield self.check_get_cached, 'jpeg_cache_tiff_source', 'tiffsource', 'jpeg', 'jpeg', 'tiff'
        yield self.check_get_cached, 'jpeg_cache_tiff_source', 'tiffsource', 'tiff', 'jpeg', 'tiff'
        yield self.check_get_cached, 'jpeg_cache_tiff_source', 'tiffsource', 'gif', 'jpeg', 'tiff'

        yield self.check_get_cached, 'png_cache_all_source', 'allsource', 'png', 'png', 'png'
        yield self.check_get_cached, 'png_cache_all_source', 'allsource', 'jpeg', 'png', 'png'

        yield self.check_get_cached, 'jpeg_cache_png_jpeg_source', 'pngjpegsource', 'jpeg', 'jpeg', 'jpeg'
        yield self.check_get_cached, 'jpeg_cache_png_jpeg_source', 'pngjpegsource', 'png', 'jpeg', 'jpeg'
        
    def test_direct_formats(self):
        yield self.check_get_direct, 'jpeg_cache_tiff_source', 'tiffsource', 'gif', 'tiff'
        yield self.check_get_direct, 'jpeg_cache_tiff_source', 'tiffsource', 'jpeg', 'tiff'
        yield self.check_get_direct, 'jpeg_cache_tiff_source', 'tiffsource', 'png', 'tiff'

        yield self.check_get_direct, 'png_cache_all_source', 'allsource', 'gif', 'gif'
        yield self.check_get_direct, 'png_cache_all_source', 'allsource', 'png', 'png'
        yield self.check_get_direct, 'png_cache_all_source', 'allsource', 'tiff', 'tiff'
        
        yield self.check_get_direct, 'jpeg_cache_png_jpeg_source', 'pngjpegsource', 'jpeg', 'jpeg'
        yield self.check_get_direct, 'jpeg_cache_png_jpeg_source', 'pngjpegsource', 'png', 'png'
        yield self.check_get_direct, 'jpeg_cache_png_jpeg_source', 'pngjpegsource', 'tiff', 'png'
        yield self.check_get_direct, 'jpeg_cache_png_jpeg_source', 'pngjpegsource', 'gif', 'png'


    def check_get_cached(self, layer, source, wms_format, cache_format, req_format):
        self.created_tiles.append((layer+'_EPSG900913/01/000/000/001/000/000/001.'+cache_format, cache_format))
        with tmp_image((256, 256), format=req_format) as img:
            expected_req = ({'path': self.expected_base_path +
                                     '&layers=' + source +
                                     '&format=image%2F' + req_format},
                            {'body': img.read(), 'headers': {'content-type': 'image/'+req_format}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                self.common_map_req.params['layers'] = layer
                self.common_map_req.params['format'] = 'image/'+wms_format
                resp = self.app.get(self.common_map_req)
                eq_(resp.content_type, 'image/'+wms_format)
                check_format(StringIO(resp.body), wms_format)

    def check_get_direct(self, layer, source, wms_format, req_format):
        with tmp_image((256, 256), format=req_format) as img:
            expected_req = ({'path': self.expected_direct_base_path +
                                     '&layers=' + source +
                                     '&format=image%2F' + req_format},
                            {'body': img.read(), 'headers': {'content-type': 'image/'+req_format}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                self.common_direct_map_req.params['layers'] = layer
                self.common_direct_map_req.params['format'] = 'image/'+wms_format
                resp = self.app.get(self.common_direct_map_req)
                eq_(resp.content_type, 'image/'+wms_format)    
                check_format(StringIO(resp.body), wms_format)

class TestTMS(TilesTest):
    def setup(self):
        TilesTest.setup(self)
        self.expected_base_path = '/service?SERVICE=WMS&REQUEST=GetMap&HEIGHT=256' \
            '&SRS=EPSG%3A900913&styles=&VERSION=1.1.1&WIDTH=256' \
            '&BBOX=0.0,0.0,20037508.3428,20037508.3428'
        self.expected_direct_base_path = '/service?SERVICE=WMS&REQUEST=GetMap&HEIGHT=200' \
            '&SRS=EPSG%3A4326&styles=&VERSION=1.1.1&WIDTH=200' \
            '&BBOX=0.0,0.0,10.0,10.0'
            
    
    def test_cache_formats(self):
        yield self.check_get_cached, 'jpeg_cache_tiff_source', 'tiffsource', 'jpeg', 'jpeg', 'tiff'

        yield self.check_get_cached, 'png_cache_all_source', 'allsource', 'png', 'png', 'png'

        yield self.check_get_cached, 'jpeg_cache_png_jpeg_source', 'pngjpegsource', 'jpeg', 'jpeg', 'jpeg'
        

    def check_get_cached(self, layer, source, tms_format, cache_format, req_format):
        self.created_tiles.append((layer+'_EPSG900913/01/000/000/001/000/000/001.'+cache_format, cache_format))
        with tmp_image((256, 256), format=req_format) as img:
            expected_req = ({'path': self.expected_base_path +
                                     '&layers=' + source +
                                     '&format=image%2F' + req_format},
                            {'body': img.read(), 'headers': {'content-type': 'image/'+req_format}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                resp = self.app.get('/tms/1.0.0/%s/0/1/1.%s' % (layer, tms_format))
                eq_(resp.content_type, 'image/'+tms_format)
                check_format(StringIO(resp.body), tms_format)
