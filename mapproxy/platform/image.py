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

if platform.system() == "Java":
    from jil import Image, ImageColor, ImageDraw, ImageFont
    
    class ImagePalette(object):
        def __init__(self, *args, **kw):
            raise NotImplementedError()
            
    def quantize(img, colors=256, alpha=False, defaults=None):
        return img.convert('P', palette=Image.ADAPTIVE, colors=colors)
    
else:
    try:
        from PIL import Image, ImageColor, ImageDraw, ImageFont, ImagePalette
    except ImportError:
        import Image, ImageColor, ImageDraw, ImageFont, ImagePalette
    
    def quantize(img, colors=256, alpha=False, defaults=None):
        if hasattr(Image, 'FASTOCTREE'):
            if not alpha:
                img = img.convert('RGB')
            img = img.quantize(colors, Image.FASTOCTREE)
        else:
            if alpha:
                alpha = img.split()[3]
                img = img.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=colors-1)
                mask = Image.eval(alpha, lambda a: 255 if a <=128 else 0)
                img.paste(255, mask)
                if defaults is not None:
                    defaults['transparency'] = 255
            else:
                img = img.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=colors)
           
        return img