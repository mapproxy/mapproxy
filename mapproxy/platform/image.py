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

import platform
import warnings

__all__ = ['Image', 'ImageColor', 'ImageDraw', 'ImageFont', 'ImagePalette',
           'ImageChops', 'quantize']

if platform.system() == "Java":
    from jil import Image, ImageColor, ImageDraw, ImageFont
    Image, ImageColor, ImageDraw, ImageFont # prevent pyflakes warnings
    
    class ImagePalette(object):
        def __init__(self, *args, **kw):
            raise NotImplementedError()
    
    class ImageChops(object):
        def __init__(self, *args, **kw):
            raise NotImplementedError()
    
    def quantize_jil(img, colors=256, alpha=False, defaults=None):
        return img.convert('P', palette=Image.ADAPTIVE, colors=colors)
    quantize = quantize_jil
else:
    try:
        from PIL import Image, ImageColor, ImageDraw, ImageFont, ImagePalette, ImageChops
        # prevent pyflakes warnings
        Image, ImageColor, ImageDraw, ImageFont, ImagePalette, ImageChops
    except ImportError:
        try:
            import Image, ImageColor, ImageDraw, ImageFont, ImagePalette, ImageChops
            # prevent pyflakes warnings
            Image, ImageColor, ImageDraw, ImageFont, ImagePalette, ImageChops
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