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

from mapproxy.platform.image import Image

class ImageOptions(object):
    def __init__(self, mode=None, transparent=False, opacity=None, resampling=None,
        format=None, bgcolor=None):
        self.transparent = transparent
        self.opacity = opacity
        self.resampling = resampling
        self.format = format
        self.mode = mode or self.transparent and 'RGBA' or 'RGB'
        self.bgcolor = bgcolor
    
    def __repr__(self):
        options = []
        for k in dir(self):
            if k.startswith('_'):
                continue
            v = getattr(self, k)
            if v:
                options.append('%s=%r' % (k, v))
        return 'ImageOptions(%s)' % (', '.join(options), )

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
        
        if image_opts.transparent and len(bgcolor) == 3:
            bgcolor = bgcolor + (0, )
    
    
    return Image.new(mode, size, bgcolor)