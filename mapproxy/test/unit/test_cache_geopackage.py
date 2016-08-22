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
from mapproxy.cache.geopackage import GeopackageCache
from mapproxy.grid import TileGrid

test_config = {}

class TestGeopackageCache():
    table_name = 'cache'

    def test_bad_config_geopackage_srs(self):
        error_msg = None
        gpkg_file = os.path.join(os.path.join(os.path.dirname(__file__),
                                                              'fixture'),
                                 'cache.gpkg')
        table_name = 'cache'
        try:
            GeopackageCache(gpkg_file, TileGrid(srs=4326), table_name)
        except ValueError as ve:
            error_msg = ve
        assert "srs is improperly configured." in str(error_msg)

    def test_bad_config_geopackage_tile(self):
        error_msg = None
        gpkg_file = os.path.join(os.path.join(os.path.dirname(__file__),
                                                              'fixture'),
                                 'cache.gpkg')
        table_name = 'cache'
        try:
            GeopackageCache(gpkg_file, TileGrid(srs=900913, tile_size=(512, 512)), table_name)
        except ValueError as ve:
            error_msg = ve
        assert "tile_size is improperly configured." in str(error_msg)

    def test_bad_config_geopackage_res(self):
        error_msg = None
        gpkg_file = os.path.join(os.path.join(os.path.dirname(__file__),
                                              'fixture'),
                                 'cache.gpkg')
        table_name = 'cache'
        try:
            GeopackageCache(gpkg_file, TileGrid(srs=900913, res=[1000, 100, 10]), table_name)
        except ValueError as ve:
            error_msg = ve
        assert "res is improperly configured." in str(error_msg)