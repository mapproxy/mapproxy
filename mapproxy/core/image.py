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
from __future__ import division, with_statement
import os
from cStringIO import StringIO

import Image
import ImageDraw
import ImageColor
import ImageFont

from mapproxy.core.srs import make_lin_transf, bbox_equals

from mapproxy.core.config import base_config

import logging
log = logging.getLogger(__name__)

__all__ = ['ImageSource', 'LayerMerger', 'ImageTransformer',
           'TileMerger', 'message_image']

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
            layers = iter(layer)
        except TypeError:
            if layer is not None:
                self.layers.append(layer)
        else:
            [self.layers.append(layer) for layer in layers if layer is not None]
        

    def merge(self, format='png', size=None, bgcolor='#ffffff', transparent=False):
        """
        Merge the layers. If the format is not 'png' just return the last image.
        
        :param format: The image format for the result.
        :param size: The size for the merged output.
        :rtype: `ImageSource`
        """
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

class ImageSource(object):
    """
    This class wraps either a PIL image, a file-like object, or a file name.
    You can access the result as an image (`as_image` ) or a file-like buffer
    object (`as_buffer`).
    """
    def __init__(self, source, format='png', size=None, transparent=False):
        """
        :param source: the image
        :type source: PIL `Image`, image file object, or filename
        :param format: the format of the ``source``
        :param size: the size of the ``source`` in pixel
        """
        self.source = source
        self.format = format
        self.transparent = transparent
        self._size = size
    def as_image(self):
        """
        Returns the image or the loaded image.
        
        :rtype: PIL `Image`
        """
        if not isinstance(self.source, Image.Image):
            log.debug('file(%s) -> image', self.source)
            f = self.source
            if isinstance(f, basestring):
                f = open(f, 'rb')
            try:
                return Image.open(f)
            except StandardError:
                try:
                    f.close()
                except:
                    pass
                raise
        return self.source
    def as_buffer(self, format=None):
        """
        Returns the image as a file object.
        
        :param format: The format to encode an image.
                       Existing files will not be re-encoded.
        :rtype: file-like object
        """
        if isinstance(self.source, Image.Image):
            if not format:
                format = self.format
            log.debug('image -> buf(%s)' % (format,))
            return img_to_buf(self.source, format)
        if isinstance(self.source, basestring):
            log.debug('file(%s) -> buf' % self.source)
            return open(self.source, 'rb')
        if not hasattr(self.source, 'seek'):
            return ReadBufWrapper(self.source)
        return self.source
    @property
    def size(self):
        if isinstance(self.source, Image.Image):
            return self.source.size
        else:
            return self._size

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

def img_to_buf(img, format='png'):
    if format == 'png8':
        img = img.convert('RGB')
        img = img.convert('P', palette=Image.ADAPTIVE, dither=0)
    format = filter_format(format)
    buf = StringIO()
    defaults = {}
    if format == 'jpeg':
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

def font_file(font_name):
    font_name = font_name.replace(' ', '')
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                'fonts', font_name + '.ttf')
    return path
    
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
        if self._font is None:
            if self.font_name == 'default':
                self._font = ImageFont.load_default()
            else:
                self._font = ImageFont.truetype(font_file(self.font_name), self.font_size)
        return self._font
    
    def text_size(self, draw):
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
            draw.rectangle((0, 0, msg_img.size[0], msg_img.size[1]), fill=self.bgcolor)
        MessageImage.draw_msg(self, msg_img, draw)
    

class WatermarkImage(MessageImage):
    """
    Image with large, faded message. 
    """
    font_name = 'DejaVu Sans'
    font_size = 24
    font_color = (0, 0, 0)
    
    def __init__(self, message, format='png', odd=False, opacity=None):
        MessageImage.__init__(self, message, format)
        if opacity is None:
            opacity = 3
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
    

