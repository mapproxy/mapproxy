# This file is part of the MapProxy project.
# Copyright (C) 2012 Omniscale <http://omniscale.de>
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
from mapproxy.test.image import tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config
from nose.tools import eq_

test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    module_setup(test_config, 'cache_grid_names.yaml')

def teardown_module():
    module_teardown(test_config)

class TestCacheGridNames(SystemTest):
    config = test_config

    def test_tms_capabilities(self):
        resp = self.app.get('/tms/1.0.0/')
        assert 'Cached Layer' in resp
        assert 'wms_cache/utm32n' in resp
        assert 'wms_cache_utm32n' not in resp
        xml = resp.lxml
        assert xml.xpath('count(//TileMap)') == 2

    def test_tms_layer_capabilities(self):
        resp = self.app.get('/tms/1.0.0/wms_cache/utm32n')
        assert 'Cached Layer' in resp
        assert 'wms_cache/utm32n' in resp
        assert 'wms_cache_utm32n' not in resp
        xml = resp.lxml
        eq_(xml.xpath('count(//TileSet)'), 12)

    def test_kml(self):
        resp = self.app.get('/kml/wms_cache/utm32n/4/2/2.kml')
        assert b'wms_cache/utm32n' in resp.body

    def test_get_tile(self):
        with tmp_image((256, 256), format='jpeg') as img:
            expected_req = ({'path': r'/service?LAYERs=bar&SERVICE=WMS&FORMAT=image%2Fjpeg'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A25832&styles='
                                      '&VERSION=1.1.1&BBOX=283803.311362,5609091.90862,319018.942566,5644307.53982'
                                      '&WIDTH=256'},
                            {'body': img.read(), 'headers': {'content-type': 'image/jpeg'}})
            with mock_httpd(('localhost', 42423), [expected_req], bbox_aware_query_comparator=True):
                resp = self.app.get('/tms/1.0.0/wms_cache/utm32n/4/2/2.jpeg')
                eq_(resp.content_type, 'image/jpeg')
                self.created_tiles.append('wms_cache/utm32n/04/000/000/002/000/000/002.jpeg')

    def test_get_tile_no_grid_name(self):
        # access tiles with grid name from TMS but cache still uses old SRS-code path
        with tmp_image((256, 256), format='jpeg') as img:
            expected_req = ({'path': r'/service?LAYERs=bar&SERVICE=WMS&FORMAT=image%2Fjpeg'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A25832&styles='
                                      '&VERSION=1.1.1&BBOX=283803.311362,5609091.90862,319018.942566,5644307.53982'
                                      '&WIDTH=256'},
                            {'body': img.read(), 'headers': {'content-type': 'image/jpeg'}})
            with mock_httpd(('localhost', 42423), [expected_req], bbox_aware_query_comparator=True):
                resp = self.app.get('/tms/1.0.0/wms_cache_no_grid_name/utm32n/4/2/2.jpeg')
                eq_(resp.content_type, 'image/jpeg')
                self.created_tiles.append('wms_cache_no_grid_name_EPSG25832/04/000/000/002/000/000/002.jpeg')

    def created_tiles_filenames(self):
        base_dir = base_config().cache.base_dir
        for filename in self.created_tiles:
            yield os.path.join(base_dir, filename)

    def check_created_tiles(self):
        for filename in self.created_tiles_filenames():
            if not os.path.exists(filename):
                assert False, "didn't found tile " + filename

    def teardown(self):
        self.check_created_tiles()
        for filename in self.created_tiles_filenames():
            if os.path.exists(filename):
                os.remove(filename)
