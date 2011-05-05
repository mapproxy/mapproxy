# -:- encoding: utf-8 -:-
# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

import copy
from mapproxy.platform.image import Image, ImageColor

class ImageOptions(object):
    def __init__(self, mode=None, transparent=False, opacity=None, resampling=None,
        format=None, bgcolor=None, colors=None):
        self.transparent = transparent
        self.opacity = opacity
        self.resampling = resampling
        if format is not None:
            format = ImageFormat(format)
        self.format = format
        self.mode = mode or self.transparent and 'RGBA' or 'RGB'
        self.bgcolor = bgcolor
        self.colors = colors
    
    def __repr__(self):
        options = []
        for k in dir(self):
            if k.startswith('_'):
                continue
            v = getattr(self, k)
            if v and not hasattr(v, 'im_func'):
                options.append('%s=%r' % (k, v))
        return 'ImageOptions(%s)' % (', '.join(options), )
    
    def copy(self):
        return copy.copy(self)

class ImageFormat(str):
    def __new__(cls, value, *args, **keywargs):
        if isinstance(value, ImageFormat):
            return value
        return str.__new__(cls, value)
    
    @property
    def mime_type(self):
        if self.startswith('image/'):
            return self
        return 'image/' + self

    @property
    def ext(self):
        ext = self
        if '/' in ext:
            ext = ext.split('/', 1)[1]
        if ';' in ext:
            ext = ext.split(';', 1)[0]
        
        return ext.strip()
        
def create_image(size, image_opts=None):
    """
    Create a new image that is compatible with the given `image_opts`.
    Takes into account mode, transparent, bgcolor.
    """
    if image_opts is None:
        mode = 'RGB'
        bgcolor = (255, 255, 255)
    else:
        mode = image_opts.mode
        bgcolor = image_opts.bgcolor or (255, 255, 255)
        
        if isinstance(bgcolor, basestring):
            bgcolor = ImageColor.getrgb(bgcolor)
        
        if image_opts.transparent and len(bgcolor) == 3:
            bgcolor = bgcolor + (0, )
    
    return Image.new(mode, size, bgcolor)


class ImageFormats(object):
    def __init__(self):
        self.format_options = {}
    
    def add(self, opts):
        assert opts.format is not None
        self.format_options[opts.format] = opts
    
    def options(self, format):
        opts = self.format_options.get(format)
        if not opts:
            opts = ImageOptions(transparent=False, format=format)
        return opts