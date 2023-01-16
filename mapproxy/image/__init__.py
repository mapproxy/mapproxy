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

"""
Image and tile manipulation (transforming, merging, etc).
"""
import io
from io import BytesIO


from mapproxy.compat.image import Image, ImageChops, ImageFileDirectory_v2, TiffTags
from mapproxy.image.opts import create_image, ImageFormat
from mapproxy.config import base_config
from mapproxy.srs import make_lin_transf, get_epsg_num
from mapproxy.compat import string_type

import logging
from functools import reduce
log = logging.getLogger('mapproxy.image')



magic_bytes = [
    ('png', (b"\211PNG\r\n\032\n",)),
    ('jpeg', (b"\xFF\xD8",)),
    ('tiff', (b"MM\x00\x2a", b"II\x2a\x00",)),
    ('gif', (b"GIF87a", b"GIF89a",)),
]

def peek_image_format(buf):
    buf.seek(0)
    header = buf.read(10)
    buf.seek(0)
    for format, bytes in magic_bytes:
        if header.startswith(bytes):
            return format
    return None

TIFF_MODELPIXELSCALETAG = 33550
TIFF_MODELTIEPOINTTAG = 33922
TIFF_GEOKEYDIRECTORYTAG = 34735

class GeoReference(object):
    def __init__(self, bbox, srs):
        self.bbox = bbox
        self.srs = srs


    def tiepoints(self):
        return (
            0.0, 0.0, 0.0,
            self.bbox[0], self.bbox[3], 0.0,
        )

    def pixelscale(self, img_size):
        width = self.bbox[2] - self.bbox[0]
        height = self.bbox[3] - self.bbox[1]
        return (
            float(width)/img_size[0], float(height)/img_size[1], 0.0,
        )

    def tiff_tags(self, img_size):
        tags = ImageFileDirectory_v2()
        tags[TIFF_MODELPIXELSCALETAG] = self.pixelscale(img_size)
        tags.tagtype[TIFF_MODELPIXELSCALETAG] = TiffTags.DOUBLE
        tags[TIFF_MODELTIEPOINTTAG] = self.tiepoints()
        tags.tagtype[TIFF_MODELTIEPOINTTAG] = TiffTags.DOUBLE

        model_type = 2 if self.srs.is_latlong else 1
        tags[TIFF_GEOKEYDIRECTORYTAG] = (
            1, 1, 0, 4, # {KeyDirectoryVersion, KeyRevision, MinorRevision, NumberOfKeys}
            1024, 0, 1, model_type, # 1 projected, 2 geographic (lat/long)
            1025, 0, 1, 1, # 1 RasterIsArea, 2 RasterIsPoint
            3072, 0, 1, get_epsg_num(self.srs.srs_code),
        )
        tags.tagtype[TIFF_GEOKEYDIRECTORYTAG] = TiffTags.SHORT
        return tags


class ImageSource(object):
    """
    This class wraps either a PIL image, a file-like object, or a file name.
    You can access the result as an image (`as_image` ) or a file-like buffer
    object (`as_buffer`).
    """

    def __init__(self, source, size=None, image_opts=None, cacheable=True, georef=None):
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
        self.image_opts = image_opts
        self._size = size
        self.cacheable = cacheable
        self.georef = georef

    @property
    def source(self):
        return self._img or self._buf or self._fname

    @source.setter
    def source(self, source):
        self._img = None
        self._buf = None
        if isinstance(source, string_type):
            self._fname = source
        elif isinstance(source, Image.Image):
            self._img = source
        else:
            self._buf = source

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
            except Exception:
                self.close_buffers()
                raise
            self._img = img
        if self.image_opts and self.image_opts.transparent and self._img.mode == 'P':
            self._img = self._img.convert('RGBA')
        return self._img

    def _make_seekable_buf(self):
        if not self._buf and self._fname:
            self._buf = open(self._fname, 'rb')
        else:
            try:
                self._buf.seek(0)
            except (io.UnsupportedOperation, AttributeError):
                # PIL needs file objects with seek
                self._buf = BytesIO(self._buf.read())

    def _make_readable_buf(self):
        if not self._buf and self._fname:
            self._buf = open(self._fname, 'rb')
        elif not hasattr(self._buf, 'seek'):
            if not isinstance(self._buf, ReadBufWrapper):
                self._buf = ReadBufWrapper(self._buf)
        else:
            try:
                self._buf.seek(0)
            except (io.UnsupportedOperation, AttributeError):
                # PIL needs file objects with seek
                self._buf = BytesIO(self._buf.read())


    def as_buffer(self, image_opts=None, format=None, seekable=False):
        """
        Returns the image as a file object.

        :param format: The format to encode an image.
                       Existing files will not be re-encoded.
        :rtype: file-like object
        """
        if format:
            image_opts = (image_opts or self.image_opts).copy()
            image_opts.format = ImageFormat(format)
        if not self._buf and not self._fname:
            if image_opts is None:
                image_opts = self.image_opts
            log.debug('image -> buf(%s)' % (image_opts.format,))
            self._buf = img_to_buf(self._img, image_opts=image_opts, georef=self.georef)
        else:
            self._make_seekable_buf() if seekable else self._make_readable_buf()
            if self.image_opts and image_opts and not self.image_opts.format and image_opts.format:
                # need actual image_opts.format for next check
                self.image_opts = self.image_opts.copy()
                self.image_opts.format = peek_image_format(self._buf)
            if self.image_opts and image_opts and self.image_opts.format != image_opts.format:
                log.debug('converting image from %s -> %s' % (self.image_opts, image_opts))
                self.source = self.as_image()
                self._buf = None
                self.image_opts = image_opts
                # hide fname to prevent as_buffer from reading the file
                fname = self._fname
                self._fname = None
                self.as_buffer(image_opts)
                self._fname = fname
        return self._buf

    @property
    def size(self):
        if self._size is None:
            self._size = self.as_image().size
        return self._size

