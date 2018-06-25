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

import pytest

from mapproxy.util.ogr import OGRShapeReader, libgdal


polygon_file = os.path.join(os.path.dirname(__file__), "polygons", "polygons.shp")


@pytest.mark.skipif(not libgdal, reason="libgdal not found")
class TestOGRShapeReader(object):

    @pytest.fixture
    def reader(self):
        return OGRShapeReader(polygon_file)

    def test_read_all(self, reader):
        wkts = list(reader.wkts())
        assert len(wkts) == 3
        for wkt in wkts:
            assert wkt.startswith(b"POLYGON ("), "unexpected WKT: %s" % wkt

    def test_read_filter(self, reader):
        wkts = list(reader.wkts(where="name = 'germany'"))
        assert len(wkts) == 2
        for wkt in wkts:
            assert wkt.startswith(b"POLYGON ("), "unexpected WKT: %s" % wkt

    def test_read_filter_no_match(self, reader):
        wkts = list(reader.wkts(where="name = 'foo'"))
        assert len(wkts) == 0
