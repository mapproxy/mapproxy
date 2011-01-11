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

from __future__ import with_statement
from mapproxy.platform.image import Image
from mapproxy.image import ImageSource, concat_legends
from mapproxy.test.image import is_png

class Test_Concat_Legends(object):
    def test_concatenation(self):
        legends = []
        img_1 = Image.new(mode='RGBA', size=(30,10), color="red")
        img_2 = Image.new(mode='RGBA', size=(10,10), color="black")
        img_3 = Image.new(mode='RGBA', size=(50,80), color="blue")
        legends.append(ImageSource(img_1))
        legends.append(ImageSource(img_2))
        legends.append(ImageSource(img_3))
        source = concat_legends(legends)
        src_img = source.as_image()
        assert src_img.getpixel((0,90)) == (255,0,0,255)
        assert src_img.getpixel((0,80)) == (0,0,0,255)
        assert src_img.getpixel((0,0)) == (0,0,255,255)
        assert src_img.getpixel((49,99)) == (255,255,255,0)
        assert is_png(source.as_buffer())
