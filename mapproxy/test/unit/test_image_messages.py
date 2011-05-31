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

from mapproxy.platform.image import (
    Image,
    ImageDraw,
    ImageColor,
    ImageFont,
)

from mapproxy.cache.tile import Tile
from mapproxy.image import ImageSource
from mapproxy.image.message import TextDraw, message_image
from mapproxy.image.opts import ImageOptions
from mapproxy.tilefilter import watermark_filter

from nose.tools import eq_

PNG_FORMAT = ImageOptions(format='image/png')

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
        image_opts = PNG_FORMAT.copy()
        image_opts.bgcolor = '#113399'
        img = message_image('', size=(100, 150), image_opts=image_opts)
        assert isinstance(img, ImageSource)
        eq_(img.size, (100, 150))
        pil_img = img.as_image()
        eq_(pil_img.getpixel((0, 0)), ImageColor.getrgb('#113399'))
        # 3 values in histogram (RGB)
        assert [x for x in pil_img.histogram() if x > 0] == [15000, 15000, 15000]
    def test_message(self):
        image_opts = PNG_FORMAT.copy()
        image_opts.bgcolor = '#113399'
        img = message_image('test', size=(100, 150), image_opts=image_opts)
        assert isinstance(img, ImageSource)
        assert img.size == (100, 150)
        # 6 values in histogram (3xRGB for background, 3xRGB for text message)
        eq_([x for x in img.as_image().histogram() if x > 10],
             [14923, 77, 14923, 77, 14923, 77])
    def test_transparent(self):
        image_opts = ImageOptions(transparent=True)
        print image_opts
        img = message_image('', size=(100, 150), image_opts=image_opts)
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