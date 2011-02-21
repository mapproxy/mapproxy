# -:- encoding: utf8 -:-
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

import os
from mapproxy.platform.image import (
    Image,
    ImageDraw,
    ImageColor,
    ImageFont,
)
from mapproxy.image import ImageSource, ReadBufWrapper, is_single_color_image, merge_images
from mapproxy.image import _make_transparent as make_transparent
from mapproxy.image.message import message_image, TextDraw
from mapproxy.image.tile import TileMerger
from mapproxy.image.transform import ImageTransformer
from mapproxy.tilefilter import watermark_filter
from mapproxy.cache.tile import Tile
from mapproxy.test.image import is_png, is_jpeg, is_tiff, create_tmp_image_file, check_format, create_debug_img
from mapproxy.srs import SRS
from nose.tools import eq_

class TestImageSource(object):
    def setup(self):
        self.tmp_filename = create_tmp_image_file((100, 100))
    
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
    
    def test_from_non_seekable_file(self):
        with open(self.tmp_filename, 'rb') as tmp_file:
            data = tmp_file.read()
            
        class FileLikeDummy(object):
            # "file" without seek, like urlopen response
            def read(self):
                return data
        
        ir = ImageSource(FileLikeDummy(), 'png')
        assert ir.as_buffer(seekable=True).read() == data
        assert ir.as_image().size == (100, 100)
        assert ir.as_buffer().read() == data
        
    
    def test_output_formats(self):
        img = Image.new('RGB', (100, 100))
        for format in ['png', 'gif', 'tiff', 'jpeg', 'GeoTIFF', 'bmp']:
            ir = ImageSource(img, format)
            yield check_format, ir.as_buffer(), format
    
    def test_converted_output(self):
        ir = ImageSource(self.tmp_filename, 'png')
        assert is_png(ir.as_buffer())
        assert is_jpeg(ir.as_buffer(format='jpeg'))
        assert is_jpeg(ir.as_buffer())
        assert is_tiff(ir.as_buffer(format='tiff'))
        assert is_tiff(ir.as_buffer())
        
    def test_output_formats_png8(self):
        img = Image.new('RGBA', (100, 100))
        ir = ImageSource(img, format='png')
        img = Image.open(ir.as_buffer(paletted=True))
        assert img.mode == 'P'
        assert img.getpixel((0, 0)) == 255
        
    def test_output_formats_png24(self):
        img = Image.new('RGBA', (100, 100))
        ir = ImageSource(img, format='png')
        img = Image.open(ir.as_buffer(paletted=False))
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


class TestTextDraw(object):
    def test_ul(self):
        font = ImageFont.load_default()
        td = TextDraw('Hello', font)
        img = Image.new('RGB', (100, 100))
        draw = ImageDraw.Draw(img)
        total_box, boxes = td.text_boxes(draw, (100, 100))
        eq_(total_box, boxes[0])
        eq_(len(boxes), 1)
    
    def test_multiline_ul(self):
        font = ImageFont.load_default()
        td = TextDraw('Hello\nWorld', font)
        img = Image.new('RGB', (100, 100))
        draw = ImageDraw.Draw(img)
        total_box, boxes = td.text_boxes(draw, (100, 100))
        eq_(total_box, (5, 5, 35, 30))
        eq_(boxes, [(5, 5, 35, 16), (5, 19, 35, 30)])

    def test_multiline_lr(self):
        font = ImageFont.load_default()
        td = TextDraw('Hello\nWorld', font, placement='lr')
        img = Image.new('RGB', (100, 100))
        draw = ImageDraw.Draw(img)
        total_box, boxes = td.text_boxes(draw, (100, 100))
        eq_(total_box, (65, 70, 95, 95))
        eq_(boxes, [(65, 70, 95, 81), (65, 84, 95, 95)])

    def test_multiline_center(self):
        font = ImageFont.load_default()
        td = TextDraw('Hello\nWorld', font, placement='cc')
        img = Image.new('RGB', (100, 100))
        draw = ImageDraw.Draw(img)
        total_box, boxes = td.text_boxes(draw, (100, 100))
        eq_(total_box, (35, 38, 65, 63))
        eq_(boxes, [(35, 38, 65, 49), (35, 52, 65, 63)])

    def test_unicode(self):
        font = ImageFont.load_default()
        td = TextDraw(u'Héllö\nWørld', font, placement='cc')
        img = Image.new('RGB', (100, 100))
        draw = ImageDraw.Draw(img)
        total_box, boxes = td.text_boxes(draw, (100, 100))
        eq_(total_box, (35, 38, 65, 63))
        eq_(boxes, [(35, 38, 65, 49), (35, 52, 65, 63)])
    
    def _test_all(self):
        for x in 'c':
            for y in 'LR':
                yield self.check_placement, x, y

    def check_placement(self, x, y):
        font = ImageFont.load_default()
        td = TextDraw('Hello\nWorld\n%s %s' % (x, y), font, placement=x+y,
            padding=5, linespacing=2)
        img = Image.new('RGB', (100, 100))
        draw = ImageDraw.Draw(img)
        td.draw(draw, img.size)
        img.show()
    
    def test_transparent(self):
        font = ImageFont.load_default()
        td = TextDraw('Hello\nWorld', font, placement='cc')
        img = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        td.draw(draw, img.size)
        eq_(len(img.getcolors()), 2)
        # top color (bg) is transparent
        eq_(sorted(img.getcolors())[1][1], (0, 0, 0, 0))
        
        
