# -:- encoding: utf8 -:-
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

from __future__ import with_statement

import os
from io import BytesIO
from mapproxy.compat.image import Image, ImageDraw
from mapproxy.image import (
    ImageSource,
    BlankImageSource,
    ReadBufWrapper,
    is_single_color_image,
    peek_image_format,
    _make_transparent as make_transparent,
    SubImageSource,
    img_has_transparency,
    quantize,
)
from mapproxy.image.merge import merge_images, BandMerger
from mapproxy.image.opts import ImageOptions
from mapproxy.image.tile import TileMerger, TileSplitter
from mapproxy.image.transform import ImageTransformer
from mapproxy.test.image import is_png, is_jpeg, is_tiff, create_tmp_image_file, check_format, create_debug_img, create_image
from mapproxy.srs import SRS
from nose.tools import eq_
from mapproxy.test.image import assert_img_colors_eq
from nose.plugins.skip import SkipTest


PNG_FORMAT = ImageOptions(format='image/png')
JPEG_FORMAT = ImageOptions(format='image/jpeg')
TIFF_FORMAT = ImageOptions(format='image/tiff')

class TestImageSource(object):
    def setup(self):
        self.tmp_filename = create_tmp_image_file((100, 100))

    def teardown(self):
        os.remove(self.tmp_filename)

    def test_from_filename(self):
        ir = ImageSource(self.tmp_filename, PNG_FORMAT)
        assert is_png(ir.as_buffer())
        assert ir.as_image().size == (100, 100)

    def test_from_file(self):
        with open(self.tmp_filename, 'rb') as tmp_file:
            ir = ImageSource(tmp_file, 'png')
            assert ir.as_buffer() == tmp_file
            assert ir.as_image().size == (100, 100)

    def test_from_image(self):
        img = Image.new('RGBA', (100, 100))
        ir = ImageSource(img, (100, 100), PNG_FORMAT)
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
            ir = ImageSource(img, (100, 100), image_opts=ImageOptions(format=format))
            yield check_format, ir.as_buffer(), format

    def test_converted_output(self):
        ir = ImageSource(self.tmp_filename, (100, 100), PNG_FORMAT)
        assert is_png(ir.as_buffer())
        assert is_jpeg(ir.as_buffer(JPEG_FORMAT))
        assert is_jpeg(ir.as_buffer())
        assert is_tiff(ir.as_buffer(TIFF_FORMAT))
        assert is_tiff(ir.as_buffer())


    def test_output_formats_greyscale_png(self):
        img = Image.new('L', (100, 100))
        ir = ImageSource(img, image_opts=PNG_FORMAT)
        img = Image.open(ir.as_buffer(ImageOptions(colors=256, transparent=True, format='image/png')))
        assert img.mode == 'P'
        assert img.getpixel((0, 0)) == 255

    def test_output_formats_greyscale_alpha_png(self):
        img = Image.new('LA', (100, 100))
        ir = ImageSource(img, image_opts=PNG_FORMAT)
        img = Image.open(ir.as_buffer(ImageOptions(colors=256, transparent=True, format='image/png')))
        assert img.mode == 'LA'
        assert img.getpixel((0, 0)) == (0, 0)

    def test_output_formats_png8(self):
        img = Image.new('RGBA', (100, 100))
        ir = ImageSource(img, image_opts=PNG_FORMAT)
        img = Image.open(ir.as_buffer(ImageOptions(colors=256, transparent=True, format='image/png')))
        assert img.mode == 'P'
        assert img.getpixel((0, 0)) == 255

    def test_output_formats_png24(self):
        img = Image.new('RGBA', (100, 100))
        image_opts = PNG_FORMAT.copy()
        image_opts.colors = 0 # TODO image_opts
        ir = ImageSource(img, image_opts=image_opts)
        img = Image.open(ir.as_buffer())
        eq_(img.mode, 'RGBA')
        assert img.getpixel((0, 0)) == (0, 0, 0, 0)

