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

import calendar
from datetime import timezone, datetime
import os
import shutil
import sys
import tempfile
import time

from io import BytesIO

import pytest

from PIL import Image

from mapproxy.cache.file import FileCache
from mapproxy.cache.mbtiles import MBTilesCache
from mapproxy.cache.tile import Tile
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.test.image import create_tmp_image_buf, is_png


tile_image = create_tmp_image_buf((256, 256), color='blue')
tile_image2 = create_tmp_image_buf((256, 256), color='red')


class TileCacheTestBase(object):
    always_loads_metadata = False
    uses_utc = False

    cache = None  # set by subclasses

    def setup_method(self):
        self.cache_dir = tempfile.mkdtemp()

    def teardown_method(self):
        if hasattr(self.cache, 'cleanup'):
            self.cache.cleanup()
        if hasattr(self, 'cache_dir') and os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)

    def create_tile(self, coord=(3009, 589, 12)):
        return Tile(coord,
                    ImageSource(tile_image,
                                image_opts=ImageOptions(format='image/png')))

    def create_another_tile(self, coord=(3009, 589, 12)):
        return Tile(coord,
                    ImageSource(tile_image2,
                                image_opts=ImageOptions(format='image/png')))

    def test_is_cached_miss(self):
        assert not self.cache.is_cached(Tile((3009, 589, 12)))

    def test_is_cached_hit(self):
        tile = self.create_tile()
        self.create_cached_tile(tile)
        assert self.cache.is_cached(Tile((3009, 589, 12)))

    def test_is_cached_none(self):
        assert self.cache.is_cached(Tile(None))

    def test_load_tile_none(self):
        assert self.cache.load_tile(Tile(None))

    def test_load_tile_not_cached(self):
        tile = Tile((3009, 589, 12))
        assert not self.cache.load_tile(tile)
        assert tile.source is None
        assert tile.is_missing()

    def test_load_tile_cached(self):
        tile = self.create_tile()
        self.create_cached_tile(tile)
        tile = Tile((3009, 589, 12))
        assert self.cache.load_tile(tile) is True
        assert not tile.is_missing()

    def test_store_tiles(self):
        tiles = [self.create_tile((x, 589, 12)) for x in range(4)]
        tiles[0].stored = True
        self.cache.store_tiles(tiles, dimensions=None)

        tiles = [Tile((x, 589, 12)) for x in range(4)]
        assert tiles[0].is_missing()
        assert self.cache.load_tile(tiles[0]) is False
        assert tiles[0].is_missing()

        for tile in tiles[1:]:
            assert tile.is_missing()
            assert self.cache.load_tile(tile) is True
            assert not tile.is_missing()

    @pytest.mark.skipif(os.geteuid() == 0, reason="Test skipped for root user")
    def test_store_tiles_no_permissions(self):
        tiles = [self.create_tile((x, 589, 12)) for x in range(4)]
        tiles[0].stored = True

        if isinstance(self.cache, FileCache):
            # reinit cache with permission props
            TileCacheTestBase.teardown_method(self)
            self.cache = FileCache(self.cache_dir, 'png', directory_permissions='555')
            try:
                self.cache.store_tiles(tiles, dimensions=None)
            except Exception as e:
                assert 'Permission denied' == e.args[1]
            else:
                assert False, 'no PermissionError raised'
        elif isinstance(self.cache, MBTilesCache):
            # reinit cache with permission props
            self.cache.cleanup()
            TileCacheTestBase.teardown_method(self)
            self.cache = MBTilesCache(os.path.join(self.cache_dir, 'tmp.mbtiles'),
                                      directory_permissions='755', file_permissions='555')
            success = self.cache.store_tiles(tiles, dimensions=None)
            assert not success
            self.cache.cleanup()
        TileCacheTestBase.teardown_method(self)

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
        assert self.cache.load_tiles(tiles) is False
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
            now = time.time()
            if self.uses_utc:
                now = calendar.timegm(datetime.now(timezone.utc).timetuple())
            assert abs(tile.timestamp - now) <= 10
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
        tile = Tile((1234, 589, 12), ImageSource(BytesIO(b'foo')))
        tile.stored = True
        self.cache.store_tile(tile)

        assert self.cache.is_cached(tile)

        tile = Tile((1234, 589, 12))
        assert not self.cache.is_cached(tile)

    def test_remove(self):
        tile = self.create_tile((1, 0, 4))
        self.create_cached_tile(tile)
        assert self.cache.is_cached(Tile((1, 0, 4)))

        self.cache.remove_tile(Tile((1, 0, 4)))
        assert not self.cache.is_cached(Tile((1, 0, 4)))

        # check if we can recreate a removed tile
        tile = self.create_tile((1, 0, 4))
        self.create_cached_tile(tile)
        assert self.cache.is_cached(Tile((1, 0, 4)))

    def create_cached_tile(self, tile):
        self.cache.store_tile(tile)


