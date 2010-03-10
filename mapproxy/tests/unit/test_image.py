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

from __future__ import with_statement
import Image
import os
import sys
from mapproxy.core.image import ImageSource, message_image, TileMerger, ReadBufWrapper
from mapproxy.core.tilefilter import watermark_filter, PNGQuantFilter
from mapproxy.core.cache import _Tile
from mapproxy.tests.image import is_png, create_tmp_image, check_format, create_debug_img
from nose.tools import eq_

class TestImageSource(object):
    def setup(self):
        self.tmp_filename = create_tmp_image((100, 100))
    
    def teardown(self):
        os.remove(self.tmp_filename)
        
    def test_from_filename(self):
        ir = ImageSource(self.tmp_filename, 'png')
        assert is_png(ir.as_buffer())
        assert ir.as_image().size == (100, 100)

    def test_from_file(self):
        with open(self.tmp_filename, 'rb') as tmp_file:
            ir = ImageSource(tmp_file, 'png')
            assert ir.as_buffer() == tmp_file
            assert ir.as_image().size == (100, 100)

    def test_from_image(self):
        img = Image.new('RGBA', (100, 100))
        ir = ImageSource(img, 'png')
        assert ir.as_image() == img
        assert is_png(ir.as_buffer())
    
    def test_output_formats(self):
        img = Image.new('RGB', (100, 100))
        for format in ['png', 'gif', 'tiff', 'jpeg', 'GeoTIFF', 'bmp']:
            ir = ImageSource(img, format)
            yield check_format, ir.as_buffer(), format
    
    def test_output_formats_png8(self):
        img = Image.new('RGBA', (100, 100))
        ir = ImageSource(img, format='png8')
        img = Image.open(ir.as_buffer())
        assert img.mode == 'P'
        
    def test_output_formats_png24(self):
        img = Image.new('RGBA', (100, 100))
        ir = ImageSource(img, format='png24')
        img = Image.open(ir.as_buffer())
        assert img.mode == 'RGBA'
        assert img.getpixel((0, 0)) == (0, 0, 0, 0)

class ROnly(object):
    def __init__(self):
        self.data = ['Hello World!']
    def read(self):
        if self.data:
            return self.data.pop()
        return ''
    def __iter__(self):
        it = iter(self.data)
        self.data = []
        return it

class TestReadBufWrapper(object):
    def setup(self):
        rbuf = ROnly()
        self.rbuf_wrapper = ReadBufWrapper(rbuf)
    def test_read(self):
        assert self.rbuf_wrapper.read() == 'Hello World!'
        self.rbuf_wrapper.seek(0)
        eq_(self.rbuf_wrapper.read(), '')
    def test_seek_read(self):
        self.rbuf_wrapper.seek(0)
        assert self.rbuf_wrapper.read() == 'Hello World!'
        self.rbuf_wrapper.seek(0)
        assert self.rbuf_wrapper.read() == 'Hello World!'
    def test_iter(self):
        data = list(self.rbuf_wrapper)
        eq_(data, ['Hello World!'])
        self.rbuf_wrapper.seek(0)
        data = list(self.rbuf_wrapper)
        eq_(data, [])
    def test_seek_iter(self):
        self.rbuf_wrapper.seek(0)
        data = list(self.rbuf_wrapper)
        eq_(data, ['Hello World!'])
        self.rbuf_wrapper.seek(0)
        data = list(self.rbuf_wrapper)
        eq_(data, ['Hello World!'])
    def test_hasattr(self):
        assert hasattr(self.rbuf_wrapper, 'seek')
        assert hasattr(self.rbuf_wrapper, 'readline')


class TestMessageImage(object):
    def test_blank(self):
        # import nose.tools; nose.tools.set_trace()
        img = message_image('', size=(100, 150), format='png', bgcolor='#113399')
        assert isinstance(img, ImageSource)
        eq_(img.size, (100, 150))
        pil_img = img.as_image()
        eq_(pil_img.getpixel((0, 0)), ImageColor.getrgb('#113399'))
        # 3 values in histogram (RGB)
        assert [x for x in pil_img.histogram() if x > 0] == [15000, 15000, 15000]
    def test_message(self):
        img = message_image('test', size=(100, 150), format='png', bgcolor='#113399')
        assert isinstance(img, ImageSource)
        assert img.size == (100, 150)
        # 6 values in histogram (3xRGB for background, 3xRGB for text message)
        eq_([x for x in img.as_image().histogram() if x > 10],
             [14923, 77, 14923, 77, 14923, 77])
    def test_transparent(self):
        img = message_image('', size=(100, 150), format='png', transparent=True)
        assert isinstance(img, ImageSource)
        assert img.size == (100, 150)
        pil_img = img.as_image()
        eq_(pil_img.getpixel((0, 0)), (255, 255, 255, 0))
        # 6 values in histogram (3xRGB for background, 3xRGB for text message)
        assert [x for x in pil_img.histogram() if x > 0] == \
               [15000, 15000, 15000, 15000]


