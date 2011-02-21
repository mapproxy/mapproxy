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

from __future__ import division
import os

from mapproxy.platform.image import Image, ImageColor, ImageDraw, ImageFont
from mapproxy.image import ImageSource

_pil_ttf_support = True


import logging
log = logging.getLogger(__name__)

def message_image(message, size, format='png', bgcolor='#ffffff',
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
    eimg = ExceptionImage(message, format=format, bgcolor=bgcolor, transparent=transparent)
    return eimg.draw(size=size)

def attribution_image(message, size, format='png',
                  transparent=False, inverse=False):
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
    aimg = AttributionImage(message, format=format, transparent=transparent,
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
    
    def __init__(self, message, format='png'):
        self.message = message
        self.format = format
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
                    log.warn("Couldn't load TrueType fonts, "
                        "PIL needs to be build with freetype support.")
            if self._font is None:
                self._font = ImageFont.load_default()
        return self._font
    
    def new_image(self, size):
        return Image.new('RGBA', size)
    
    def draw(self, img=None, size=None):
        """
        Create the message image. Either draws on top of `img` or creates a
        new image with the given `size`.
        """
        if not ((img and not size) or (size and not img)):
            raise TypeError, 'need either img or size argument'

        if img is None:
            base_img = self.new_image(size)
        else:
            base_img = img.as_image()
            size = base_img.size
        
        if not self.message:
            if img is not None:
                return img
            return ImageSource(base_img, size=size, format=self.format)
        
        draw = ImageDraw.Draw(base_img)
        self.draw_msg(draw, size)
        return ImageSource(base_img, size=size, format=self.format)
    
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
    def __init__(self, message, format='png', bgcolor='#000000', transparent=False):
        MessageImage.__init__(self, message, format=format)
        self.bgcolor = bgcolor
        self.transparent = transparent
    
    def new_image(self, size):
        bgcolor = ImageColor.getrgb(self.bgcolor)
        if self.transparent:
            bgcolor += (0,)
            return Image.new('RGBA', size, color=bgcolor)
        return Image.new('RGB', size, color=bgcolor)
    
    @property
    def font_color(self):
        if self.transparent:
            return ImageColor.getrgb('black')
        if _luminance(ImageColor.getrgb(self.bgcolor)) < 128:
            return ImageColor.getrgb('white')
        return ImageColor.getrgb('black')
    

class WatermarkImage(MessageImage):
    """
    Image with large, faded message. 
    """
    font_name = 'DejaVu Sans'
    font_size = 24
    font_color = (128, 128, 128)
    
    def __init__(self, message, format='png', placement='c', opacity=None, font_size=None):
        MessageImage.__init__(self, message, format)
        if opacity is None:
            opacity = 3
        if font_size:
            self.font_size = font_size
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
    
    def __init__(self, message, format='png', transparent=False, inverse=False):
        MessageImage.__init__(self, message, format)
        self.transparent = transparent
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
    font_name = font_name.replace(' ', '')
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                'fonts', font_name + '.ttf')
    return path
    

def _luminance(color):
    """
    Returns the luminance of a RGB tuple. Uses ITU-R 601-2 luma transform.
    """
    r, g, b = color
    return r * 299/1000 + g * 587/1000 + b * 114/1000
