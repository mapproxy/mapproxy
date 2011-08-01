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

from __future__ import with_statement

import os
import shutil
import tempfile
import time

from cStringIO import StringIO

from PIL import Image

from mapproxy.cache.tile import Tile
from mapproxy.cache.file import FileCache
from mapproxy.cache.mbtiles import MBTilesCache
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.test.image import create_tmp_image_buf, is_png

tile_image = create_tmp_image_buf((256, 256), color='blue')
tile_image2 = create_tmp_image_buf((256, 256), color='red')

def timestamp_is_now(timestamp, delta=5):
    return abs(timestamp - time.time()) <= delta

class TileCacheTestBase(object):
    def setup(self):
        self.cache_dir = tempfile.mkdtemp()
    
    def teardown(self):
        if hasattr(self, 'cache_dir') and os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)

    def create_tile(self, coord=(0, 0, 0)):
        return Tile(coord,
            ImageSource(tile_image,
                image_opts=ImageOptions(format='image/png')))
    
    def create_another_tile(self, coord=(0, 0, 0)):
        return Tile(coord,
            ImageSource(tile_image2,
                image_opts=ImageOptions(format='image/png')))
    
    def test_is_cached_miss(self):
        assert not self.cache.is_cached(Tile((0, 0, 0)))
    
    def test_is_cached_hit(self):
        tile = self.create_tile()
        self.create_cached_tile(tile)
        assert self.cache.is_cached(Tile((0, 0, 0)))
    
    def test_is_cached_none(self):
        assert self.cache.is_cached(Tile(None))

    def test_load_tile_not_cached(self):
        tile = Tile((0, 0, 0))
        assert not self.cache.load_tile(tile)
        assert tile.source is None
        assert tile.is_missing()
    
    def test_load_tile_cached(self):
        tile = self.create_tile()
        self.create_cached_tile(tile)
        tile = Tile((0, 0, 0))
        assert self.cache.load_tile(tile) == True
        assert not tile.is_missing()

    def test_load_stored_tile(self):
        tile = self.create_tile((5, 12, 2))
        self.cache.store_tile(tile)
        size = tile.size
        
        # check stored tile
        tile = Tile((5, 12, 2))
        assert tile.source is None
        assert self.cache.load_tile(tile)
        assert tile.source is not None
        assert tile.timestamp is None
        assert tile.size is None
        stored_size = len(tile.source.as_buffer().read())
        assert stored_size == size
        
        # check loading of metadata (timestamp, size)
        tile = Tile((5, 12, 2))
        assert tile.source is None
        assert self.cache.load_tile(tile, with_metadata=True)
        assert tile.source is not None
        if tile.timestamp:
            assert timestamp_is_now(tile.timestamp, delta=5)
        if tile.size:
            assert tile.size == size
        
    def test_overwrite_tile(self):
        tile = self.create_tile((5, 12, 2))
        self.cache.store_tile(tile)
        
        tile = Tile((5, 12, 2))
        self.cache.load_tile(tile)
        tile1_content = tile.source.as_buffer().read()
        assert tile1_content == tile_image.getvalue()
        
        tile = self.create_another_tile((5, 12, 2))
        self.cache.store_tile(tile)
        
        tile = Tile((5, 12, 2))
        self.cache.load_tile(tile)
        tile2_content = tile.source.as_buffer().read()
        assert tile2_content == tile_image2.getvalue()
        
        assert tile1_content != tile2_content

    def test_store_tile_already_stored(self):
        # tile object is marked as stored, do not save
        # (used for disable_storage)
        tile = Tile((0, 0, 0), ImageSource(StringIO('foo')))
        tile.stored = True
        self.cache.store_tile(tile)
        
        assert self.cache.is_cached(tile)
        
        tile = Tile((0, 0, 0))
        assert not self.cache.is_cached(tile)
    
    def test_remove(self):
        tile = self.create_tile((0, 0, 0))
        self.create_cached_tile(tile)
        assert self.cache.is_cached(Tile((0, 0, 0)))
        
        self.cache.remove_tile(self.create_tile())
        assert not self.cache.is_cached(Tile((0, 0, 0)))
    
    def create_cached_tile(self, tile):
        self.cache.store_tile(tile)
    
class TestFileTileCache(TileCacheTestBase):
    def setup(self):
        TileCacheTestBase.setup(self)
        self.cache = FileCache(self.cache_dir, 'png')
    
    def test_store_tile(self):
        tile = self.create_tile((5, 12, 2))
        self.cache.store_tile(tile)
        tile_location = os.path.join(self.cache_dir,
            '02', '000', '000', '005', '000', '000', '012.png' )
        assert os.path.exists(tile_location), tile_location
    
    def test_single_color_tile_store(self):
        img = Image.new('RGB', (256, 256), color='#ff0105')
        tile = Tile((0, 0, 0), ImageSource(img, image_opts=ImageOptions(format='image/png')))
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
        tile = Tile((0, 0, 0), ImageSource(img, image_opts=ImageOptions(format='image/png')))
        self.cache.link_single_color_images = True
        self.cache.store_tile(tile)
        assert self.cache.is_cached(tile)
        loc = self.cache.tile_location(tile)
        assert os.path.islink(loc)
        assert os.path.realpath(loc).endswith('ff0105ff.png')
        assert is_png(open(loc, 'rb'))

    def create_cached_tile(self, tile):
        loc = self.cache.tile_location(tile, create_dir=True)
        with open(loc, 'w') as f:
            f.write('foo')

class TestMBTileCache(TileCacheTestBase):
    def setup(self):
        TileCacheTestBase.setup(self)
        self.cache = MBTilesCache(os.path.join(self.cache_dir, 'tmp.mbtiles'))
        