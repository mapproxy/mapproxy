# This file is part of the MapProxy project.
# Copyright (C) 2011-2013 Omniscale <http://omniscale.de>
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
import shutil
import threading
import tempfile
import time
import sqlite3

from io import BytesIO

from PIL import Image

from mapproxy.cache.tile import Tile
from mapproxy.cache.file import FileCache
from mapproxy.cache.mbtiles import MBTilesCache, MBTilesLevelCache
from mapproxy.cache.base import CacheBackendError
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.test.image import create_tmp_image_buf, is_png

from nose.tools import eq_, assert_raises

tile_image = create_tmp_image_buf((256, 256), color='blue')
tile_image2 = create_tmp_image_buf((256, 256), color='red')

def timestamp_is_now(timestamp, delta=5):
    return abs(timestamp - time.time()) <= delta

class TileCacheTestBase(object):
    always_loads_metadata = False

    def setup(self):
        self.cache_dir = tempfile.mkdtemp()

    def teardown(self):
        if hasattr(self, 'cache_dir') and os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)

    def create_tile(self, coord=(0, 0, 4)):
        return Tile(coord,
            ImageSource(tile_image,
                image_opts=ImageOptions(format='image/png')))

    def create_another_tile(self, coord=(0, 0, 4)):
        return Tile(coord,
            ImageSource(tile_image2,
                image_opts=ImageOptions(format='image/png')))

    def test_is_cached_miss(self):
        assert not self.cache.is_cached(Tile((0, 0, 4)))

    def test_is_cached_hit(self):
        tile = self.create_tile()
        self.create_cached_tile(tile)
        assert self.cache.is_cached(Tile((0, 0, 4)))

    def test_is_cached_none(self):
        assert self.cache.is_cached(Tile(None))

    def test_load_tile_none(self):
        assert self.cache.load_tile(Tile(None))

    def test_load_tile_not_cached(self):
        tile = Tile((0, 0, 4))
        assert not self.cache.load_tile(tile)
        assert tile.source is None
        assert tile.is_missing()

    def test_load_tile_cached(self):
        tile = self.create_tile()
        self.create_cached_tile(tile)
        tile = Tile((0, 0, 4))
        assert self.cache.load_tile(tile) == True
        assert not tile.is_missing()

    def test_store_tiles(self):
        tiles = [self.create_tile((x, 0, 4)) for x in range(4)]
        tiles[0].stored = True
        self.cache.store_tiles(tiles)

        tiles = [Tile((x, 0, 4)) for x in range(4)]
        assert tiles[0].is_missing()
        assert self.cache.load_tile(tiles[0]) == False
        assert tiles[0].is_missing()

        for tile in tiles[1:]:
            assert tile.is_missing()
            assert self.cache.load_tile(tile) == True
            assert not tile.is_missing()

    def test_load_tiles_cached(self):
        self.cache.store_tile(self.create_tile((0, 0, 1)))
        self.cache.store_tile(self.create_tile((0, 1, 1)))
        tiles = [Tile((0, 0, 1)), Tile((0, 1, 1))]
        assert self.cache.load_tiles(tiles)

        assert not tiles[0].is_missing()
        assert not tiles[1].is_missing()

    def test_load_tiles_mixed(self):
        tile = self.create_tile((1, 0, 4))
        self.create_cached_tile(tile)
        tiles = [Tile(None), Tile((0, 0, 4)), Tile((1, 0, 4))]
        assert self.cache.load_tiles(tiles) == False
        assert not tiles[0].is_missing()
        assert tiles[1].is_missing()
        assert not tiles[2].is_missing()

    def test_load_stored_tile(self):
        tile = self.create_tile((5, 12, 4))
        self.cache.store_tile(tile)
        size = tile.size

        # check stored tile
        tile = Tile((5, 12, 4))
        assert tile.source is None

        assert self.cache.load_tile(tile)
        if not self.always_loads_metadata:
            assert tile.source is not None
            assert tile.timestamp is None
            assert tile.size is None
        stored_size = len(tile.source.as_buffer().read())
        assert stored_size == size

        # check loading of metadata (timestamp, size)
        tile = Tile((5, 12, 4))
        assert tile.source is None
        assert self.cache.load_tile(tile, with_metadata=True)
        assert tile.source is not None
        if tile.timestamp:
            assert timestamp_is_now(tile.timestamp, delta=10)
        if tile.size:
            assert tile.size == size

    def test_overwrite_tile(self):
        tile = self.create_tile((5, 12, 4))
        self.cache.store_tile(tile)

        tile = Tile((5, 12, 4))
        self.cache.load_tile(tile)
        tile1_content = tile.source.as_buffer().read()
        assert tile1_content == tile_image.getvalue()

        tile = self.create_another_tile((5, 12, 4))
        self.cache.store_tile(tile)

        tile = Tile((5, 12, 4))
        self.cache.load_tile(tile)
        tile2_content = tile.source.as_buffer().read()
        assert tile2_content == tile_image2.getvalue()

        assert tile1_content != tile2_content

    def test_store_tile_already_stored(self):
        # tile object is marked as stored,
        # check that is is not stored 'again'
        # (used for disable_storage)
        tile = Tile((0, 0, 4), ImageSource(BytesIO(b'foo')))
        tile.stored = True
        self.cache.store_tile(tile)

        assert self.cache.is_cached(tile)

        tile = Tile((0, 0, 4))
        assert not self.cache.is_cached(tile)

    def test_remove(self):
        tile = self.create_tile((1, 0, 4))
        self.create_cached_tile(tile)
        assert self.cache.is_cached(Tile((1, 0, 4)))

        self.cache.remove_tile(Tile((1, 0, 4)))
        assert not self.cache.is_cached(Tile((1, 0, 4)))

    def create_cached_tile(self, tile):
        self.cache.store_tile(tile)