class TestMessageImage(object):
    def test_blank(self):
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
        self.tile = Tile((0, 0, 0))
        self.filter = watermark_filter('Test')
    def test_filter(self):
        img = Image.new('RGB', (200, 200))
        orig_source = ImageSource(img)
        self.tile.source = orig_source
        filtered_tile = self.filter(self.tile)
        
        assert self.tile is filtered_tile
        assert orig_source != filtered_tile.source
        
        pil_img = filtered_tile.source.as_image()
        eq_(pil_img.getpixel((0, 0)), (0, 0, 0))

        colors = pil_img.getcolors()
        colors.sort()
        # most but not all parts are bg color
        assert 39950 > colors[-1][0] > 39000
        assert colors[-1][1] == (0, 0, 0)

    def test_filter_with_alpha(self):
        img = Image.new('RGBA', (200, 200), (10, 15, 20, 0))
        orig_source = ImageSource(img)
        self.tile.source = orig_source
        filtered_tile = self.filter(self.tile)
        
        assert self.tile is filtered_tile
        assert orig_source != filtered_tile.source
        
        pil_img = filtered_tile.source.as_image()
        eq_(pil_img.getpixel((0, 0)), (10, 15, 20, 0))

        colors = pil_img.getcolors()
        colors.sort()
        # most but not all parts are bg color
        assert 39950 > colors[-1][0] > 39000
        eq_(colors[-1][1], (10, 15, 20, 0))
        