class TestSubImageSource(object):
    def test_full(self):
        sub_img = create_image((100, 100), color=[100, 120, 130, 140])
        img = SubImageSource(sub_img, size=(100, 100), offset=(0, 0), image_opts=ImageOptions()).as_image()
        eq_(img.getcolors(), [(100*100, (100, 120, 130, 140))])

    def test_larger(self):
        sub_img = create_image((150, 150), color=[100, 120, 130, 140])
        img = SubImageSource(sub_img, size=(100, 100), offset=(0, 0), image_opts=ImageOptions()).as_image()
        eq_(img.getcolors(), [(100*100, (100, 120, 130, 140))])

    def test_negative_offset(self):
        sub_img = create_image((150, 150), color=[100, 120, 130, 140])
        img = SubImageSource(sub_img, size=(100, 100), offset=(-50, 0), image_opts=ImageOptions()).as_image()
        eq_(img.getcolors(), [(100*100, (100, 120, 130, 140))])

    def test_overlap_right(self):
        sub_img = create_image((50, 50), color=[100, 120, 130, 140])
        img = SubImageSource(sub_img, size=(100, 100), offset=(75, 25), image_opts=ImageOptions(transparent=True)).as_image()
        eq_(sorted(img.getcolors()), [(25*50, (100, 120, 130, 140)), (100*100-25*50, (255, 255, 255, 0))])

    def test_outside(self):
        sub_img = create_image((50, 50), color=[100, 120, 130, 140])
        img = SubImageSource(sub_img, size=(100, 100), offset=(200, 0), image_opts=ImageOptions(transparent=True)).as_image()
        eq_(img.getcolors(), [(100*100, (255, 255, 255, 0))])

class ROnly(object):
    def __init__(self):
        self.data = [b'Hello World!']
    def read(self):
        if self.data:
            return self.data.pop()
        return b''
    def __iter__(self):
        it = iter(self.data)
        self.data = []
        return it

class TestReadBufWrapper(object):
    def setup(self):
        rbuf = ROnly()
        self.rbuf_wrapper = ReadBufWrapper(rbuf)
    def test_read(self):
        assert self.rbuf_wrapper.read() == b'Hello World!'
        self.rbuf_wrapper.seek(0)
        eq_(self.rbuf_wrapper.read(), b'')
    def test_seek_read(self):
        self.rbuf_wrapper.seek(0)
        assert self.rbuf_wrapper.read() == b'Hello World!'
        self.rbuf_wrapper.seek(0)
        assert self.rbuf_wrapper.read() == b'Hello World!'
    def test_iter(self):
        data = list(self.rbuf_wrapper)
        eq_(data, [b'Hello World!'])
        self.rbuf_wrapper.seek(0)
        data = list(self.rbuf_wrapper)
        eq_(data, [])
    def test_seek_iter(self):
        self.rbuf_wrapper.seek(0)
        data = list(self.rbuf_wrapper)
        eq_(data, [b'Hello World!'])
        self.rbuf_wrapper.seek(0)
        data = list(self.rbuf_wrapper)
        eq_(data, [b'Hello World!'])
    def test_hasattr(self):
        assert hasattr(self.rbuf_wrapper, 'seek')
        assert hasattr(self.rbuf_wrapper, 'readline')