class TestFileTileCache(TileCacheTestBase):
    def setup_method(self):
        TileCacheTestBase.setup_method(self)
        self.cache = FileCache(self.cache_dir, 'png')

    def test_default_coverage(self):
        assert self.cache.coverage is None

    def test_store_tile(self):
        tile = self.create_tile((5, 12, 4))
        self.cache.store_tile(tile)
        tile_location = os.path.join(self.cache_dir,
                                     '04', '000', '000', '005', '000', '000', '012.png')
        assert os.path.exists(tile_location), tile_location

    @pytest.mark.skipif(sys.platform == 'win32',
                        reason='link_single_color_tiles not supported on windows')
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

        tile3 = Tile((0, 0, 2), ImageSource(img))
        self.cache.link_single_color_images = 'hardlink'
        self.cache.store_tile(tile3)
        assert self.cache.is_cached(tile3)
        loc3 = self.cache.tile_location(tile3)
        assert is_png(open(loc3, 'rb'))

        assert loc != loc3
        assert os.path.samefile(loc, loc3)
        loc3stat = os.stat(loc3)
        assert loc3stat.st_nlink == 2

        tile4 = Tile((0, 0, 1), ImageSource(img))
        self.cache.link_single_color_images = 'symlink'
        self.cache.store_tile(tile4)
        assert self.cache.is_cached(tile4)
        loc4 = self.cache.tile_location(tile4)
        assert os.path.islink(loc4)
        assert os.path.realpath(loc4).endswith('ff0105.png')
        assert is_png(open(loc4, 'rb'))

        assert loc != loc4
        assert os.path.samefile(loc, loc4)

    @pytest.mark.skipif(sys.platform == 'win32',
                        reason='link_single_color_tiles not supported on windows')
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

        tile2 = Tile((0, 0, 2), ImageSource(img))
        self.cache.link_single_color_images = 'hardlink'
        self.cache.store_tile(tile2)
        assert self.cache.is_cached(tile2)
        loc2 = self.cache.tile_location(tile2)
        assert is_png(open(loc2, 'rb'))

        assert loc != loc2
        assert os.path.samefile(loc, loc2)
        loc2stat = os.stat(loc2)
        assert loc2stat.st_nlink == 2

    def test_load_metadata_missing_tile(self):
        tile = Tile((0, 0, 0))
        self.cache.load_tile_metadata(tile)
        assert tile.timestamp == 0
        assert tile.size == 0

    def create_cached_tile(self, tile):
        loc = self.cache.tile_location(tile, create_dir=True)
        with open(loc, 'wb') as f:
            f.write(b'foo')

    @pytest.mark.parametrize('layout,tile_coord,path', [
        ['mp', (12345, 67890,  2), '/tmp/foo/02/0001/2345/0006/7890.png'],
        ['mp', (12345, 67890, 12), '/tmp/foo/12/0001/2345/0006/7890.png'],

        ['tc', (12345, 67890,  2), '/tmp/foo/02/000/012/345/000/067/890.png'],
        ['tc', (12345, 67890, 12), '/tmp/foo/12/000/012/345/000/067/890.png'],

        ['tms', (12345, 67890,  2), '/tmp/foo/2/12345/67890.png'],
        ['tms', (12345, 67890, 12), '/tmp/foo/12/12345/67890.png'],

        ['quadkey', (0, 0, 0), '/tmp/foo/.png'],
        ['quadkey', (0, 0, 1), '/tmp/foo/0.png'],
        ['quadkey', (1, 1, 1), '/tmp/foo/3.png'],
        ['quadkey', (12345, 67890, 12), '/tmp/foo/200200331021.png'],

        ['arcgis', (1, 2, 3), '/tmp/foo/L03/R00000002/C00000001.png'],
        ['arcgis', (9, 2, 3), '/tmp/foo/L03/R00000002/C00000009.png'],
        ['arcgis', (10, 2, 3), '/tmp/foo/L03/R00000002/C0000000a.png'],
        ['arcgis', (12345, 67890, 12), '/tmp/foo/L12/R00010932/C00003039.png'],
    ])
    def test_tile_location(self, layout, tile_coord, path):
        cache = FileCache('/tmp/foo', 'png', directory_layout=layout)
        assert os.path.abspath(cache.tile_location(Tile(tile_coord))) == os.path.abspath(path)

    @pytest.mark.parametrize('layout,level,path', [
        ['mp', 2, '/tmp/foo/02'],
        ['mp', 12, '/tmp/foo/12'],

        ['tc',  2, '/tmp/foo/02'],
        ['tc', 12, '/tmp/foo/12'],

        ['tms',  '2', '/tmp/foo/2'],
        ['tms', 12, '/tmp/foo/12'],

        ['arcgis', 3, '/tmp/foo/L03'],
        ['arcgis', 3, '/tmp/foo/L03'],
        ['arcgis', 3, '/tmp/foo/L03'],
        ['arcgis', 12, '/tmp/foo/L12'],
    ])
    def test_level_location(self, layout, level, path):
        cache = FileCache('/tmp/foo', 'png', directory_layout=layout)
        assert os.path.abspath(cache.level_location(level)) == os.path.abspath(path)

    def test_level_location_quadkey(self):
        cache = FileCache('/tmp/foo', 'png', directory_layout='quadkey')
        with pytest.raises(NotImplementedError):
            cache.level_location(0)


class TestQuadkeyFileTileCache(TileCacheTestBase):
    def setup_method(self):
        TileCacheTestBase.setup_method(self)
        self.cache = FileCache(self.cache_dir, 'png', directory_layout='quadkey')

    def test_default_coverage(self):
        assert self.cache.coverage is None

    def test_store_tile(self):
        tile = self.create_tile((3, 4, 2))
        self.cache.store_tile(tile)
        tile_location = os.path.join(self.cache_dir, '11.png')
        assert os.path.exists(tile_location), tile_location