def _luminance(color):
    """
    Returns the luminance of a RGB tuple. Uses ITU-R 601-2 luma transform.
    """
    r, g, b = color
    return r * 299/1000 + g * 587/1000 + b * 114/1000

def filter_map():
    return { 'nearest': Image.NEAREST,
             'bilinear': Image.BILINEAR,
             'bicubic': Image.BICUBIC }
image_filter = filter_map()
del filter_map

class TileMerger(object):
    """
    Merge multiple tiles into one image.
    """
    def __init__(self, tile_grid, tile_size):
        """
        :param tile_grid: the grid size
        :type tile_grid: ``(int(x_tiles), int(y_tiles))``
        :param tile_size: the size of each tile
        """
        self.tile_grid = tile_grid
        self.tile_size = tile_size
    def merge(self, ordered_tiles, transparent=False):
        """
        Merge all tiles into one image.
        
        :param ordered_tiles: list of tiles, sorted row-wise (top to bottom)
        :rtype: `ImageSource`
        """
        if self.tile_grid == (1, 1):
            assert len(ordered_tiles) == 1
            if ordered_tiles[0] is not None:
                tile = ordered_tiles.pop()
                return ImageSource(tile.source, size=self.tile_size,
                                   transparent=transparent)
        src_size = self._src_size()
        result = Image.new("RGBA", src_size, (255, 255, 255, 255))
        for i, source in enumerate(ordered_tiles):
            if source is None:
                continue
            try:
                tile = source.as_image()
                tile.draft('RGBA', self.tile_size)
                pos = self._tile_offset(i)
                result.paste(tile, pos)
            except IOError, e:
                log.warn('unable to load tile %s, removing it (reason was: %s)'
                         % (source, str(e)))
                if isinstance(source.source, basestring):
                    if os.path.exists(source.source):
                        os.remove(source.source)
        return ImageSource(result, size=src_size, transparent=transparent)
    def _src_size(self):
        width = self.tile_grid[0]*self.tile_size[0]
        height = self.tile_grid[1]*self.tile_size[1]
        return width, height
    def _tile_offset(self, i):
        """
        Return the image offset (upper-left coord) of the i-th tile,
        where the tiles are ordered row-wise, top to bottom.
        """
        return (i%self.tile_grid[0]*self.tile_size[0],
                i//self.tile_grid[0]*self.tile_size[1])
    

class TileSplitter(object):
    """
    Splits a large image into multiple tiles.
    """
    def __init__(self, meta_tile, format):
        self.meta_img = meta_tile.as_image()
        if self.meta_img.mode == 'P' and format in ('png', 'gif'):
            self.meta_img = self.meta_img.convert('RGBA')
        self.format = format
    
    def get_tile(self, crop_coord, tile_size):
        """
        Return the cropped tile.
        :param crop_coord: the upper left pixel coord to start
        :param tile_size: width and height of the new tile
        :rtype: `ImageSource`
        """
        minx, miny = crop_coord
        maxx = minx + tile_size[0]
        maxy = miny + tile_size[1]
        
        crop = self.meta_img.crop((minx, miny, maxx, maxy))
        return ImageSource(crop, self.format)
    

class ImageTransformer(object):
    """
    Transform images between different bbox and spatial reference systems.
    
    :note: The transformation doesn't make a real transformation for each pixel,
           but a mesh transformation (see `PIL Image.transform`_).
           It will divide the target image into rectangles (a mesh). The
           source coordinates for each rectangle vertex will be calculated.
           The quadrilateral will then be transformed with the source coordinates
           into the destination quad (affine).
           
           This method will perform good transformation results if the number of
           quads is high enough (even transformations with strong distortions).
           Tests on images up to 1500x1500 have shown that meshes beyond 8x8
           will not improve the results.
           
           .. _PIL Image.transform:
              http://www.pythonware.com/library/pil/handbook/image.htm#Image.transform
           
           ::
              
                    src quad                   dst quad
                    .----.   <- coord-           .----.
                   /    /       transformation   |    |
                  /    /                         |    |
                 .----.   img-transformation ->  .----.----
                           |                     |    |
            ---------------.
            large src image                   large dst image
    """
    def __init__(self, src_srs, dst_srs, resampling=None, mesh_div=8):
        """
        :param src_srs: the srs of the source image
        :param dst_srs: the srs of the target image
        :param resampling: the resampling method used for transformation
        :type resampling: nearest|bilinear|bicubic
        :param mesh_div: the number of quads in each direction to use
                         for transformation (totals to ``mesh_div**2`` quads)
        
        """
        self.src_srs = src_srs
        self.dst_srs = dst_srs
        if resampling is None:
            resampling = base_config().image.resampling_method
        self.resampling = resampling
        self.mesh_div = mesh_div
        self.dst_bbox = self.dst_size = None
    
    def transform(self, src_img, src_bbox, dst_size, dst_bbox):
        """
        Transforms the `src_img` between the source and destination SRS
        of this ``ImageTransformer`` instance.
        
        When the ``src_srs`` and ``dst_srs`` are equal the image will be cropped
        and not transformed. If the `src_bbox` and `dst_bbox` are equal,
        the `src_img` itself will be returned.
        
        :param src_img: the source image for the transformation
        :param src_bbox: the bbox of the src_img
        :param dst_size: the size of the result image (in pizel)
        :type dst_size: ``(int(width), int(height))``
        :param dst_bbox: the bbox of the result image
        :return: the transformed image
        :rtype: `ImageSource`
        """
        if self._no_transformation_needed(src_img.size, src_bbox, dst_size, dst_bbox):
            return src_img
        elif self.src_srs == self.dst_srs:
            return self._transform_simple(src_img, src_bbox, dst_size, dst_bbox)
        else:
            return self._transform(src_img, src_bbox, dst_size, dst_bbox)
    
    def _transform_simple(self, src_img, src_bbox, dst_size, dst_bbox):
        """
        Do a simple crop/extend transformation.
        """
        src_quad = (0, 0, src_img.size[0], src_img.size[1])
        to_src_px = make_lin_transf(src_bbox, src_quad)
        minx, miny = to_src_px((dst_bbox[0], dst_bbox[3]))
        maxx, maxy = to_src_px((dst_bbox[2], dst_bbox[1]))
        
        src_res = (src_bbox[0]-src_bbox[2])/src_img.size[0]
        dst_res = (dst_bbox[0]-dst_bbox[2])/dst_size[0]
        
        tenth_px_res = abs(dst_res/(dst_size[0]*10))
        if abs(src_res-dst_res) < tenth_px_res:
            minx = int(round(minx))
            miny = int(round(miny))
            result = src_img.as_image().crop((minx, miny,
                                              minx+dst_size[0], miny+dst_size[1]))
        else:
            result = src_img.as_image().transform(dst_size, Image.EXTENT,
                                                  (minx, miny, maxx, maxy),
                                                  image_filter[self.resampling])
        return ImageSource(result, size=dst_size, transparent=src_img.transparent)
    
    def _transform(self, src_img, src_bbox, dst_size, dst_bbox):
        """
        Do a 'real' transformation with a transformed mesh (see above).
        """
        src_bbox = self.src_srs.align_bbox(src_bbox)
        dst_bbox = self.dst_srs.align_bbox(dst_bbox)
        src_size = src_img.size
        src_quad = (0, 0, src_size[0], src_size[1])
        dst_quad = (0, 0, dst_size[0], dst_size[1])
        to_src_px = make_lin_transf(src_bbox, src_quad)
        to_dst_w = make_lin_transf(dst_quad, dst_bbox)
        meshes = []
        def dst_quad_to_src(quad):
            src_quad = []
            for dst_px in [(quad[0], quad[1]), (quad[0], quad[3]),
                           (quad[2], quad[3]), (quad[2], quad[1])]:
                dst_w = to_dst_w(dst_px)
                src_w = self.dst_srs.transform_to(self.src_srs, dst_w)
                src_px = to_src_px(src_w)
                src_quad.extend(src_px)
            return quad, src_quad
        
        mesh_div = self.mesh_div
        while mesh_div > 1 and (dst_size[0] / mesh_div < 10 or dst_size[1] / mesh_div < 10):
            mesh_div -= 1
        for quad in griddify(dst_quad, mesh_div):
            meshes.append(dst_quad_to_src(quad))
        result = src_img.as_image().transform(dst_size, Image.MESH, meshes,
                                              image_filter[self.resampling])
        return ImageSource(result, size=self.dst_size, transparent=src_img.transparent)
    
    def _no_transformation_needed(self, src_size, src_bbox, dst_size, dst_bbox):
        """
        >>> src_bbox = (-2504688.5428486541, 1252344.271424327,
        ...             -1252344.271424327, 2504688.5428486541)
        >>> dst_bbox = (-2504688.5431999983, 1252344.2704,
        ...             -1252344.2719999983, 2504688.5416000001)
        >>> from mapproxy.core.srs import SRS
        >>> t = ImageTransformer(SRS(900913), SRS(900913))
        >>> t._no_transformation_needed((256, 256), src_bbox, (256, 256), dst_bbox)
        True
        """
        xres = (dst_bbox[2]-dst_bbox[0])/dst_size[0]
        yres = (dst_bbox[3]-dst_bbox[1])/dst_size[1]
        return (src_size == dst_size and
                self.src_srs == self.dst_srs and
                bbox_equals(src_bbox, dst_bbox, xres/10, yres/10))
    

def griddify(quad, steps):
    """
    Divides a box (`quad`) into multiple boxes (``steps x steps``).
    
    >>> list(griddify((0, 0, 500, 500), 2))
    [(0, 0, 250, 250), (250, 0, 500, 250), (0, 250, 250, 500), (250, 250, 500, 500)]
    """
    w = quad[2]-quad[0]
    h = quad[3]-quad[1]
    x_step = w / float(steps)
    y_step = h / float(steps)
    
    y = quad[1]
    for _ in range(steps):
        x = quad[0]
        for _ in range(steps):
            yield (int(x), int(y), int(x+x_step), int(y+y_step))
            x += x_step
        y += y_step

class TiledImage(object):
    """
    An image built-up from multiple tiles.
    """
    def __init__(self, tiles, tile_grid, tile_size, src_bbox, src_srs, transparent):
        """
        :param tiles: all tiles (sorted row-wise, top to bottom)
        :param tile_grid: the tile grid size
        :type tile_grid: ``(int(x_tiles), int(y_tiles))``
        :param tile_size: the size of each tile
        :param src_bbox: the bbox of all tiles
        :param src_srs: the srs of the bbox
        :param transparent: if the sources are transparent
        """
        self.tiles = tiles
        self.tile_grid = tile_grid
        self.tile_size = tile_size
        self.src_bbox = src_bbox
        self.src_srs = src_srs
        self.transparent = transparent
    
    def image(self):
        """
        Return the tiles as one merged image.
        
        :rtype: `ImageSource`
        """
        tm = TileMerger(self.tile_grid, self.tile_size)
        return tm.merge(self.tiles, transparent=self.transparent)
    
    def transform(self, req_bbox, req_srs, out_size):
        """
        Return the the tiles as one merged and transformed image.
        
        :param req_bbox: the bbox of the output image
        :param req_srs: the srs of the req_bbox
        :param out_size: the size in pixel of the output image
        :rtype: `ImageSource`
        """
        transformer = ImageTransformer(self.src_srs, req_srs)
        src_img = self.image()
        return transformer.transform(src_img, self.src_bbox, out_size, req_bbox)
    