class TestMergeAll(object):
    def setup(self):
        self.cleanup_tiles = []

    def test_full_merge(self):
        self.cleanup_tiles = [create_tmp_image_file((100, 100)) for _ in range(9)]
        self.tiles = [ImageSource(tile) for tile in self.cleanup_tiles]
        m = TileMerger(tile_grid=(3, 3), tile_size=(100, 100))
        img_opts = ImageOptions()
        result = m.merge(self.tiles, img_opts)
        img = result.as_image()
        eq_(img.size, (300, 300))

    def test_one(self):
        self.cleanup_tiles = [create_tmp_image_file((100, 100))]
        self.tiles = [ImageSource(self.cleanup_tiles[0])]
        m = TileMerger(tile_grid=(1, 1), tile_size=(100, 100))
        img_opts = ImageOptions(transparent=True)
        result = m.merge(self.tiles, img_opts)
        img = result.as_image()
        eq_(img.size, (100, 100))
        eq_(img.mode, 'RGBA')

    def test_missing_tiles(self):
        self.cleanup_tiles = [create_tmp_image_file((100, 100))]
        self.tiles = [ImageSource(self.cleanup_tiles[0])]
        self.tiles.extend([None]*8)
        m = TileMerger(tile_grid=(3, 3), tile_size=(100, 100))
        img_opts = ImageOptions()
        result = m.merge(self.tiles, img_opts)
        img = result.as_image()
        eq_(img.size, (300, 300))
        eq_(img.getcolors(), [(80000, (255, 255, 255)), (10000, (0, 0, 0)), ])

    def test_invalid_tile(self):
        self.cleanup_tiles = [create_tmp_image_file((100, 100)) for _ in range(9)]
        self.tiles = [ImageSource(tile) for tile in self.cleanup_tiles]
        invalid_tile = self.tiles[0].source
        with open(invalid_tile, 'wb') as tmp:
            tmp.write(b'invalid')
        m = TileMerger(tile_grid=(3, 3), tile_size=(100, 100))
        img_opts = ImageOptions(bgcolor=(200, 0, 50))
        result = m.merge(self.tiles, img_opts)
        img = result.as_image()
        eq_(img.size, (300, 300))
        eq_(img.getcolors(), [(10000, (200, 0, 50)), (80000, (0, 0, 0))])
        assert not os.path.isfile(invalid_tile)

    def test_none_merge(self):
        tiles = [None]
        m = TileMerger(tile_grid=(1, 1), tile_size=(100, 100))
        img_opts = ImageOptions(mode='RGBA', bgcolor=(200, 100, 30, 40))
        result = m.merge(tiles, img_opts)
        img = result.as_image()
        eq_(img.size, (100, 100))
        eq_(img.getcolors(), [(100*100, (200, 100, 30, 40))])

    def teardown(self):
        for tile_fname in self.cleanup_tiles:
            if tile_fname and os.path.isfile(tile_fname):
                os.remove(tile_fname)

class TestGetCrop(object):
    def setup(self):
        self.tmp_file = create_tmp_image_file((100, 100), two_colored=True)
        self.img = ImageSource(self.tmp_file,
                               image_opts=ImageOptions(format='image/png'), size=(100, 100))

    def teardown(self):
        if os.path.exists(self.tmp_file):
            os.remove(self.tmp_file)

    def test_perfect_match(self):
        bbox = (-10, -5, 30, 35)
        transformer = ImageTransformer(SRS(4326), SRS(4326))
        result = transformer.transform(self.img, bbox, (100, 100), bbox, image_opts=None)
        assert self.img == result

    def test_simple_resize_nearest(self):
        bbox = (-10, -5, 30, 35)
        transformer = ImageTransformer(SRS(4326), SRS(4326))
        result = transformer.transform(self.img, bbox, (200, 200), bbox,
            image_opts=ImageOptions(resampling='nearest'))
        img = result.as_image()

        eq_(img.size, (200, 200))
        eq_(len(img.getcolors()), 2)

    def test_simple_resize_bilinear(self):
        bbox = (-10, -5, 30, 35)
        transformer = ImageTransformer(SRS(4326), SRS(4326))
        result = transformer.transform(self.img, bbox, (200, 200), bbox,
            image_opts=ImageOptions(resampling='bilinear'))
        img = result.as_image()

        eq_(img.size, (200, 200))
        # some shades of grey with bilinear
        assert len(img.getcolors()) >= 4


