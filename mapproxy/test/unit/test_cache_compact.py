# This file is part of the MapProxy project.
# Copyright (C) 2016 Omniscale <http://omniscale.de>
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
import time
import sqlite3
import threading

from io import BytesIO

from mapproxy.image import ImageSource
from mapproxy.cache.compact import CompactCache
from mapproxy.cache.tile import Tile
from mapproxy.grid import tile_grid, TileGrid
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase

from nose.tools import eq_

class TestCompactCache(TileCacheTestBase):

    always_loads_metadata = True

    def setup(self):
        TileCacheTestBase.setup(self)
        self.cache = CompactCache(
            cache_dir=self.cache_dir,
        )
