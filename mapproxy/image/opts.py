# -:- encoding: utf-8 -:-
# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

import copy

class ImageOptions(object):
    def __init__(self, mode=None, transparent=None, opacity=None, resampling=None,
        format=None, bgcolor=None, colors=None, encoding_options=None):
        self.transparent = transparent
        self.opacity = opacity
        self.resampling = resampling
        if format is not None:
            format = ImageFormat(format)
        self.format = format
        self.mode = mode
        self.bgcolor = bgcolor
        self.colors = colors
        self.encoding_options = encoding_options or {}
    
    def __repr__(self):
        options = []
        for k in dir(self):
            if k.startswith('_'):
                continue
            v = getattr(self, k)
            if v is not None and not hasattr(v, 'im_func'):
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
    
    def __eq__(self, other):
        if isinstance(other, basestring):
            other = ImageFormat(other)
        elif not isinstance(other, ImageFormat):
            return NotImplemented
        
        return self.ext == other.ext
    
    def __ne__(self, other):
        return not (self == other)
    
def create_image(size, image_opts=None):
    """
    Create a new image that is compatible with the given `image_opts`.
    Takes into account mode, transparent, bgcolor.
    """
    from mapproxy.platform.image import Image, ImageColor
    
    if image_opts is None:
        mode = 'RGB'
        bgcolor = (255, 255, 255)
    else:
        mode = image_opts.mode
        if mode in (None, 'P'):
            if image_opts.transparent:
                mode = 'RGBA'
            else:
                mode = 'RGB'
        
        bgcolor = image_opts.bgcolor or (255, 255, 255)
        
        if isinstance(bgcolor, basestring):
            bgcolor = ImageColor.getrgb(bgcolor)
        
        if image_opts.transparent and len(bgcolor) == 3:
            bgcolor = bgcolor + (0, )
        
        if image_opts.mode == 'I':
            bgcolor = bgcolor[0]
    
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

def compatible_image_options(img_opts, base_opts=None):
    """
    Return ImageOptions that is compatible with all given `img_opts`.
    
    """
    if any(True for o in img_opts if o.colors == 0):
        colors = 0
    else:
        colors = max(o.colors for o in img_opts)
    
    transparent = None
    for o in img_opts:
        if o.transparent == False:
            transparent = False
            break
        if o.transparent == True:
            transparent = True
    
    # I < P < RGB < RGBA :)
    mode = max(o.mode for o in img_opts)
    
    if base_opts:
        options = base_opts.copy()
        if options.colors is None:
            options.colors = colors
        if options.mode is None:
            options.mode = mode
        if options.transparent is None:
            options.transparent = transparent
    else:
        options = img_opts[0].copy()
        options.colors = colors
        options.transparent = transparent
        options.mode = mode
    
    return options