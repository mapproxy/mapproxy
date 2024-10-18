# This file is part of the MapProxy project.
# Copyright (C) 2024 terrestris <https://terrestris.de>
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
import sqlite3
import threading
import time

from io import BytesIO

from mapproxy.cache.mbtiles import MBTilesCache, MBTilesLevelCache
from mapproxy.cache.tile import Tile
from mapproxy.image import ImageSource
from mapproxy.test.helper import assert_files_in_dir, assert_permissions
from mapproxy.test.image import create_tmp_image_buf
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase

tile_image = create_tmp_image_buf((256, 256), color='blue')
tile_image2 = create_tmp_image_buf((256, 256), color='red')


class TestMBTileCache(TileCacheTestBase):
    def setup_method(self):
        TileCacheTestBase.setup_method(self)
        self.cache = MBTilesCache(os.path.join(self.cache_dir, 'tmp.mbtiles'))

    def teardown_method(self):
        if self.cache:
            self.cache.cleanup()
        TileCacheTestBase.teardown_method(self)

    def test_default_coverage(self):
        assert self.cache.coverage is None

    def test_load_empty_tileset(self):
        assert self.cache.load_tiles([Tile(None)]) is True
        assert self.cache.load_tiles([Tile(None), Tile(None), Tile(None)]) is True

    def test_load_more_than_2000_tiles(self):
        # prepare data
        for i in range(0, 2010):
            assert self.cache.store_tile(Tile((i, 0, 10),  ImageSource(BytesIO(b'foo'))))

        tiles = [Tile((i, 0, 10)) for i in range(0, 2010)]
        assert self.cache.load_tiles(tiles)

    def test_timeouts(self):
        self.cache._db_conn_cache.db = sqlite3.connect(self.cache.mbtile_file, timeout=0.05)

        def block():
            # block database by delaying the commit
            db = sqlite3.connect(self.cache.mbtile_file)
            cur = db.cursor()
            stmt = "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?,?,?,?)"
            cur.execute(stmt, (3, 1, 1, '1234'))
            time.sleep(0.2)
            db.commit()

        try:
            assert self.cache.store_tile(self.create_tile((0, 0, 1))) is True

            t = threading.Thread(target=block)
            t.start()
            time.sleep(0.05)
            assert self.cache.store_tile(self.create_tile((0, 0, 1))) is False
        finally:
            t.join()

        assert self.cache.store_tile(self.create_tile((0, 0, 1))) is True


class TestMBTileCachePermissions(TileCacheTestBase):
    def setup_method(self):
        TileCacheTestBase.setup_method(self)
        self.cache = MBTilesCache(os.path.join(self.cache_dir, 'tmp.mbtiles'), file_permissions='700')

    def teardown_method(self):
        if self.cache:
            self.cache.cleanup()
        TileCacheTestBase.teardown_method(self)

    def test_permissions(self):
        assert_permissions(self.cache.mbtile_file, '700')


class TestMBTileLevelCache(TileCacheTestBase):
    always_loads_metadata = True

    def setup_method(self):
        TileCacheTestBase.setup_method(self)
        self.cache = MBTilesLevelCache(self.cache_dir)

    def test_default_coverage(self):
        assert self.cache.coverage is None

    def test_level_files(self):
        assert_files_in_dir(self.cache_dir, [])

        self.cache.store_tile(self.create_tile((0, 0, 1)))
        assert_files_in_dir(self.cache_dir, ['1.mbtile'], glob='*.mbtile')

        self.cache.store_tile(self.create_tile((0, 0, 5)))
        assert_files_in_dir(self.cache_dir, ['1.mbtile', '5.mbtile'], glob='*.mbtile')

    def test_remove_level_files(self):
        self.cache.store_tile(self.create_tile((0, 0, 1)))
        self.cache.store_tile(self.create_tile((0, 0, 2)))
        assert_files_in_dir(self.cache_dir, ['1.mbtile', '2.mbtile'], glob='*.mbtile')

        self.cache.remove_level_tiles_before(1, timestamp=0)
        assert_files_in_dir(self.cache_dir, ['2.mbtile'], glob='*.mbtile')

    def test_remove_level_tiles_before(self):
        self.cache.store_tile(self.create_tile((0, 0, 1)))
        self.cache.store_tile(self.create_tile((0, 0, 2)))

        assert_files_in_dir(self.cache_dir, ['1.mbtile', '2.mbtile'], glob='*.mbtile')
        assert self.cache.is_cached(Tile((0, 0, 1)))

        self.cache.remove_level_tiles_before(1, timestamp=time.time() - 60)
        assert self.cache.is_cached(Tile((0, 0, 1)))

        self.cache.remove_level_tiles_before(1, timestamp=time.time() + 60)
        assert not self.cache.is_cached(Tile((0, 0, 1)))

        assert_files_in_dir(self.cache_dir, ['1.mbtile', '2.mbtile'], glob='*.mbtile')
        assert self.cache.is_cached(Tile((0, 0, 2)))

    def test_bulk_store_tiles_with_different_levels(self):
        self.cache.store_tiles([
            self.create_tile((0, 0, 1)),
            self.create_tile((0, 0, 2)),
            self.create_tile((1, 0, 2)),
            self.create_tile((1, 0, 1)),
        ], dimensions=None)

        assert_files_in_dir(self.cache_dir, ['1.mbtile', '2.mbtile'], glob='*.mbtile')
        assert self.cache.is_cached(Tile((0, 0, 1)))
        assert self.cache.is_cached(Tile((1, 0, 1)))
        assert self.cache.is_cached(Tile((0, 0, 2)))
        assert self.cache.is_cached(Tile((1, 0, 2)))
