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


from mapproxy.image.opts import ImageOptions, create_image
from nose.tools import eq_

class TestCreateImage(object):
    def test_default(self):
        img = create_image((100, 100))
        eq_(img.size, (100, 100))
        eq_(img.mode, 'RGB')
        eq_(img.getcolors(), [(100*100, (255, 255, 255))])
    
    def test_transparent(self):
        img = create_image((100, 100), ImageOptions(transparent=True))
        eq_(img.size, (100, 100))
        eq_(img.mode, 'RGBA')
        eq_(img.getcolors(), [(100*100, (255, 255, 255, 0))])

    def test_transparent_rgb(self):
        img = create_image((100, 100), ImageOptions(mode='RGB', transparent=True))
        eq_(img.size, (100, 100))
        eq_(img.mode, 'RGB')
        eq_(img.getcolors(), [(100*100, (255, 255, 255))])
    
    def test_bgcolor(self):
        img = create_image((100, 100), ImageOptions(bgcolor=(200, 100, 0)))
        eq_(img.size, (100, 100))
        eq_(img.mode, 'RGB')
        eq_(img.getcolors(), [(100*100, (200, 100, 0))])
        
    def test_rgba_bgcolor(self):
        img = create_image((100, 100), ImageOptions(bgcolor=(200, 100, 0, 30)))
        eq_(img.size, (100, 100))
        eq_(img.mode, 'RGB')
        eq_(img.getcolors(), [(100*100, (200, 100, 0))])

    def test_rgba_bgcolor_transparent(self):
        img = create_image((100, 100), ImageOptions(bgcolor=(200, 100, 0, 30), transparent=True))
        eq_(img.size, (100, 100))
        eq_(img.mode, 'RGBA')
        eq_(img.getcolors(), [(100*100, (200, 100, 0, 30))])

    def test_rgba_bgcolor_rgba_mode(self):
        img = create_image((100, 100), ImageOptions(bgcolor=(200, 100, 0, 30), mode='RGBA'))
        eq_(img.size, (100, 100))
        eq_(img.mode, 'RGBA')
        eq_(img.getcolors(), [(100*100, (200, 100, 0, 30))])
        
    