def SubImageSource(source, size, offset, image_opts, cacheable=True):
    """
    Create a new ImageSource with `size` and `image_opts` and
    place `source` image at `offset`.
    """
    # force new image to contain alpha channel
    new_image_opts = image_opts.copy()
    new_image_opts.transparent = True
    img = create_image(size, new_image_opts)

    if not hasattr(source, 'as_image'):
        source = ImageSource(source)
    subimg = source.as_image()
    img.paste(subimg, offset)
    return ImageSource(img, size=size, image_opts=new_image_opts, cacheable=cacheable)

class BlankImageSource(object):
    """
    ImageSource for transparent or solid-color images.
    Implements optimized as_buffer() method.
    """
    def __init__(self, size, image_opts, cacheable=False):
        self.size = size
        self.image_opts = image_opts
        self._buf = None
        self._img = None
        self.cacheable = cacheable

    def as_image(self):
        if not self._img:
            self._img = create_image(self.size, self.image_opts)
        return self._img

    def as_buffer(self, image_opts=None, format=None, seekable=False):
        if not self._buf:
            image_opts = (image_opts or self.image_opts).copy()
            if format:
                image_opts.format = ImageFormat(format)
            image_opts.colors = 0
            self._buf = img_to_buf(self.as_image(), image_opts=image_opts)
        return self._buf

    def close_buffers(self):
        pass

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
            self.stringio = BytesIO(self.readbuf.read())
        return getattr(self.stringio, name)

def img_has_transparency(img):
    if img.mode == 'P':
        if img.info.get('transparency', False):
            return True
        # convert to RGBA and check alpha channel
        img = img.convert('RGBA')
    if img.mode == 'RGBA':
        # any alpha except fully opaque
        return any(img.histogram()[-256:-1])
    return False

def img_to_buf(img, image_opts, georef=None):
    defaults = {}
    image_opts = image_opts.copy()

    # convert I or L images to target mode
    if image_opts.mode and img.mode[0] in ('I', 'L') and img.mode != image_opts.mode:
        img = img.convert(image_opts.mode)

    if (image_opts.colors is None and base_config().image.paletted
        and image_opts.format.endswith('png')):
        # force 255 colors for png with globals.image.paletted
        image_opts.colors = 255

    format = filter_format(image_opts.format.ext)
    if format == 'mixed':
        if img_has_transparency(img):
            format = 'png'
        else:
            format = 'jpeg'
            image_opts.colors = None
            image_opts.transparent = False

    # quantize if colors is set, but not if we already have a paletted image
    if image_opts.colors and not (img.mode == 'P' and len(img.getpalette()) == image_opts.colors*3):
        quantizer = None
        if 'quantizer' in image_opts.encoding_options:
            quantizer = image_opts.encoding_options['quantizer']
        if image_opts.transparent:
            img = quantize(img, colors=image_opts.colors, alpha=True,
                defaults=defaults, quantizer=quantizer)
        else:
            img = quantize(img, colors=image_opts.colors,
                quantizer=quantizer)
        if hasattr(Image, 'RLE'):
            defaults['compress_type'] = Image.RLE

    buf = BytesIO()
    if format == 'jpeg':
        img = img.convert('RGB')
        if 'jpeg_quality' in image_opts.encoding_options:
            defaults['quality'] = image_opts.encoding_options['jpeg_quality']
        else:
            defaults['quality'] = base_config().image.jpeg_quality

    elif format == 'tiff':
        if georef:
            tags = georef.tiff_tags(img.size)
            defaults['tiffinfo'] = tags
        if 'tiff_compression' in image_opts.encoding_options:
            defaults['compression'] = image_opts.encoding_options['tiff_compression']
            if defaults['compression'] == 'jpeg':
                if 'jpeg_quality' in image_opts.encoding_options:
                    defaults['quality'] = image_opts.encoding_options['jpeg_quality']

    # unsupported transparency tuple can still be in non-RGB img.infos
    # see: https://github.com/python-pillow/Pillow/pull/2633
    if format == 'png' and img.mode != 'RGB' and 'transparency' in img.info and isinstance(img.info['transparency'], tuple):
        del img.info['transparency']

    img.save(buf, format, **defaults)
    buf.seek(0)
    return buf