class TestFileTileCache(TileCacheTestBase):
    def setup(self):
        TileCacheTestBase.setup(self)
        self.cache = FileCache(self.cache_dir, 'png')

    def test_store_tile(self):
        tile = self.create_tile((5, 12, 4))
        self.cache.store_tile(tile)
        tile_location = os.path.join(self.cache_dir,
            '04', '000', '000', '005', '000', '000', '012.png' )
        assert os.path.exists(tile_location), tile_location

    def test_single_color_tile_store(self):
        img = Image.new('RGB', (256, 256), color='#ff0105')
        tile = Tile((0, 0, 4), ImageSource(img, image_opts=ImageOptions(format='image/png')))
        self.cache.link_single_color_images = True
        self.cache.store_tile(tile)
        assert self.cache.is_cached(tile)
        loc = self.cache.tile_location(tile)
        assert os.path.islink(loc)
        assert os.path.realpath(loc).endswith('ff0105.png')
        assert is_png(open(loc, 'rb'))

        tile2 = Tile((0, 0, 1), ImageSource(img))
        self.cache.store_tile(tile2)
        assert self.cache.is_cached(tile2)
        loc2 = self.cache.tile_location(tile2)
        assert os.path.islink(loc2)
        assert os.path.realpath(loc2).endswith('ff0105.png')
        assert is_png(open(loc2, 'rb'))

        assert loc != loc2
        assert os.path.samefile(loc, loc2)

    def test_single_color_tile_store_w_alpha(self):
        img = Image.new('RGBA', (256, 256), color='#ff0105')
        tile = Tile((0, 0, 4), ImageSource(img, image_opts=ImageOptions(format='image/png')))
        self.cache.link_single_color_images = True
        self.cache.store_tile(tile)
        assert self.cache.is_cached(tile)
        loc = self.cache.tile_location(tile)
        assert os.path.islink(loc)
        assert os.path.realpath(loc).endswith('ff0105ff.png')
        assert is_png(open(loc, 'rb'))

    def test_load_metadata_missing_tile(self):
        tile = Tile((0, 0, 0))
        self.cache.load_tile_metadata(tile)
        assert tile.timestamp == 0
        assert tile.size == 0

    def create_cached_tile(self, tile):
        loc = self.cache.tile_location(tile, create_dir=True)
        with open(loc, 'wb') as f:
            f.write(b'foo')


class TestMBTileCache(TileCacheTestBase):
    def setup(self):
        TileCacheTestBase.setup(self)
        self.cache = MBTilesCache(os.path.join(self.cache_dir, 'tmp.mbtiles'))

    def test_load_empty_tileset(self):
        assert self.cache.load_tiles([Tile(None)]) == True
        assert self.cache.load_tiles([Tile(None), Tile(None), Tile(None)]) == True

    def test_load_1001_tiles(self):
        assert_raises(CacheBackendError, self.cache.load_tiles, [Tile((19, 1, 1))] * 1001)

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
            assert self.cache.store_tile(self.create_tile((0, 0, 1))) == True

            t = threading.Thread(target=block)
            t.start()
            time.sleep(0.05)
            assert self.cache.store_tile(self.create_tile((0, 0, 1))) == False
        finally:
            t.join()

        assert self.cache.store_tile(self.create_tile((0, 0, 1))) == True


class TestQuadkeyFileTileCache(TileCacheTestBase):
    def setup(self):
        TileCacheTestBase.setup(self)
        self.cache = FileCache(self.cache_dir, 'png', directory_layout='quadkey')

    def test_store_tile(self):
        tile = self.create_tile((3, 4, 2))
        self.cache.store_tile(tile)
        tile_location = os.path.join(self.cache_dir, '11.png' )
        assert os.path.exists(tile_location), tile_location


class TestMBTileLevelCache(TileCacheTestBase):
    always_loads_metadata = True

    def setup(self):
        TileCacheTestBase.setup(self)
        self.cache = MBTilesLevelCache(self.cache_dir)

    def test_level_files(self):
        eq_(os.listdir(self.cache_dir), [])

        self.cache.store_tile(self.create_tile((0, 0, 1)))
        eq_(os.listdir(self.cache_dir), ['1.mbtile'])

        self.cache.store_tile(self.create_tile((0, 0, 5)))
        eq_(sorted(os.listdir(self.cache_dir)), ['1.mbtile', '5.mbtile'])

    def test_remove_level_files(self):
        self.cache.store_tile(self.create_tile((0, 0, 1)))
        self.cache.store_tile(self.create_tile((0, 0, 2)))
        eq_(sorted(os.listdir(self.cache_dir)), ['1.mbtile', '2.mbtile'])

        self.cache.remove_level_tiles_before(1, timestamp=0)
        eq_(os.listdir(self.cache_dir), ['2.mbtile'])

    def test_remove_level_tiles_before(self):
        self.cache.store_tile(self.create_tile((0, 0, 1)))
        self.cache.store_tile(self.create_tile((0, 0, 2)))

        eq_(sorted(os.listdir(self.cache_dir)), ['1.mbtile', '2.mbtile'])
        assert self.cache.is_cached(Tile((0, 0, 1)))

        self.cache.remove_level_tiles_before(1, timestamp=time.time() - 60)
        assert self.cache.is_cached(Tile((0, 0, 1)))

        self.cache.remove_level_tiles_before(1, timestamp=time.time() + 60)
        assert not self.cache.is_cached(Tile((0, 0, 1)))

        eq_(sorted(os.listdir(self.cache_dir)), ['1.mbtile', '2.mbtile'])
        assert self.cache.is_cached(Tile((0, 0, 2)))
