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
from mapproxy.test.image import is_jpeg, is_png, tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.helper import validate_with_dtd, validate_with_xsd
from nose.tools import eq_, assert_almost_equal

from mapproxy.test.system.test_wms import is_111_exception

global_app = None

def setup_module():
    fixture_dir = os.path.join(os.path.dirname(__file__), 'fixture')
    fixture_layer_conf = os.path.join(fixture_dir, 'layer.yaml')
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

class TestWMSC(WMSTest):
    def setup(self):
        WMSTest.setup(self)
        self.common_cap_req = WMS111CapabilitiesRequest(url='/service?', param=dict(service='WMS', 
             version='1.1.1'))
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS', 
             version='1.1.1', bbox='-20037508,0.0,0.0,20037508', width='256', height='256',
             layers='wms_cache', srs='EPSG:900913', format='image/jpeg',
             styles='', request='GetMap'))
        self.common_fi_req = WMS111FeatureInfoRequest(url='/service?',
            param=dict(x='10', y='20', width='200', height='200', layers='wms_cache',
                       format='image/png', query_layers='wms_cache', styles='',
                       bbox='1000,400,2000,1400', srs='EPSG:900913'))
    
    def test_capabilities(self):
        req = str(self.common_cap_req) + '&tiled=true'
        resp = self.app.get(req)
        xml = resp.lxml
        assert validate_with_dtd(xml, dtd_name='wmsc/1.1.1/WMS_MS_Capabilities.dtd')
        eq_(len(xml.xpath('//TileSet')), 7)
    
    def test_get_tile(self):
        resp = self.app.get(str(self.common_map_req) + '&tiled=true')
        eq_(resp.content_type, 'image/jpeg')
        data = StringIO(resp.body)
        assert is_jpeg(data)

    def test_get_tile_w_rounded_bbox(self):
        self.common_map_req.params.bbox = '-20037400,0.0,0.0,20037400'
        resp = self.app.get(str(self.common_map_req) + '&tiled=true')
        eq_(resp.content_type, 'image/jpeg')
        data = StringIO(resp.body)
        assert is_jpeg(data)
        
    def test_get_tile_wrong_bbox(self):
        self.common_map_req.params.bbox = '-20037508,0.0,200000.0,20037508'
        resp = self.app.get(str(self.common_map_req) + '&tiled=true')
        is_111_exception(resp.lxml, re_msg='.*invalid bbox')
    
    def test_get_tile_wrong_fromat(self):
        self.common_map_req.params.format = 'image/png'
        resp = self.app.get(str(self.common_map_req) + '&tiled=true')
        is_111_exception(resp.lxml, re_msg='Invalid request: invalid.*format.*jpeg')
    
    def test_get_tile_wrong_size(self):
        self.common_map_req.params.size = (256, 255)
        resp = self.app.get(str(self.common_map_req) + '&tiled=true')
        is_111_exception(resp.lxml, re_msg='Invalid request: invalid.*size.*256x256')