class TestWatermarkTileFilter(object):
    def setup(self):
        from mapproxy.core.cache import _Tile
        self.tile = _Tile((0, 0, 0))
        self.filter = watermark_filter('Test')
    def test_filter(self):
        img = Image.new('RGB', (200, 200))
        orig_source = ImageSource(img)
        self.tile.source = orig_source
        filtered_tile = self.filter(self.tile)
        
        assert self.tile is filtered_tile
        assert orig_source != filtered_tile.source
        
        pil_img = filtered_tile.source.as_image()
        eq_(pil_img.getpixel((0, 0)), (0, 0, 0, 255))
        # 6 values in histogram (3xRGB for background, 3xRGB for text message)
        eq_([x for x in pil_img.histogram() if x > 0],
               [40000, 40000, 40000, 227, 37, 64, 39672])
        
class TestMergeAll(object):
    def setup(self):
        self.cleanup_tiles = []
    def test_full_merge(self):
        self.cleanup_tiles = [create_tmp_image((100, 100)) for _ in range(9)]
        self.tiles = [ImageSource(tile) for tile in self.cleanup_tiles]
        m = TileMerger(tile_grid=(3, 3), tile_size=(100, 100))
        result = m.merge(self.tiles)
        assert result.as_image().size == (300, 300)
    def test_one(self):
        self.cleanup_tiles = [create_tmp_image((100, 100))]
        self.tiles = [ImageSource(self.cleanup_tiles[0])]
        m = TileMerger(tile_grid=(1, 1), tile_size=(100, 100))
        result = m.merge(self.tiles)
        assert result.as_image().size == (100, 100)
    def test_missing_tiles(self):
        self.cleanup_tiles = [create_tmp_image((100, 100))]
        self.tiles = [ImageSource(self.cleanup_tiles[0])]
        self.tiles.extend([None]*8)
        m = TileMerger(tile_grid=(3, 3), tile_size=(100, 100))
        result = m.merge(self.tiles)
        assert result.as_image().size == (300, 300)
    def test_invalid_tile(self):
        self.cleanup_tiles = [create_tmp_image((100, 100)) for _ in range(9)]
        self.tiles = [ImageSource(tile) for tile in self.cleanup_tiles]
        invalid_tile = self.tiles[0].source
        with open(invalid_tile, 'w') as tmp:
            tmp.write('invalid')
        m = TileMerger(tile_grid=(3, 3), tile_size=(100, 100))
        result = m.merge(self.tiles)
        assert result.as_image().size == (300, 300)
        assert not os.path.isfile(invalid_tile)
    def test_none_merge(self):
        tiles = [None]
        m = TileMerger(tile_grid=(1, 1), tile_size=(100, 100))
        result = m.merge(tiles)
        assert result.as_image().size == (100, 100)
    def teardown(self):
        for tile_fname in self.cleanup_tiles:
            if tile_fname and os.path.isfile(tile_fname):
                os.remove(tile_fname)

class TestGetCrop(object):
    def setup(self):
        self.img = ImageSource(create_tmp_image((100, 100)),
                               format='png', size=(100, 100))
    def test_perfect_match(self):
        bbox = (-10, -5, 30, 35)
        transformer = ImageTransformer(SRS(4326), SRS(4326))
        result = transformer.transform(self.img, bbox, (100, 100), bbox)
        assert self.img == result
    def test_simple_resize(self):
        bbox = (-10, -5, 30, 35)
        transformer = ImageTransformer(SRS(4326), SRS(4326))
        result = transformer.transform(self.img, bbox, (200, 200), bbox)
        assert result.as_image().size == (200, 200)

from mapproxy.core.srs import SRS
from mapproxy.core.image import ImageTransformer 

import ImageColor

class TestTransform(object):
    def setup(self):
        self.src_img = ImageSource(create_debug_img((200, 200), transparent=False))
        self.src_srs = SRS(31467)
        self.dst_size = (100, 150)
        self.dst_srs = SRS(4326)
        self.dst_bbox = (0.2, 45.1, 8.3, 53.2)
        self.src_bbox = self.dst_srs.transform_bbox_to(self.src_srs, self.dst_bbox)
    def test_transform(self, mesh_div=4):
        transformer = ImageTransformer(self.src_srs, self.dst_srs, mesh_div=mesh_div)
        result = transformer.transform(self.src_img, self.src_bbox, self.dst_size, self.dst_bbox)
        assert isinstance(result, ImageSource)
        assert result.as_image() != self.src_img
        assert result.size == (100, 150)
    
    def _test_compare_mesh_div(self):
        """
        Create transformations with different div values.
        """
        for div in [1, 2, 4, 6, 8, 12, 16]:
            transformer = ImageTransformer(self.src_srs, self.dst_srs, mesh_div=div)
            result = transformer.transform(self.src_img, self.src_bbox,
                                           self.dst_size, self.dst_bbox)
            result.as_image().save('/tmp/transform-%d.png' % (div,))
        
