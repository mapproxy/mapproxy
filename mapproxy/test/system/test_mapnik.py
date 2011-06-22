# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

from mapproxy.test.system import module_setup, module_teardown, SystemTest

from mapproxy.platform.image import Image
from cStringIO import StringIO

from nose.tools import eq_

test_config = {}


mapnik_xml = """
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE Map>
<Map bgcolor="#ff0000" srs="+proj=latlong +datum=WGS84">
</Map>
""".strip()

mapnik_l2_xml = """
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE Map>
<Map bgcolor="#0000ff" srs="+proj=latlong +datum=WGS84">
</Map>
""".strip()

mapnik_transp_xml = """
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE Map>
<Map bgcolor="transparent" srs="+proj=latlong +datum=WGS84">
</Map>
""".strip()

def setup_module():

    try:
        import mapnik
        mapnik
    except ImportError:
        from nose.plugins.skip import SkipTest
        raise SkipTest('requires mapnik')
    
    module_setup(test_config, 'mapnik_source.yaml')
    with open(os.path.join(test_config['base_dir'], 'mapnik.xml'), 'w') as f:
        f.write(mapnik_xml)
    with open(os.path.join(test_config['base_dir'], 'mapnik-02.xml'), 'w') as f:
        f.write(mapnik_l2_xml)
    with open(os.path.join(test_config['base_dir'], 'mapnik-transparent.xml'), 'w') as f:
        f.write(mapnik_transp_xml)


def teardown_module():
    module_teardown(test_config)

class TestMapnikSource(SystemTest):
    config = test_config

    def test_get_map(self):
        req = (r'/service?LAYERs=mapnik&SERVICE=WMS&FORMAT=image%2Fpng'
                '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326'
                '&VERSION=1.1.1&BBOX=-90,-90,0,0&styles='
                '&WIDTH=200&')
        
        resp = self.app.get(req)
        data = StringIO(resp.body)
        img = Image.open(data)
        colors = img.getcolors(1)
        # map bg color
        eq_(colors[0], (40000, (255, 0, 0, 255)))
    
    def test_get_map_outside_coverage(self):
        req = (r'/service?LAYERs=mapnik&SERVICE=WMS&FORMAT=image%2Fpng'
                '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326'
                '&VERSION=1.1.1&BBOX=-175,-85,-172,-82&styles='
                '&WIDTH=200&&BGCOLOR=0x00ff00')
        
        resp = self.app.get(req)
        data = StringIO(resp.body)
        img = Image.open(data)
        colors = img.getcolors(1)
        # wms request bg color
        eq_(colors[0], (40000, (0, 255, 0)))

    def test_get_map_unknown_file(self):
        req = (r'/service?LAYERs=mapnik_unknown&SERVICE=WMS&FORMAT=image%2Fpng'
                '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326'
                '&VERSION=1.1.1&BBOX=-90,-90,0,0&styles='
                '&WIDTH=200&&BGCOLOR=0x00ff00')
        
        resp = self.app.get(req)
        assert 'unknown.xml' in resp.body, resp.body

    def test_get_map_transparent(self):
        req = (r'/service?LAYERs=mapnik_transparent&SERVICE=WMS&FORMAT=image%2Fpng'
                '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326'
                '&VERSION=1.1.1&BBOX=-90,-90,0,0&styles='
                '&WIDTH=200&transparent=True')
        
        resp = self.app.get(req)
        data = StringIO(resp.body)
        img = Image.open(data)
        colors = img.getcolors(1)
        eq_(colors[0], (40000, (0, 0, 0, 0)))

