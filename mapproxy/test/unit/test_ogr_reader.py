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
            assert wkt.startswith(b'POLYGON ('), 'unexpected WKT: %s' % wkt
    def test_read_filter(self):
        wkts = list(self.reader.wkts(where='name = "germany"'))
        eq_(len(wkts), 2)
        for wkt in wkts:
            assert wkt.startswith(b'POLYGON ('), 'unexpected WKT: %s' % wkt
    def test_read_filter_no_match(self):
        wkts = list(self.reader.wkts(where='name = "foo"'))
        eq_(len(wkts), 0)