class TestLayerMerge(object):
    def test_opacity_merge(self):
        img1 = ImageSource(Image.new('RGB', (10, 10), (255, 0, 255)))
        img2 = ImageSource(Image.new('RGB', (10, 10), (0, 255, 255)),
            image_opts=ImageOptions(opacity=0.5))

        result = merge_images([img1, img2], ImageOptions(transparent=False))
        img = result.as_image()
        eq_(img.getpixel((0, 0)), (127, 127, 255))

    def test_opacity_merge_mixed_modes(self):
        img1 = ImageSource(Image.new('RGBA', (10, 10), (255, 0, 255, 255)))
        img2 = ImageSource(Image.new('RGB', (10, 10), (0, 255, 255)).convert('P'),
            image_opts=ImageOptions(opacity=0.5))

        result = merge_images([img1, img2], ImageOptions(transparent=True))
        img = result.as_image()
        assert_img_colors_eq(img, [
            (10*10, (127, 127, 255, 255)),
        ])

    def test_merge_L(self):
        img1 = ImageSource(Image.new('RGBA', (10, 10), (255, 0, 255, 255)))
        img2 = ImageSource(Image.new('L', (10, 10), 100))

        # img2 overlays img1
        result = merge_images([img1, img2], ImageOptions(transparent=True))
        img = result.as_image()
        assert_img_colors_eq(img, [
            (10*10, (100, 100, 100, 255)),
        ])

    def test_paletted_merge(self):
        if not hasattr(Image, 'FASTOCTREE'):
            raise SkipTest()

        # generate RGBA images with a transparent rectangle in the lower right
        img1 = ImageSource(Image.new('RGBA', (50, 50), (0, 255, 0, 255))).as_image()
        draw = ImageDraw.Draw(img1)
        draw.rectangle((25, 25, 49, 49), fill=(0, 0, 0, 0))
        paletted_img = quantize(img1, alpha=True)
        assert img_has_transparency(paletted_img)
        assert paletted_img.mode == 'P'

        rgba_img = Image.new('RGBA', (50, 50), (255, 0, 0, 255))
        draw = ImageDraw.Draw(rgba_img)
        draw.rectangle((25, 25, 49, 49), fill=(0, 0, 0, 0))

        img1 = ImageSource(paletted_img)
        img2 = ImageSource(rgba_img)

        # generate base image and merge the others above
        img3 = ImageSource(Image.new('RGBA', (50, 50), (0, 0, 255, 255)))
        result = merge_images([img3, img1, img2], ImageOptions(transparent=True))
        img = result.as_image()

        assert img.mode == 'RGBA'
        eq_(img.getpixel((49, 49)), (0, 0, 255, 255))
        eq_(img.getpixel((0, 0)), (255, 0, 0, 255))

    def test_solid_merge(self):
        img1 = ImageSource(Image.new('RGB', (10, 10), (255, 0, 255)))
        img2 = ImageSource(Image.new('RGB', (10, 10), (0, 255, 255)))

        result = merge_images([img1, img2], ImageOptions(transparent=False))
        img = result.as_image()
        eq_(img.getpixel((0, 0)), (0, 255, 255))

    def test_merge_rgb_with_transp(self):
        img1 = ImageSource(Image.new('RGB', (10, 10), (255, 0, 255)))
        raw = Image.new('RGB', (10, 10), (0, 255, 255))
        raw.info = {'transparency': (0, 255, 255)} # make full transparent
        img2 = ImageSource(raw)

        result = merge_images([img1, img2], ImageOptions(transparent=False))
        img = result.as_image()
        eq_(img.getpixel((0, 0)), (255, 0, 255))