class TestMergeAll(object):
    def setup(self):
        self.cleanup_tiles = []
    def test_full_merge(self):
        self.cleanup_tiles = [create_tmp_image_file((100, 100)) for _ in range(9)]
        self.tiles = [ImageSource(tile) for tile in self.cleanup_tiles]
        m = TileMerger(tile_grid=(3, 3), tile_size=(100, 100))
        result = m.merge(self.tiles)
        assert result.as_image().size == (300, 300)
    def test_one(self):
        self.cleanup_tiles = [create_tmp_image_file((100, 100))]
        self.tiles = [ImageSource(self.cleanup_tiles[0])]
        m = TileMerger(tile_grid=(1, 1), tile_size=(100, 100))
        result = m.merge(self.tiles)
        assert result.as_image().size == (100, 100)
    def test_missing_tiles(self):
        self.cleanup_tiles = [create_tmp_image_file((100, 100))]
        self.tiles = [ImageSource(self.cleanup_tiles[0])]
        self.tiles.extend([None]*8)
        m = TileMerger(tile_grid=(3, 3), tile_size=(100, 100))
        result = m.merge(self.tiles)
        assert result.as_image().size == (300, 300)
    def test_invalid_tile(self):
        self.cleanup_tiles = [create_tmp_image_file((100, 100)) for _ in range(9)]
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
        self.img = ImageSource(create_tmp_image_file((100, 100)),
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


class TestLayerMerge(object):
    def test_opacity_merge(self):
        img1 = ImageSource(Image.new('RGB', (10, 10), (255, 0, 255)))
        img2 = ImageSource(Image.new('RGB', (10, 10), (0, 255, 255)), opacity=0.5)
        
        result = merge_images([img1, img2], transparent=False)
        img = result.as_image()
        eq_(img.getpixel((0, 0)), (127, 127, 255))

    def test_opacity_merge_mixed_modes(self):
        img1 = ImageSource(Image.new('RGBA', (10, 10), (255, 0, 255, 255)))
        img2 = ImageSource(Image.new('RGB', (10, 10), (0, 255, 255)).convert('P'), opacity=0.5)
        
        result = merge_images([img1, img2])
        img = result.as_image()
        eq_(img.getpixel((0, 0)), (127, 127, 255, 255))

    def test_solid_merge(self):
        img1 = ImageSource(Image.new('RGB', (10, 10), (255, 0, 255)))
        img2 = ImageSource(Image.new('RGB', (10, 10), (0, 255, 255)))
        
        result = merge_images([img1, img2], transparent=False)
        img = result.as_image()
        eq_(img.getpixel((0, 0)), (0, 255, 255))
    

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
        

class TestSingleColorImage(object):
    def test_one_point(self):
        img = Image.new('RGB', (100, 100), color='#ff0000')
        draw = ImageDraw.Draw(img)
        draw.point((99, 99))
        del draw
        
        assert not is_single_color_image(img)
    
    def test_solid(self):
        img = Image.new('RGB', (100, 100), color='#ff0102')
        eq_(is_single_color_image(img), (255, 1, 2))
    
    def test_solid_w_alpha(self):
        img = Image.new('RGBA', (100, 100), color='#ff0102')
        eq_(is_single_color_image(img), (255, 1, 2, 255))
    
    def test_solid_paletted_image(self):
        img = Image.new('P', (100, 100), color=20)
        palette = []
        for i in range(256):
            palette.extend((i, i//2, i%3))
        img.putpalette(palette)
        eq_(is_single_color_image(img), (20, 10, 2))

class TestMakeTransparent(object):
    def _make_test_image(self):
        img = Image.new('RGB', (50, 50), (130, 140, 120))
        draw = ImageDraw.Draw(img)
        draw.rectangle((10, 10, 39, 39), fill=(130, 150, 120))
        return img
    
    def _make_transp_test_image(self):
        img = Image.new('RGBA', (50, 50), (130, 140, 120, 100))
        draw = ImageDraw.Draw(img)
        draw.rectangle((10, 10, 39, 39), fill=(130, 150, 120, 120))
        return img
    
    def test_result(self):
        img = self._make_test_image()
        img = make_transparent(img, (130, 150, 120), tolerance=5)
        assert img.mode == 'RGBA'
        assert img.size == (50, 50)
        colors = img.getcolors()
        assert colors == [(1600, (130, 140, 120, 255)), (900, (130, 150, 120, 0))]
    
    def test_with_color_fuzz(self):
        img = self._make_test_image()
        img = make_transparent(img, (128, 154, 121), tolerance=5)
        assert img.mode == 'RGBA'
        assert img.size == (50, 50)
        colors = img.getcolors()
        assert colors == [(1600, (130, 140, 120, 255)), (900, (130, 150, 120, 0))]

    def test_no_match(self):
        img = self._make_test_image()
        img = make_transparent(img, (130, 160, 120), tolerance=5)
        assert img.mode == 'RGBA'
        assert img.size == (50, 50)
        colors = img.getcolors()
        assert colors == [(1600, (130, 140, 120, 255)), (900, (130, 150, 120, 255))]

    def test_from_paletted(self):
        img = self._make_test_image().quantize(256)
        img = make_transparent(img, (130, 150, 120), tolerance=5)
        assert img.mode == 'RGBA'
        assert img.size == (50, 50)
        colors = img.getcolors()
        eq_(colors, [(1600, (130, 140, 120, 255)), (900, (130, 150, 120, 0))])
    
    def test_from_transparent(self):
        img = self._make_transp_test_image()
        img = make_transparent(img, (130, 150, 120, 120), tolerance=5)
        assert img.mode == 'RGBA'
        assert img.size == (50, 50)
        colors = img.getcolors()
        eq_(colors, [(1600, (130, 140, 120, 255)), (900, (130, 150, 120, 0))])
    