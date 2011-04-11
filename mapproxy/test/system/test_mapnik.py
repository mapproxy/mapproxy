# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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
        # wms reqeust bg color
        eq_(colors[0], (40000, (0, 255, 0)))

    def test_get_map_unknown_file(self):
        req = (r'/service?LAYERs=mapnik_unknown&SERVICE=WMS&FORMAT=image%2Fpng'
                '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326'
                '&VERSION=1.1.1&BBOX=-90,-90,0,0&styles='
                '&WIDTH=200&&BGCOLOR=0x00ff00')
        
        resp = self.app.get(req)
        assert 'unknown.xml' in resp.body, resp.body
    
    
    def test_get_map_with_level(self):
        req = (r'/service?LAYERs=mapnik_level&SERVICE=WMS&FORMAT=image%2Fpng'
                '&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326'
                '&VERSION=1.1.1&BBOX=-90,-90,0,0&styles='
                '&WIDTH=200&&BGCOLOR=0x00ff00')
        
        resp = self.app.get(req)
        data = StringIO(resp.body)
        img = Image.open(data)
        colors = img.getcolors(1)
        # wms reqeust bg color
        eq_(colors[0], (40000, (0, 0, 255, 255)))    
    