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
