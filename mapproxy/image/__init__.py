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

"""
Image and tile manipulation (transforming, merging, etc).
"""
from __future__ import with_statement
from cStringIO import StringIO

from mapproxy.platform.image import Image, ImageColor, ImageChops, quantize
from mapproxy.config import base_config

import logging
log = logging.getLogger(__name__)


class LayerMerger(object):
    """
    Merge multiple layers into one image.
    """
    def __init__(self):
        self.layers = []
    def add(self, layer):
        """
        Add one or more layers to merge. Bottom-layers first.
        """
        try:
            layer = iter(layer)
        except TypeError:
            if layer is not None:
                self.layers.append(layer)
        else:
            for l in layer:
                self.add(l)

    def merge(self, format='png', size=None, bgcolor='#ffffff', transparent=False):
        """
        Merge the layers. If the format is not 'png' just return the last image.
        
        :param format: The image format for the result.
        :param size: The size for the merged output.
        :rtype: `ImageSource`
        """
        if not self.layers:
            return BlankImageSource(size=size, bgcolor=bgcolor, transparent=transparent)
        if len(self.layers) == 1:
            if (self.layers[0].transparent == transparent):
                return self.layers[0]
        
        # TODO optimizations
        #  - layer with non transparency
        #         if not format.endswith('png'): #TODO png8?
        #             return self.layers[-1]
        
        if size is None:
            size = self.layers[0].size
        bgcolor = ImageColor.getrgb(bgcolor)
        if transparent:
            img = Image.new('RGBA', size, bgcolor+(0,))
        else:
            img = Image.new('RGB', size, bgcolor)
        
        for layer in self.layers:
            layer_img = layer.as_image()
            if layer.opacity is not None and layer.opacity < 1.0:
                layer_img = layer_img.convert(img.mode)
                img = Image.blend(img, layer_img, layer.opacity)
            else:
                if layer_img.mode == 'RGBA':
                    # paste w transparency mask from layer
                    img.paste(layer_img, (0, 0), layer_img)
                else:
                    img.paste(layer_img, (0, 0))
        return ImageSource(img, format)

def merge_images(images, format='png', size=None, transparent=True):
    """
    Merge multiple images into one.
    
    :param images: list of `ImageSource`, bottom image first
    :param format: the format of the output `ImageSource`
    :param size: size of the merged image, if ``None`` the size
                 of the first image is used
    :rtype: `ImageSource`
    """
    merger = LayerMerger()
    merger.add(images)
    return merger.merge(format=format, size=size, transparent=transparent)

def concat_legends(legends, format='png', size=None, bgcolor='#ffffff', transparent=True):
    """
    Merge multiple legends into one
    :param images: list of `ImageSource`, bottom image first
    :param format: the format of the output `ImageSource`
    :param size: size of the merged image, if ``None`` the size
                 will be calculated
    :rtype: `ImageSource`
    """
    if not legends:
        return BlankImageSource(size=(1,1), bgcolor=bgcolor, transparent=transparent)
    if len(legends) == 1:
        return legends[0]
    
    legends = legends[:]
    legends.reverse()
    if size is None:
        legend_width = 0
        legend_height = 0
        legend_position_y = []
        #iterate through all legends, last to first, calc img size and remember the y-position
        for legend in legends:
            legend_position_y.append(legend_height)
            tmp_img = legend.as_image()
            legend_width = max(legend_width, tmp_img.size[0])
            legend_height += tmp_img.size[1] #images shall not overlap themselfs
            
        size = [legend_width, legend_height]
    bgcolor = ImageColor.getrgb(bgcolor)
    
    if transparent:
        img = Image.new('RGBA', size, bgcolor+(0,))
    else:
        img = Image.new('RGB', size, bgcolor)
    for i in range(len(legends)):
        legend_img = legends[i].as_image()
        if legend_img.mode == 'RGBA':
            # paste w transparency mask from layer
            img.paste(legend_img, (0, legend_position_y[i]), legend_img)
        else:
            img.paste(legend_img, (0, legend_position_y[i]))
    return ImageSource(img, format)

class ImageSource(object):
    """
    This class wraps either a PIL image, a file-like object, or a file name.
    You can access the result as an image (`as_image` ) or a file-like buffer
    object (`as_buffer`).
    """
    def __init__(self, source, format='png', size=None, transparent=False, opacity=None):
        """
        :param source: the image
        :type source: PIL `Image`, image file object, or filename
        :param format: the format of the ``source``
        :param size: the size of the ``source`` in pixel
        """
        self._img = None
        self._buf = None
        self._fname = None
        self.source = source
        self.format = format
        self.transparent = transparent
        self.opacity = opacity
        self._size = size
    
    def _set_source(self, source):
        self._img = None
        self._buf = None
        if isinstance(source, basestring):
            self._fname = source
        elif isinstance(source, Image.Image):
            self._img = source
        else:
            self._buf = source
    
    def _get_source(self):
        return self._img or self._buf or self._fname
    
    source = property(_get_source, _set_source)
    
    def close_buffers(self):
        if self._buf:
            try:
                self._buf.close()
            except IOError:
                pass
    
    @property
    def filename(self):
        return self._fname
    
    def as_image(self):
        """
        Returns the image or the loaded image.
        
        :rtype: PIL `Image`
        """
        if not self._img: 
            self._make_seekable_buf()
            log.debug('file(%s) -> image', self._fname or self._buf)
        
            try:
                img = Image.open(self._buf)
            except StandardError:
                self.close_buffers()
                raise
            self._img = img
        
        if self.transparent and self._img.mode == 'P':
            self._img = self._img.convert('RGBA')
    
        return self._img
    
    def _make_seekable_buf(self):
        if not self._buf and self._fname:
            self._buf = open(self._fname, 'rb')
        elif not hasattr(self._buf, 'seek'):
            # PIL needs file objects with seek
            self._buf = StringIO(self._buf.read())
        self._buf.seek(0)
    
    def _make_readable_buf(self):
        if not self._buf and self._fname:
            self._buf = open(self._fname, 'rb')
        elif not hasattr(self._buf, 'seek'):
            if isinstance(self._buf, ReadBufWrapper):
                self._buf = ReadBufWrapper(self._buf)
        else:
            self._buf.seek(0)
    
    def as_buffer(self, format=None, paletted=None, seekable=False):
        """
        Returns the image as a file object.
        
        :param format: The format to encode an image.
                       Existing files will not be re-encoded.
        :rtype: file-like object
        """
        if not self._buf and not self._fname:
            if not format:
                format = self.format
            log.debug('image -> buf(%s)' % (format,))
            self._buf = img_to_buf(self._img, format, paletted=paletted)
        else:
            self._make_seekable_buf() if seekable else self._make_readable_buf()
            if self.format and format and self.format != format:
                log.debug('converting image from %s -> %s' % (self.format, format))
                self.source = self.as_image()
                self._buf = None
                self.format = format
                # hide fname to prevent as_buffer from reading the file
                fname = self._fname
                self._fname = None
                self.as_buffer(format=format, paletted=paletted)        
                self._fname = fname
        return self._buf

    @property
    def size(self):
        if self._size is None:
            self._size = self.as_image().size
        return self._size

