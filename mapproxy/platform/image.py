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

import platform

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
        import Image, ImageColor, ImageDraw, ImageFont, ImagePalette, ImageChops
        # prevent pyflakes warnings
        Image, ImageColor, ImageDraw, ImageFont, ImagePalette, ImageChops
    
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