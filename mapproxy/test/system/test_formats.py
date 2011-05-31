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
from cStringIO import StringIO
from mapproxy.request.wms import WMS111MapRequest, WMS111FeatureInfoRequest
from mapproxy.test.image import tmp_image, check_format
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config
from nose.tools import eq_

test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    module_setup(test_config, 'formats.yaml', with_cache_data=True)

def teardown_module():
    module_teardown(test_config)

class TilesTest(SystemTest):
    config = test_config
    
    def created_tiles_filenames(self):
        base_dir = base_config().cache.base_dir
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
                # check_format(StringIO(resp.body), tms_format)
