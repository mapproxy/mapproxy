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


from mapproxy.image.opts import ImageOptions, create_image, compatible_image_options
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


class TestCompatibleImageOptions(object):
    def test_formats(self):
        img_opts = compatible_image_options([
            ImageOptions(format='image/png'),
            ImageOptions(format='image/jpeg'),
        ])
        eq_(img_opts.format, 'image/png')

        img_opts = compatible_image_options([
            ImageOptions(format='image/png'),
            ImageOptions(format='image/jpeg'),
        ],
        ImageOptions(format='image/tiff'),
        )
        eq_(img_opts.format, 'image/tiff')

    def test_colors(self):
        img_opts = compatible_image_options([
            ImageOptions(colors=None),
            ImageOptions(colors=16),
        ])
        eq_(img_opts.colors, 16)

        img_opts = compatible_image_options([
            ImageOptions(colors=256),
            ImageOptions(colors=16),
        ])
        eq_(img_opts.colors, 256)

        img_opts = compatible_image_options([
            ImageOptions(colors=256),
            ImageOptions(colors=16),
        ],
        ImageOptions(colors=4)
        )
        eq_(img_opts.colors, 4)

        img_opts = compatible_image_options([
            ImageOptions(colors=256),
            ImageOptions(colors=0),
        ])
        eq_(img_opts.colors, 0)

    def test_transparent(self):
        img_opts = compatible_image_options([
            ImageOptions(transparent=False),
            ImageOptions(transparent=True),
        ])
        eq_(img_opts.transparent, False)

        img_opts = compatible_image_options([
            ImageOptions(transparent=None),
            ImageOptions(transparent=True),
        ])
        eq_(img_opts.transparent, True)

        img_opts = compatible_image_options([
            ImageOptions(transparent=None),
            ImageOptions(transparent=True),
        ],
        ImageOptions(transparent=None)
        )
        eq_(img_opts.transparent, True)

        img_opts = compatible_image_options([
            ImageOptions(transparent=True),
            ImageOptions(transparent=True),
        ])
        eq_(img_opts.transparent, True)

    def test_mode(self):
        img_opts = compatible_image_options([
            ImageOptions(mode='RGB'),
            ImageOptions(mode='P'),
        ])
        eq_(img_opts.mode, 'RGB')

        img_opts = compatible_image_options([
            ImageOptions(mode='RGBA'),
            ImageOptions(mode='P'),
        ])
        eq_(img_opts.mode, 'RGBA')

        img_opts = compatible_image_options([
            ImageOptions(mode='RGB'),
            ImageOptions(mode='P'),
        ])
        eq_(img_opts.mode, 'RGB')

        img_opts = compatible_image_options([
            ImageOptions(mode='RGB'),
            ImageOptions(mode='P'),
        ],
        ImageOptions(mode='P')
        )
        eq_(img_opts.mode, 'P')

