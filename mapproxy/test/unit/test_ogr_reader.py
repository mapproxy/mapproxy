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

import os
from mapproxy.util.ogr import OGRShapeReader, libgdal
from nose.tools import eq_
from nose.plugins.skip import SkipTest

if not libgdal:
    raise SkipTest('libgdal not found')
    
polygon_file = os.path.join(os.path.dirname(__file__), 'polygons', 'polygons.shp')

class TestOGRShapeReader(object):
    def setup(self):
        self.reader = OGRShapeReader(polygon_file)
    def test_read_all(self):
        wkts = list(self.reader.wkts())
        eq_(len(wkts), 3)
        for wkt in wkts:
            assert wkt.startswith('POLYGON ('), 'unexpected WKT: %s' % wkt
    def test_read_filter(self):
        wkts = list(self.reader.wkts(where='name = "germany"'))
        eq_(len(wkts), 2)
        for wkt in wkts:
            assert wkt.startswith('POLYGON ('), 'unexpected WKT: %s' % wkt
    def test_read_filter_no_match(self):
        wkts = list(self.reader.wkts(where='name = "foo"'))
        eq_(len(wkts), 0)
        