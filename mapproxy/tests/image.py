import os
import Image
import ImageDraw
import ImageColor

import tempfile
from nose.tools import eq_
from cStringIO import StringIO
from contextlib import contextmanager


def assert_image_mode(img, mode):
    pos = img.tell()
    try:
        img = Image.open(img)
        eq_(img.mode, mode)
    finally:
        img.seek(pos)
    

def check_format(img, format):
    assert globals()['is_' + format.lower()](img)

def has_magic_bytes(fileobj, bytes):
    pos = fileobj.tell()
    for magic in bytes:
        fileobj.seek(0)
        it_is = fileobj.read(len(magic)) == magic
        fileobj.seek(pos)
        if it_is:
            return True
    return False

magic_bytes = { 'png': ["\211PNG\r\n\032\n"],
                'tiff': ["MM\x00\x2a", "II\x2a\x00"],
                'geotiff': ["MM\x00\x2a", "II\x2a\x00"],
                'gif': ["GIF87a", "GIF89a"],
                'jpeg': ["\xFF\xD8", "GIF89a"],
                'bmp': ['BM']
                }

def create_is_x_functions():
    for type_, magic in magic_bytes.iteritems():
        def create_is_type(type_, magic):
            def is_type(fileobj):
                return has_magic_bytes(fileobj, magic)
            return is_type
        globals()['is_' + type_] = create_is_type(type_, magic)

create_is_x_functions()
del create_is_x_functions


def create_tmp_image(size):
    fd, out_file = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    print 'creating temp image %s (%r)' % (out_file, size)
    img = Image.new('RGBA', size)
    img.save(out_file, 'png')
    return out_file
    

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
def tmp_image(size, format='png'):
    img = create_debug_img(size)
    data = StringIO()
    img.save(data, format)
    data.seek(0)
    yield data