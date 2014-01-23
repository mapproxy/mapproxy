# This file is part of the MapProxy project.
# Copyright (C) 2014 Omniscale <http://omniscale.de>
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

from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config
from mapproxy.test.image import is_png, is_transparent
from mapproxy.test.image import tmp_image, assert_colors_equal, img_from_buf
from mapproxy.test.http import mock_httpd
from nose.tools import eq_

test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    module_setup(test_config, 'wms_srs_extent.yaml')

def teardown_module():
    module_teardown(test_config)

class TestWMSSRSExtentTest(SystemTest):
    config = test_config

    def test_out_of_extent(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetMap'
            '&LAYERS=direct&STYLES='
            '&WIDTH=100&HEIGHT=100&FORMAT=image/png'
            '&BBOX=-10000,0,0,1000&SRS=EPSG:25832'
            '&VERSION=1.1.0&TRANSPARENT=TRUE')
        # empty/transparent response
        eq_(resp.content_type, 'image/png')
        assert is_png(resp.body)
        assert is_transparent(resp.body)

    def test_out_of_extent_bgcolor(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetMap'
            '&LAYERS=direct&STYLES='
            '&WIDTH=100&HEIGHT=100&FORMAT=image/png'
            '&BBOX=-10000,0,0,1000&SRS=EPSG:25832'
            '&VERSION=1.1.0&TRANSPARENT=FALSE&BGCOLOR=0xff0000')
        # red response
        eq_(resp.content_type, 'image/png')
        assert is_png(resp.body)
        assert_colors_equal(img_from_buf(resp.body).convert('RGBA'),
                [(100 * 100, [255, 0, 0, 255])])

    def test_clipped(self):
        with tmp_image((256, 256), format='png', color=(255, 0, 0)) as img:
            expected_req = ({'path':
                r'/service?LAYERs=bar&SERVICE=WMS&FORMAT=image%2Fpng'
                 '&REQUEST=GetMap&HEIGHT=100&SRS=EPSG%3A25832&styles='
                 '&VERSION=1.1.1&BBOX=0.0,3500000.0,150.0,3500100.0'
                 '&WIDTH=75'},
                {'body': img.read(), 'headers': {'content-type': 'image/png'}})
        with mock_httpd(('localhost', 42423), [expected_req]):
            resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetMap'
                '&LAYERS=direct&STYLES='
                '&WIDTH=100&HEIGHT=100&FORMAT=image/png'
                '&BBOX=-50,3500000,150,3500100&SRS=EPSG:25832'
                '&VERSION=1.1.0&TRANSPARENT=TRUE')
            eq_(resp.content_type, 'image/png')
            assert is_png(resp.body)
            colors = sorted(img_from_buf(resp.body).convert('RGBA').getcolors())
            # quarter is clipped, check if it's transparent
            eq_(colors[0][0], (25 * 100))
            eq_(colors[0][1][3], 0)
            eq_(colors[1], (75 * 100, (255, 0, 0, 255)))

    def test_clipped_bgcolor(self):
        with tmp_image((256, 256), format='png', color=(255, 0, 0)) as img:
            expected_req = ({'path':
                r'/service?LAYERs=bar&SERVICE=WMS&FORMAT=image%2Fpng'
                 '&REQUEST=GetMap&HEIGHT=100&SRS=EPSG%3A25832&styles='
                 '&VERSION=1.1.1&BBOX=0.0,3500000.0,100.0,3500100.0'
                 '&WIDTH=50'},
                {'body': img.read(), 'headers': {'content-type': 'image/png'}})
        with mock_httpd(('localhost', 42423), [expected_req]):
            resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetMap'
                '&LAYERS=direct&STYLES='
                '&WIDTH=100&HEIGHT=100&FORMAT=image/png'
                '&BBOX=-100,3500000,100,3500100&SRS=EPSG:25832'
                '&VERSION=1.1.0&TRANSPARENT=FALSE&BGCOLOR=0x00ff00')
            eq_(resp.content_type, 'image/png')
            assert is_png(resp.body)
            assert_colors_equal(img_from_buf(resp.body).convert('RGBA'),
                [(50 * 100, [255, 0, 0, 255]), (50 * 100, [0, 255, 0, 255])])