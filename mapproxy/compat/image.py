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

import warnings

__all__ = ['Image', 'ImageColor', 'ImageDraw', 'ImageFont', 'ImagePalette',
           'ImageChops', 'quantize']

try:
    import PIL
    from PIL import Image, ImageColor, ImageDraw, ImageFont, ImagePalette, ImageChops, ImageMath
    from PIL.TiffImagePlugin import ImageFileDirectory_v2, TiffTags
    # prevent pyflakes warnings
    Image, ImageColor, ImageDraw, ImageFont, ImagePalette, ImageChops, ImageMath
    ImageFileDirectory_v2, TiffTags
    PIL_VERSION = getattr(PIL, '__version__') or getattr(PIL, 'PILLOW_VERSION')
except ImportError:
    # allow MapProxy to start without PIL (for tilecache only).
    # issue warning and raise ImportError on first use of
    # a function that requires PIL
    warnings.warn('PIL is not available')
    class NoPIL(object):
        def __getattr__(self, name):
            if name.startswith('__'):
                raise AttributeError()
            raise ImportError('PIL is not available')
    ImageDraw = ImageFont = ImagePalette = ImageChops = NoPIL()
    # add some dummy stuff required on import/load time
    Image = NoPIL()
    Image.NEAREST = Image.BILINEAR = Image.BICUBIC = 1
    Image.Image = NoPIL
    ImageColor = NoPIL()
    ImageColor.getrgb = lambda x: x
    PIL_VERSION = None

def has_alpha_composite_support():
    return hasattr(Image, 'alpha_composite')

def transform_uses_center():
    # transformation behavior changed with Pillow 3.4 to use pixel centers
    # https://github.com/python-pillow/Pillow/commit/5232361718bae0f0ccda76bfd5b390ebf9179b18
    if not PIL_VERSION or PIL_VERSION.startswith(('1.', '2.', '3.0', '3.1', '3.2', '3.3')):
        return False
    return True

def quantize_pil(img, colors=256, alpha=False, defaults=None):
    if hasattr(Image, 'FASTOCTREE'):
        if not alpha:
            img = img.convert('RGB')
        img = img.quantize(colors, Image.FASTOCTREE)
    else:
        if alpha:
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
quantize = quantize_pil
