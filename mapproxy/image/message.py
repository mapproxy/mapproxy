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
    
    def text_size(self, draw):
        try:
            return draw.textsize(self.message, font=self.font)
        except UnicodeEncodeError:
            # PILs default font does only support ascii
            self.message = self.message.encode('ascii', 'ignore')
            return draw.textsize(self.message, font=self.font)
    
    def text_box(self, img, draw):
        raise NotImplementedError
    
    def new_image(self, size):
        return Image.new('RGBA', size)
    
    def draw(self, img=None, size=None):
        """
        Create the message image. Either draws on top of `img` or creates a
        new image with the given `size`.
        """
        if not ((img and not size) or (size and not img)):
            raise TypeError, 'need either img or size argument'
        base_img = None
        if img is not None:
            base_img = img.as_image().convert('RGBA')
            size = base_img.size
        msg_img = self.new_image(size)
        if not self.message:
            return img if img is not None else ImageSource(msg_img, size=size,
                                                           format=self.format)
        draw = ImageDraw.Draw(msg_img)
        self.draw_msg(msg_img, draw)
        result = self.merge_msg(base_img, msg_img)
        return ImageSource(result, size=size, format=self.format)
    
    def merge_msg(self, img, msg_img):
        if img is not None:
            img.paste(msg_img, (0, 0), msg_img)
            return img
        return msg_img
    
    def draw_msg(self, msg_img, draw):
        text_box = self.text_box(msg_img, draw)
        if self.box_color:
            draw.rectangle(text_box, fill=self.box_color)
        draw.text((text_box[0], text_box[1]), self.message, font=self.font,
                  fill=self.font_color)

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
    
    def text_box(self, _img, draw):
        text_size = self.text_size(draw)
        return (10, 10, text_size[0]+10, text_size[1]+10)
    
    def draw_msg(self, msg_img, draw):
        if not self.transparent:
            bgcolor = ImageColor.getrgb(self.bgcolor)
            draw.rectangle((0, 0, msg_img.size[0], msg_img.size[1]), fill=bgcolor)
        MessageImage.draw_msg(self, msg_img, draw)
    

class WatermarkImage(MessageImage):
    """
    Image with large, faded message. 
    """
    font_name = 'DejaVu Sans'
    font_size = 24
    font_color = (0, 0, 0)
    
    def __init__(self, message, format='png', odd=False, opacity=None, font_size=None):
        MessageImage.__init__(self, message, format)
        if opacity is None:
            opacity = 3
        if font_size:
            self.font_size = font_size
        self.font_color = self.font_color + tuple([opacity])
        self.odd = odd
    
    def new_image(self, size):
        return Image.new('RGBA', size)
    
    def text_box(self, img, draw):
        text_size = self.text_size(draw)
        w, h = img.size
        x = w//2 - text_size[0]//2
        y = h//2 - text_size[1]//2
        return (x, y, x+w, y+h)
    
    def merge_msg(self, img, msg_img):
        if img is None:
            return msg_img
        w, _ = img.size
        if self.odd:
            img.paste(msg_img, (-w//2, 0), msg_img)
            img.paste(msg_img, (w//2, 0), msg_img)
        else:
            img.paste(msg_img, (0, 0), msg_img)
        return img

class AttributionImage(MessageImage):
    """
    Image with attribution information.
    """
    font_name = 'DejaVu Sans'
    font_size = 10
    
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
    
    def text_box(self, img, draw):
        img_size = img.size
        text_size = self.text_size(draw)
        return (img_size[0]-text_size[0]-5, img_size[1]-5-text_size[1],
                img_size[0]-5, img_size[1]-5)


class TextDraw(object):
    def __init__(self, text, font, font_color=None, bg_color=None,
                 placement='ul', padding=10, linespacing=10):
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