class TestLayerCompositeMerge(object):
    def test_composite_merge(self):
        # http://stackoverflow.com/questions/3374878

        if not hasattr(Image, 'alpha_composite'):
            raise SkipTest()

        img1 = Image.new('RGBA', size=(100, 100), color=(255, 0, 0, 255))
        draw = ImageDraw.Draw(img1)
        draw.rectangle((33, 0, 66, 100), fill=(255, 0, 0, 128))
        draw.rectangle((67, 0, 100, 100), fill=(255, 0, 0, 0))
        img1 = ImageSource(img1)
        img2 = Image.new('RGBA', size =(100, 100), color=(0, 255, 0, 255))
        draw = ImageDraw.Draw(img2)
        draw.rectangle((0, 33, 100, 66), fill=(0, 255, 0, 128))
        draw.rectangle((0, 67, 100, 100), fill=(0, 255, 0, 0))
        img2 = ImageSource(img2)

        result = merge_images([img2, img1], ImageOptions(transparent=True))
        img = result.as_image()
        eq_(img.mode, 'RGBA')
        assert_img_colors_eq(img, [
            (1089, (0, 255, 0, 255)),
            (1089, (255, 255, 255, 0)),
            (1122, (0, 255, 0, 128)),
            (1122, (128, 126, 0, 255)),
            (1122, (255, 0, 0, 128)),
            (1156, (170, 84, 0, 191)),
            (3300, (255, 0, 0, 255))])

    def test_composite_merge_opacity(self):
        if not hasattr(Image, 'alpha_composite'):
            raise SkipTest()

        bg = Image.new('RGBA', size=(100, 100), color=(255, 0, 255, 255))
        bg = ImageSource(bg)
        fg = Image.new('RGBA', size =(100, 100), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(fg)
        draw.rectangle((10, 10, 89, 89), fill=(0, 255, 255, 255))
        fg = ImageSource(fg, image_opts=ImageOptions(opacity=0.5))

        result = merge_images([bg, fg], ImageOptions(transparent=True))
        img = result.as_image()
        eq_(img.mode, 'RGBA')
        assert_img_colors_eq(img, [
            (3600, (255, 0, 255, 255)),
            (6400, (128, 127, 255, 255))])

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
        result = transformer.transform(self.src_img, self.src_bbox, self.dst_size, self.dst_bbox,
            image_opts=ImageOptions(resampling='nearest'))
        assert isinstance(result, ImageSource)
        assert result.as_image() != self.src_img.as_image()
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
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, 4, 4), fill=(130, 100, 120, 0))
        draw.rectangle((5, 5, 9, 9), fill=(130, 150, 120, 255))
        img = make_transparent(img, (130, 150, 120, 120), tolerance=5)
        assert img.mode == 'RGBA'
        assert img.size == (50, 50)
        colors = sorted(img.getcolors(), reverse=True)
        eq_(colors, [(1550, (130, 140, 120, 100)), (900, (130, 150, 120, 0)),
            (25, (130, 150, 120, 255)), (25, (130, 100, 120, 0))])


class TestTileSplitter(object):
    def test_background_larger_crop(self):
        img = ImageSource(Image.new('RGB', (356, 266), (130, 140, 120)))
        img_opts = ImageOptions('RGB')
        splitter = TileSplitter(img, img_opts)

        tile = splitter.get_tile((0, 0), (256, 256))

        eq_(tile.size, (256, 256))
        colors = tile.as_image().getcolors()
        eq_(colors, [(256*256, (130, 140, 120))])

        tile = splitter.get_tile((256, 256), (256, 256))

        eq_(tile.size, (256, 256))
        colors = tile.as_image().getcolors()
        eq_(sorted(colors), [(10*100, (130, 140, 120)), (256*256-10*100, (255, 255, 255))])

    def test_background_larger_crop_with_transparent(self):
        img = ImageSource(Image.new('RGBA', (356, 266), (130, 140, 120, 255)))
        img_opts = ImageOptions('RGBA', transparent=True)
        splitter = TileSplitter(img, img_opts)

        tile = splitter.get_tile((0, 0), (256, 256))

        eq_(tile.size, (256, 256))
        colors = tile.as_image().getcolors()
        eq_(colors, [(256*256, (130, 140, 120, 255))])

        tile = splitter.get_tile((256, 256), (256, 256))

        eq_(tile.size, (256, 256))
        colors = tile.as_image().getcolors()
        eq_(sorted(colors), [(10*100, (130, 140, 120, 255)), (256*256-10*100, (255, 255, 255, 0))])

class TestHasTransparency(object):
    def test_rgb(self):
        if not hasattr(Image, 'FASTOCTREE'):
            raise SkipTest()

        img = Image.new('RGB', (10, 10))
        assert not img_has_transparency(img)

        img = quantize(img, alpha=False)
        assert not img_has_transparency(img)

    def test_rbga(self):
        if not hasattr(Image, 'FASTOCTREE'):
            raise SkipTest()

        img = Image.new('RGBA', (10, 10), (100, 200, 50, 255))
        img.paste((255, 50, 50, 0), (3, 3, 7, 7))
        assert img_has_transparency(img)

        img = quantize(img, alpha=True)
        assert img_has_transparency(img)

