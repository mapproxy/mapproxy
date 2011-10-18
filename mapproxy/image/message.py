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

from __future__ import division
import os

from mapproxy.config import base_config, abspath
from mapproxy.platform.image import Image, ImageColor, ImageDraw, ImageFont
from mapproxy.image import ImageSource
from mapproxy.image.opts import create_image, ImageOptions

_pil_ttf_support = True


import logging
log_system = logging.getLogger('mapproxy.system')

def message_image(message, size, image_opts, bgcolor='#ffffff',
                  transparent=False):
    """
    Creates an image with text (`message`). This can be used
    to create in_image exceptions.
    
    For dark `bgcolor` the font color is white, otherwise black.
    
    :param message: the message to put in the image
    :param size: the size of the output image
    :param format: the output format of the image
    :param bgcolor: the background color of the image
    :param transparent: if True and the `format` supports it,
                        return a transparent image
    :rtype: `ImageSource`
    """
    eimg = ExceptionImage(message, image_opts=image_opts)
    return eimg.draw(size=size)

def attribution_image(message, size, image_opts=None, inverse=False):
    """
    Creates an image with text attribution (`message`).
    
    :param message: the message to put in the image
    :param size: the size of the output image
    :param format: the output format of the image
    :param inverse: if true, write white text
    :param transparent: if True and the `format` supports it,
                        return a transparent image
    :rtype: `ImageSource`
    """
    if image_opts is None:
        image_opts = ImageOptions(transparent=True)
    aimg = AttributionImage(message, image_opts=image_opts,
                            inverse=inverse)
    return aimg.draw(size=size)

class MessageImage(object):
    """
    Base class for text rendering in images (for watermarks, exception images, etc.)
    
    :ivar font_name: the font name for the text
    :ivar font_size: the font size of the text
    :ivar font_color: the color of the font as a tuple
    :ivar box_color: the color of the box behind the text.
                     color as a tuple or ``None``
    """
    font_name = 'DejaVu Sans Mono'
    font_size = 10
    font_color = ImageColor.getrgb('black')
    box_color = None
    linespacing = 5
    padding = 3
    placement = 'ul'
    
    def __init__(self, message, image_opts):
        self.message = message
        self.image_opts = image_opts
        self._font = None
    
    @property
    def font(self):
        global _pil_ttf_support
        if self._font is None:
            if self.font_name != 'default' and _pil_ttf_support:
                try:
                    self._font = ImageFont.truetype(font_file(self.font_name),
                        self.font_size)
                except ImportError:
                    _pil_ttf_support = False
                    log_system.warn("Couldn't load TrueType fonts, "
                        "PIL needs to be build with freetype support.")
            if self._font is None:
                self._font = ImageFont.load_default()
        return self._font
    
    def new_image(self, size):
        return Image.new('RGBA', size)
    
    def draw(self, img=None, size=None, in_place=True):
        """
        Create the message image. Either draws on top of `img` or creates a
        new image with the given `size`.
        """
        if not ((img and not size) or (size and not img)):
            raise TypeError, 'need either img or size argument'

        if img is None:
            base_img = self.new_image(size)
        elif not in_place:
            size = img.size
            base_img = self.new_image(size)
        else:
            base_img = img.as_image()
            size = base_img.size
        
        if not self.message:
            if img is not None:
                return img
            return ImageSource(base_img, size=size, image_opts=self.image_opts)
        
        draw = ImageDraw.Draw(base_img)
        self.draw_msg(draw, size)
        if not in_place and img:
            img = img.as_image()
            img.paste(base_img, (0, 0), base_img)
            base_img = img
        
        return ImageSource(base_img, size=size, image_opts=self.image_opts)
    
    def draw_msg(self, draw, size):
        td = TextDraw(self.message, font=self.font, bg_color=self.box_color,
                      font_color=self.font_color, placement=self.placement,
                      linespacing=self.linespacing, padding=self.padding)
        td.draw(draw, size)


class ExceptionImage(MessageImage):
    """
    Image for exceptions.
    """
    font_name = 'default'
    font_size = 9
    def __init__(self, message, image_opts):
        MessageImage.__init__(self, message, image_opts=image_opts.copy())
        if not self.image_opts.bgcolor:
            self.image_opts.bgcolor = '#ffffff'
    
    def new_image(self, size):
        return create_image(size, self.image_opts)
    
    @property
    def font_color(self):
        if self.image_opts.transparent:
            return ImageColor.getrgb('black')
        if _luminance(ImageColor.getrgb(self.image_opts.bgcolor)) < 128:
            return ImageColor.getrgb('white')
        return ImageColor.getrgb('black')
    