class BlankImageSource(object):
    """
    ImageSource for transparent or solid-color images.
    Implements optimized as_buffer() method.
    """
    def __init__(self, size, bgcolor=None, transparent=True, format=None):
        self.size = size
        self.bgcolor = bgcolor or '#ffffff'
        self.transparent = transparent
        self.opacity = 0.0 if transparent else 1.0
        self.format = format
    
    def as_image(self):
        bgcolor = ImageColor.getrgb(self.bgcolor)
        if self.transparent:
            img = Image.new('RGBA', self.size, bgcolor+(0,))
        else:
            img = Image.new('RGB', self.size, bgcolor)
        # set paletted to false, no need to quantize single color image
        return img
    
    def as_buffer(self, format=None, paletted=None, seekable=False):
        return img_to_buf(self.as_image(), format or self.format, paletted=False)

class ReadBufWrapper(object):
    """
    This class wraps everything with a ``read`` method and adds support
    for ``seek``, etc. A call to everything but ``read`` will create a
    StringIO object of the ``readbuf``.
    """
    def __init__(self, readbuf):
        self.ok_to_seek = False
        self.readbuf = readbuf
        self.stringio = None
    
    def read(self, *args, **kw):
        if self.stringio:
            return self.stringio.read(*args, **kw)
        return self.readbuf.read(*args, **kw)
    
    def __iter__(self):
        if self.stringio:
            return iter(self.stringio)
        else:
            return iter(self.readbuf)
    
    def __getattr__(self, name):
        if self.stringio is None:
            if hasattr(self.readbuf, name):
                return getattr(self.readbuf, name)
            elif name == '__length_hint__':
                raise AttributeError
            self.ok_to_seek = True
            self.stringio = StringIO(self.readbuf.read())
        return getattr(self.stringio, name)

def img_to_buf(img, format='png', paletted=None):
    defaults = {}    
    if paletted is None:
        if format == 'png8':
            paletted = True
        else:
            paletted = base_config().image.paletted
    if paletted:
        if format in ('png', 'gif', 'png8'):
            if img.mode == 'RGBA':
                img = quantize(img, alpha=True, defaults=defaults)
            else:
                img = quantize(img)
            if hasattr(Image, 'RLE'):
                defaults['compress_type'] = Image.RLE
    format = filter_format(format)
    buf = StringIO()
    if format == 'jpeg':
        img = img.convert('RGB')
        defaults['quality'] = base_config().image.jpeg_quality
    img.save(buf, format, **defaults)
    buf.seek(0)
    return buf
    
def filter_format(format):
    if format.lower() == 'geotiff':
        format = 'tiff'
    if format.lower().startswith('png'):
        format = 'png'
    return format

image_filter = { 
    'nearest': Image.NEAREST,
    'bilinear': Image.BILINEAR,
    'bicubic': Image.BICUBIC
}


def is_single_color_image(image):
    """
    Checks if the `image` contains only one color.
    Returns ``False`` if it contains more than one color, else
    the color-tuple of the single color.
    """
    result = image.getcolors(1)
    # returns a list of (count, color), limit to one
    if result is None:
        return False
    
    color = result[0][1]
    if image.mode == 'P':
        palette = image.getpalette()
        return palette[color*3], palette[color*3+1], palette[color*3+2]
    
    return result[0][1]

def make_transparent(img, color, tolerance=10):
    """
    Create alpha channel for the given image and make each pixel
    in `color` full transparent.
    
    Returns an RGBA ImageSoruce.
    
    Modifies the image in-place, unless it needs to be converted
    first (P->RGB).
    
    :param color: RGB color tuple
    :param tolerance: tolerance applied to each color value
    """
    result = _make_transparent(img.as_image(), color, tolerance)
    return ImageSource(result, size=result.size, transparent=True)

def _make_transparent(img, color, tolerance=10):
    img.load()
    
    if img.mode == 'P':
        img = img.convert('RGB')
    
    channels = img.split()
    mask_channels = []
    for ch, c in zip(channels, color):
        low_c, high_c = c-tolerance, c+tolerance
        mask_channels.append(Image.eval(ch, lambda x: 255 if low_c <= x <= high_c else 0))
        
    alpha = reduce(ImageChops.multiply, mask_channels)
    img.putalpha(ImageChops.invert(alpha))
    return img