class TestPeekImageFormat(object):
    def test_peek(self):
        yield self.check, 'png', 'png'
        yield self.check, 'tiff', 'tiff'
        yield self.check, 'gif', 'gif'
        yield self.check, 'jpeg', 'jpeg'
        yield self.check, 'bmp', None

    def check(self, format, expected_format):
        buf = BytesIO()
        Image.new('RGB', (100, 100)).save(buf, format)
        eq_(peek_image_format(buf), expected_format)

class TestBandMerge(object):
    def setup(self):
        self.img0 = ImageSource(Image.new('RGB', (10, 10), (0, 10, 20)))
        self.img1 = ImageSource(Image.new('RGB', (10, 10), (100, 110, 120)))
        self.img2 = ImageSource(Image.new('RGB', (10, 10), (200, 210, 220)))
        self.img3 = ImageSource(Image.new('RGB', (10, 10), (0, 255, 0)))
        self.blank = BlankImageSource(size=(10, 10), image_opts=ImageOptions())

    def test_merge_noops(self):
        """
        Check that black image is returned for no ops.
        """
        merger = BandMerger(mode='RGB')

        img_opts = ImageOptions('RGB')
        result = merger.merge([self.img0], img_opts)
        img = result.as_image()
        eq_(img.size, (10, 10))
        eq_(img.getpixel((0, 0)), (0, 0, 0))

    def test_merge_missing_source(self):
        """
        Check that empty source list or source list with missing images
        returns BlankImageSource.
        """
        merger = BandMerger(mode='RGB')
        merger.add_ops(dst_band=0, src_img=0, src_band=0)
        merger.add_ops(dst_band=1, src_img=1, src_band=0)
        merger.add_ops(dst_band=2, src_img=2, src_band=0)

        img_opts = ImageOptions('RGBA', transparent=True)
        result = merger.merge([], img_opts, size=(10, 10))
        img = result.as_image()

        eq_(img.size, (10, 10))
        eq_(img.getpixel((0, 0)), (255, 255, 255, 0))

        result = merger.merge([self.img0, self.img1], img_opts, size=(10, 10))
        img = result.as_image()

        eq_(img.size, (10, 10))
        eq_(img.getpixel((0, 0)), (255, 255, 255, 0))


    def test_rgb_merge(self):
        """
        Check merge of RGB bands
        """
        merger = BandMerger(mode='RGB')

        merger.add_ops(dst_band=1, src_img=0, src_band=0, factor=0.5)
        merger.add_ops(dst_band=1, src_img=3, src_band=1, factor=0.5)
        merger.add_ops(dst_band=0, src_img=2, src_band=1)
        merger.add_ops(dst_band=2, src_img=1, src_band=2)

        img_opts = ImageOptions('RGB')
        result = merger.merge([self.img0, self.img1, self.img2, self.img3], img_opts)
        img = result.as_image()

        eq_(img.getpixel((0, 0)), (210, 127, 120))

    def test_rgb_merge_missing(self):
        """
        Check missing band is set to 0
        """
        merger = BandMerger(mode='RGB')

        merger.add_ops(dst_band=0, src_img=2, src_band=1)
        merger.add_ops(dst_band=2, src_img=1, src_band=2)

        img_opts = ImageOptions('RGB')
        result = merger.merge([self.img0, self.img1, self.img2, self.img3], img_opts)
        img = result.as_image()

        eq_(img.getpixel((0, 0)), (210, 0, 120))

    def test_rgba_merge(self):
        """
        Check merge of RGBA bands
        """
        merger = BandMerger(mode='RGBA')

        merger.add_ops(dst_band=1, src_img=0, src_band=0, factor=0.5)
        merger.add_ops(dst_band=1, src_img=3, src_band=1, factor=0.5)
        merger.add_ops(dst_band=0, src_img=2, src_band=1)
        merger.add_ops(dst_band=2, src_img=1, src_band=2)
        merger.add_ops(dst_band=3, src_img=1, src_band=1)

        img_opts = ImageOptions('RGBA')
        result = merger.merge([self.img0, self.img1, self.img2, self.img3], img_opts)
        img = result.as_image()

        eq_(img.getpixel((0, 0)), (210, 127, 120, 110))

    def test_rgba_merge_missing_a(self):
        """
        Check that missing alpha band defaults to opaque
        """
        merger = BandMerger(mode='RGBA')

        merger.add_ops(dst_band=1, src_img=0, src_band=0, factor=0.5)
        merger.add_ops(dst_band=1, src_img=3, src_band=1, factor=0.5)
        merger.add_ops(dst_band=0, src_img=2, src_band=1)
        merger.add_ops(dst_band=2, src_img=1, src_band=2)

        img_opts = ImageOptions('RGBA')
        result = merger.merge([self.img0, self.img1, self.img2, self.img3], img_opts)
        img = result.as_image()

        eq_(img.getpixel((0, 0)), (210, 127, 120, 255))

    def test_l_merge(self):
        """
        Check merge bands to grayscale image
        """
        merger = BandMerger(mode='L')

        merger.add_ops(dst_band=0, src_img=0, src_band=2, factor=0.2)
        merger.add_ops(dst_band=0, src_img=2, src_band=1, factor=0.3)
        merger.add_ops(dst_band=0, src_img=3, src_band=1, factor=0.5)

        img_opts = ImageOptions('L')
        result = merger.merge([self.img0, self.img1, self.img2, self.img3], img_opts)
        img = result.as_image()

        eq_(img.getpixel((0, 0)), int(20*0.2) + int(210*0.3) + int(255*0.5))

    def test_p_merge(self):
        """
        Check merge bands to paletted image
        """
        merger = BandMerger(mode='RGB')

        merger.add_ops(dst_band=1, src_img=0, src_band=0, factor=0.5)
        merger.add_ops(dst_band=1, src_img=3, src_band=1, factor=0.5)
        merger.add_ops(dst_band=0, src_img=2, src_band=1)
        merger.add_ops(dst_band=2, src_img=1, src_band=2)

        img_opts = ImageOptions('P', format='image/png', encoding_options={'quantizer': 'mediancut'})
        result = merger.merge([self.img0, self.img1, self.img2, self.img3], img_opts)

        # need to encode to get conversion to P
        img = Image.open(result.as_buffer())

        eq_(img.mode, 'P')
        img = img.convert('RGB')
        eq_(img.getpixel((0, 0)), (210, 127, 120))

    def test_from_p_merge(self):
        """
        Check merge bands from paletted image
        """
        merger = BandMerger(mode='RGB')

        merger.add_ops(dst_band=0, src_img=0, src_band=2)
        merger.add_ops(dst_band=1, src_img=0, src_band=1)
        merger.add_ops(dst_band=2, src_img=0, src_band=0)

        img = Image.new('RGB', (10, 10), (0, 100, 200)).quantize(256)
        eq_(img.mode, 'P')
        # src img is P but we can still access RGB bands
        src_img = ImageSource(img)

        img_opts = ImageOptions('RGB')
        result = merger.merge([src_img], img_opts)

        img = result.as_image()
        eq_(img.mode, 'RGB')
        eq_(img.getpixel((0, 0)), (200, 100, 0))

    def test_from_mixed_merge(self):
        """
        Check merge RGBA bands from image without alpha (mixed)
        """
        merger = BandMerger(mode='RGBA')

        merger.add_ops(dst_band=0, src_img=0, src_band=2)
        merger.add_ops(dst_band=1, src_img=0, src_band=1)
        merger.add_ops(dst_band=2, src_img=0, src_band=0)
        merger.add_ops(dst_band=3, src_img=0, src_band=3)

        img = Image.new('RGB', (10, 10), (0, 100, 200))
        src_img = ImageSource(img)

        img_opts = ImageOptions('RGBA')
        result = merger.merge([src_img], img_opts)

        img = result.as_image()
        eq_(img.mode, 'RGBA')
        eq_(img.getpixel((0, 0)), (200, 100, 0, 255))

