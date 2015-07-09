# This file is part of the MapProxy project.
# Copyright (C) 2012 Omniscale <http://omniscale.de>
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

from mapproxy.compat.image import Image
from mapproxy.srs import SRS
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.image.mask import mask_image_source_from_coverage
from mapproxy.util.coverage import load_limited_to
from mapproxy.test.image import assert_img_colors_eq

try:
    from shapely.geometry import Polygon
    geom_support = True
except ImportError:
    geom_support = False

if not geom_support:
    from nose.plugins.skip import SkipTest
    raise SkipTest('requires Shapely')


def coverage(geom, srs='EPSG:4326'):
    return load_limited_to({'srs': srs, 'geometry': geom})

class TestMaskImage(object):
    def test_mask_outside_of_image_transparent(self):
        img = ImageSource(Image.new('RGB', (100, 100), color=(100, 0, 200)),
            image_opts=ImageOptions(transparent=True))
        result = mask_image_source_from_coverage(img, [0, 0, 10, 10], SRS(4326), coverage([20, 20, 30, 30]))
        assert_img_colors_eq(result.as_image().getcolors(), [((100*100), (255, 255, 255, 0))])

    def test_mask_outside_of_image_bgcolor(self):
        img = ImageSource(Image.new('RGB', (100, 100), color=(100, 0, 200)),
            image_opts=ImageOptions(bgcolor=(200, 30, 120)))

        result = mask_image_source_from_coverage(img, [0, 0, 10, 10], SRS(4326), coverage([20, 20, 30, 30]))
        assert_img_colors_eq(result.as_image().getcolors(), [((100*100), (200, 30, 120))])

    def test_mask_partial_image_bgcolor(self):
        img = ImageSource(Image.new('RGB', (100, 100), color=(100, 0, 200)),
            image_opts=ImageOptions(bgcolor=(200, 30, 120)))

        result = mask_image_source_from_coverage(img, [0, 0, 10, 10], SRS(4326), coverage([5, 5, 30, 30]))
        assert_img_colors_eq(result.as_image().getcolors(),
            [(7500, (200, 30, 120)), (2500, (100, 0, 200))])

    def test_mask_partial_image_transparent(self):
        img = ImageSource(Image.new('RGB', (100, 100), color=(100, 0, 200)),
            image_opts=ImageOptions(transparent=True))

        result = mask_image_source_from_coverage(img, [0, 0, 10, 10], SRS(4326), coverage([5, 5, 30, 30]))
        assert_img_colors_eq(result.as_image().getcolors(),
            [(7500, (255, 255, 255, 0)), (2500, (100, 0, 200, 255))])

    def test_wkt_mask_partial_image_transparent(self):
        img = ImageSource(Image.new('RGB', (100, 100), color=(100, 0, 200)),
            image_opts=ImageOptions(transparent=True))

        # polygon with hole
        geom = 'POLYGON((2 2, 2 8, 8 8, 8 2, 2 2), (4 4, 4 6, 6 6, 6 4, 4 4))'

        result = mask_image_source_from_coverage(img, [0, 0, 10, 10], SRS(4326), coverage(geom))
        # 60*61 - 20*21 = 3240
        assert_img_colors_eq(result.as_image().getcolors(),
            [(10000-3240, (255, 255, 255, 0)), (3240, (100, 0, 200, 255))])

    def test_shapely_mask_with_transform_partial_image_transparent(self):
        img = ImageSource(Image.new('RGB', (100, 100), color=(100, 0, 200)),
            image_opts=ImageOptions(transparent=True))

        p = Polygon([(0, 0), (222000, 0), (222000, 222000), (0, 222000)]) # ~ 2x2 degres

        result = mask_image_source_from_coverage(img, [0, 0, 10, 10], SRS(4326), coverage(p, 'EPSG:3857'))
        # 20*20 = 400
        assert_img_colors_eq(result.as_image().getcolors(),
            [(10000-400, (255, 255, 255, 0)), (400, (100, 0, 200, 255))])
