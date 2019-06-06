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

from __future__ import print_function, division

import os
import tempfile

from io import BytesIO
from contextlib import contextmanager

from mapproxy.compat.image import (
    Image,
    ImageDraw,
    ImageColor,
)
from mapproxy.compat import string_type, iteritems



def assert_image_mode(img, mode):
    pos = img.tell()
    try:
        img = Image.open(img)
        assert img.mode == mode
    finally:
        img.seek(pos)


def check_format(img, format):
    assert globals()['is_' + format.lower()](img), 'img is not %s' % format

def has_magic_bytes(fileobj, bytes):
    pos = fileobj.tell()
    for magic in bytes:
        fileobj.seek(0)
        it_is = fileobj.read(len(magic)) == magic
        fileobj.seek(pos)
        if it_is:
            return True
    return False

magic_bytes = { 'png': [b"\211PNG\r\n\032\n"],
                'tiff': [b"MM\x00\x2a", b"II\x2a\x00"],
                'geotiff': [b"MM\x00\x2a", b"II\x2a\x00"],
                'gif': [b"GIF87a", b"GIF89a"],
                'jpeg': [b"\xFF\xD8"],
                'bmp': [b'BM']
               }

def create_is_x_functions():
    for type_, magic in iteritems(magic_bytes):
        def create_is_type(type_, magic):
            def is_type(fileobj):
                if not hasattr(fileobj, 'read'):
                    fileobj = BytesIO(fileobj)
                return has_magic_bytes(fileobj, magic)
            return is_type
        globals()['is_' + type_] = create_is_type(type_, magic)

create_is_x_functions()
del create_is_x_functions


def is_transparent(img_data):
    data = BytesIO(img_data)
    img = Image.open(data)
    if img.mode == 'P':
        img = img.convert('RGBA')
    if img.mode == 'RGBA':
        return any(img.histogram()[-256:-1])

    raise NotImplementedError(
        'assert_is_transparent works only for RGBA images, got %s image' % img.mode)


def img_from_buf(buf):
    data = BytesIO(buf)
    return Image.open(data)


def bgcolor_ratio(img_data):
    """
    Return the ratio of the primary/bg color. 1 == only bg color.
    """
    data = BytesIO(img_data)
    img = Image.open(data)
    total_colors = img.size[0] * img.size[1]
    colors = img.getcolors()
    colors.sort()
    bgcolor = colors[-1][0]
    return bgcolor/total_colors

def create_tmp_image_file(size, two_colored=False):
    fd, out_file = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    img = Image.new('RGBA', size)
    if two_colored:
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, img.size[0]//2, img.size[1]),
            fill=ImageColor.getrgb('white'))
    img.save(out_file, 'png')
    return out_file

def create_image(size, color=None, mode=None):
    if color is not None:
        if isinstance(color, string_type):
            if mode is None:
                mode = 'RGB'
            img = Image.new(mode, size, color=color)
        else:
            if mode is None:
                mode = 'RGBA' if len(color) == 4 else 'RGB'
            img = Image.new(mode, size, color=tuple(color))
    else:
        img = create_debug_img(size)
    return img

def create_tmp_image_buf(size, format='png', color=None, mode='RGB'):
    img = create_image(size, color, mode)
    data = BytesIO()
    img.save(data, format)
    data.seek(0)
    return data

def create_tmp_image(size, format='png', color=None, mode='RGB'):
    data = create_tmp_image_buf(size, format, color, mode)
    return data.read()


def create_debug_img(size, transparent=True):
    if transparent:
        img = Image.new("RGBA", size)
    else:
        img = Image.new("RGB", size, ImageColor.getrgb("#EEE"))

    draw = ImageDraw.Draw(img)
    draw_pattern(draw, size)
    return img

def draw_pattern(draw, size):
    w, h = size
    black_color = ImageColor.getrgb("black")
    draw.rectangle((0, 0, w-1, h-1), outline=black_color)
    draw.ellipse((0, 0, w-1, h-1), outline=black_color)
    step = w/16.0
    for i in range(16):
        color = ImageColor.getrgb('#3' + hex(16-i)[-1] + hex(i)[-1])
        draw.line((i*step, 0, i*step, h), fill=color)
    step = h/16.0
    for i in range(16):
        color = ImageColor.getrgb('#' + hex(16-i)[-1] + hex(i)[-1] + '3')
        draw.line((0, i*step, w, i*step), fill=color)


@contextmanager
def tmp_image(size, format='png', color=None, mode='RGB'):
    if color is not None:
        img = Image.new(mode, size, color=color)
    else:
        img = create_debug_img(size)
    if format == 'jpeg':
        img = img.convert('RGB')
    data = BytesIO()
    img.save(data, format)
    data.seek(0)
    yield data


def assert_img_colors_eq(img1, img2, delta=1, pixel_delta=1):
    """
    assert that the colors of two images are equal.
    Use `delta` to accept small color variations
    (e.g. (255, 0, 127) == (254, 1, 128) with delta=1)
    Use `pixel_delta` to accept small variations in the number of pixels for each color
    (in percent of total pixels).

    `img1` and `img2` needs to be an image or list of
    colors like ``[(n, (r, g, b)), (n, (r, g, b)), ...]``
    """
    colors1 = sorted(img1.getcolors() if hasattr(img1, 'getcolors') else img1)
    colors2 = sorted(img2.getcolors() if hasattr(img2, 'getcolors') else img2)

    total_pixels = sum(n for n, _ in colors1)
    for (n1, c1), (n2, c2) in zip(colors1, colors2):
        assert abs(n1 - n2) < (total_pixels / 100 * pixel_delta), 'num colors not equal: %r != %r' % (colors1, colors2)
        assert_colors_eq(c1, c2)

assert_colors_equal = assert_img_colors_eq

def assert_colors_eq(c1, c2, delta=1):
    """
    assert that two colors are equal. Use `delta` to accept
    small color variations.
    """
    assert abs(c1[0] - c2[0]) <= delta, 'colors not equal: %r != %r' % (c1, c2)
    assert abs(c1[1] - c2[1]) <= delta, 'colors not equal: %r != %r' % (c1, c2)
    assert abs(c1[2] - c2[2]) <= delta, 'colors not equal: %r != %r' % (c1, c2)