class WatermarkImage(MessageImage):
    """
    Image with large, faded message. 
    """
    font_name = 'DejaVu Sans'
    font_size = 24
    font_color = (128, 128, 128)
    
    def __init__(self, message, image_opts, placement='c', opacity=None, font_color=None, font_size=None):
        MessageImage.__init__(self, message, image_opts=image_opts)
        if opacity is None:
            opacity = 30
        if font_size:
            self.font_size = font_size
        if font_color:
            self.font_color = font_color
        self.font_color = self.font_color + tuple([opacity])
        self.placement = placement
    
    def draw_msg(self, draw, size):
        td = TextDraw(self.message, self.font, self.font_color)
        if self.placement in ('l', 'b'):
            td.placement = 'cL'
            td.draw(draw, size)
        if self.placement in ('r', 'b'):
            td.placement = 'cR'
            td.draw(draw, size)
        if self.placement == 'c':
            td.placement = 'cc'
            td.draw(draw, size)
        
    
class AttributionImage(MessageImage):
    """
    Image with attribution information.
    """
    font_name = 'DejaVu Sans'
    font_size = 10
    placement = 'lr'
    
    def __init__(self, message, image_opts, inverse=False):
        MessageImage.__init__(self, message, image_opts=image_opts)
        self.inverse = inverse
    
    @property
    def font_color(self):
        if self.inverse:
            return ImageColor.getrgb('white')
        else:
            return ImageColor.getrgb('black')
    
    @property
    def box_color(self):
        if self.inverse:
            return (0, 0, 0, 100)
        else:
            return (255, 255, 255, 120)
    

class TextDraw(object):
    def __init__(self, text, font, font_color=None, bg_color=None,
                 placement='ul', padding=5, linespacing=3):
        if isinstance(text, basestring):
            text = text.split('\n')
        self.text = text
        self.font = font
        self.bg_color = bg_color
        self.font_color = font_color
        self.placement = placement
        self.padding = (padding, padding, padding, padding)
        self.linespacing = linespacing
    
    def text_boxes(self, draw, size):
        try:
            total_bbox, boxes = self._relative_text_boxes(draw)
        except UnicodeEncodeError:
            self.text = [l.encode('ascii', 'replace') for l in self.text]
            total_bbox, boxes = self._relative_text_boxes(draw)
        return self._place_boxes(total_bbox, boxes, size)
    
    def draw(self, draw, size):
        total_bbox, boxes = self.text_boxes(draw, size)
        if self.bg_color:
            draw.rectangle(
                (total_bbox[0]-self.padding[0],
                 total_bbox[1]-self.padding[1],
                 total_bbox[2]+self.padding[2],
                 total_bbox[3]+self.padding[3]),
                fill=self.bg_color)
        
        for text, box in zip(self.text, boxes):
            draw.text((box[0], box[1]), text, font=self.font, fill=self.font_color)
        
    def _relative_text_boxes(self, draw):
        total_bbox = (1e9, 1e9, -1e9, -1e9)
        boxes = []
        y_offset = 0
        for i, line in enumerate(self.text):
            text_size = draw.textsize(line, font=self.font)
            text_box = (0, y_offset, text_size[0], text_size[1]+y_offset)
            boxes.append(text_box)
            total_bbox = (min(total_bbox[0], text_box[0]),
                          min(total_bbox[1], text_box[1]),
                          max(total_bbox[2], text_box[2]),
                          max(total_bbox[3], text_box[3]),
                         )
            
            y_offset += text_size[1] + self.linespacing
        return total_bbox, boxes
        
    def _move_bboxes(self, boxes, offsets):
        result = []
        for box in boxes:
            box = box[0]+offsets[0], box[1]+offsets[1], box[2]+offsets[0], box[3]+offsets[1]
            result.append(tuple(int(x) for x in box))
        return result
    
    def _place_boxes(self, total_bbox, boxes, size):
        x_offset = y_offset = None
        text_size = (total_bbox[2] - total_bbox[0]), (total_bbox[3] - total_bbox[1])
        
        if self.placement[0] == 'u':
            y_offset = self.padding[1]
        elif self.placement[0] == 'l':
            y_offset = size[1] - self.padding[3] - text_size[1]
        elif self.placement[0] == 'c':
            y_offset = size[1] // 2 - text_size[1] // 2
        
        if self.placement[1] == 'l':
            x_offset = self.padding[0]
        if self.placement[1] == 'L':
            x_offset = -text_size[0] // 2
        elif self.placement[1] == 'r':
            x_offset = size[0] - self.padding[1] - text_size[0]
        elif self.placement[1] == 'R':
            x_offset = size[0] - text_size[0] // 2
        elif self.placement[1] == 'c':
            x_offset = size[0] // 2 - text_size[0] // 2
        
        if x_offset is None or y_offset is None:
            raise ValueError('placement %r not supported' % self.placement)
        
        offsets = x_offset, y_offset
        return self._move_bboxes([total_bbox], offsets)[0], self._move_bboxes(boxes, offsets)

def font_file(font_name):
    font_dir = base_config().image.font_dir
    if font_dir:
        abspath(font_dir)
    else:
        font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
    font_name = font_name.replace(' ', '')
    path = os.path.join(font_dir, font_name + '.ttf')
    return path
    

def _luminance(color):
    """
    Returns the luminance of a RGB tuple. Uses ITU-R 601-2 luma transform.
    """
    r, g, b = color
    return r * 299/1000 + g * 587/1000 + b * 114/1000