def quantize(img, colors=256, alpha=False, defaults=None, quantizer=None):
    if hasattr(Image, 'FASTOCTREE') and quantizer in (None, 'fastoctree'):
        if not alpha:
            img = img.convert('RGB')
        try:
            if img.mode == 'P':
                # quantize with alpha does not work with P images
                img = img.convert('RGBA')
            img = img.quantize(colors, Image.FASTOCTREE)
        except ValueError:
            pass
    else:
        if alpha and img.mode == 'RGBA':
            img.load() # split might fail if image is not loaded
            alpha = img.split()[3]
            img = img.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=colors-1)
            mask = Image.eval(alpha, lambda a: 255 if a <=128 else 0)
            img.paste(255, mask)
            if defaults is not None:
                defaults['transparency'] = 255
        else:
            img = img.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=colors)

    return img


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
    image_opts = img.image_opts.copy()
    image_opts.transparent = True
    image_opts.mode = 'RGBA'
    return ImageSource(result, size=result.size, image_opts=image_opts)

def _make_transparent(img, color, tolerance=10):
    img.load()

    if img.mode == 'P':
        img = img.convert('RGBA')

    channels = img.split()
    mask_channels = []
    for ch, c in zip(channels, color):
        # create bit mask for each matched color
        low_c, high_c = c-tolerance, c+tolerance
        mask_channels.append(Image.eval(ch, lambda x: 255 if low_c <= x <= high_c else 0))

    # multiply channel bit masks to get a single mask
    alpha = reduce(ImageChops.multiply, mask_channels)
    # invert to get alpha channel
    alpha = ImageChops.invert(alpha)

    if len(channels) == 4:
        # multiply with existing alpha
        alpha = ImageChops.multiply(alpha, channels[-1])

    img.putalpha(alpha)
    return img

def bbox_position_in_image(bbox, size, src_bbox):
    """
    Calculate the position of ``bbox`` in an image of ``size`` and ``src_bbox``.
    Returns the sub-image size and the offset in pixel from top-left corner
    and the sub-bbox.

    >>> bbox_position_in_image((-180, -90, 180, 90), (600, 300), (-180, -90, 180, 90))
    ((600, 300), (0, 0), (-180, -90, 180, 90))
    >>> bbox_position_in_image((-200, -100, 200, 100), (600, 300), (-180, -90, 180, 90))
    ((540, 270), (30, 15), (-180, -90, 180, 90))
    >>> bbox_position_in_image((-200, -50, 200, 100), (600, 300), (-180, -90, 180, 90))
    ((540, 280), (30, 20), (-180, -50, 180, 90))
    >>> bbox_position_in_image((586400,196400,752800,362800), (256, 256), (586400,196400,752800,350000))
    ((256, 237), (0, 19), (586400, 196400, 752800, 350000))
    """
    coord_to_px = make_lin_transf(bbox, (0, 0) + size)
    offsets = [0, size[1], size[0], 0]
    sub_bbox = list(bbox)
    if src_bbox[0] > bbox[0]:
        sub_bbox[0] = src_bbox[0]
        x, y = coord_to_px((src_bbox[0], 0))
        offsets[0] = int(x)
    if src_bbox[1] > bbox[1]:
        sub_bbox[1] = src_bbox[1]
        x, y = coord_to_px((0, src_bbox[1]))
        offsets[1] = int(y)

    if src_bbox[2] < bbox[2]:
        sub_bbox[2] = src_bbox[2]
        x, y = coord_to_px((src_bbox[2], 0))
        offsets[2] = int(x)

    if src_bbox[3] < bbox[3]:
        sub_bbox[3] = src_bbox[3]
        x, y = coord_to_px((0, src_bbox[3]))
        offsets[3] = int(y)

    size = abs(offsets[2] - offsets[0]), abs(offsets[1] - offsets[3])
    return size, (offsets[0], offsets[3]), tuple(sub_bbox)
