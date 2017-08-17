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

from mapproxy.compat.image import Image, ImageDraw
from mapproxy.srs import SRS, make_lin_transf
from mapproxy.image import ImageSource
from mapproxy.image.opts import create_image
from mapproxy.util.geom import flatten_to_polygons

def mask_image_source_from_coverage(img_source, bbox, bbox_srs, coverage,
    image_opts=None):
    if image_opts is None:
        image_opts = img_source.image_opts
    img = img_source.as_image()
    img = mask_image(img, bbox, bbox_srs, coverage)
    result = create_image(img.size, image_opts)
    result.paste(img, (0, 0), img)
    return ImageSource(result, image_opts=image_opts)

def mask_image(img, bbox, bbox_srs, coverage):
    geom = mask_polygons(bbox, SRS(bbox_srs), coverage)
    mask = image_mask_from_geom(img.size, bbox, geom)
    img = img.convert('RGBA')
    img.paste((255, 255, 255, 0), (0, 0), mask)
    return img

def mask_polygons(bbox, bbox_srs, coverage):
    coverage = coverage.transform_to(bbox_srs)
    coverage = coverage.intersection(bbox, bbox_srs)
    return flatten_to_polygons(coverage.geom)

def image_mask_from_geom(size, bbox, polygons):
    mask = Image.new('L', size, 255)
    if len(polygons) == 0:
        return mask

    transf = make_lin_transf(bbox, (0, 0) + size)

    # use negative ~.1 pixel buffer
    buffer = -0.1 * min((bbox[2] - bbox[0]) / size[0], (bbox[3] - bbox[1]) / size[1])

    draw = ImageDraw.Draw(mask)

    def draw_polygon(p):
        draw.polygon([transf(coord) for coord in p.exterior.coords], fill=0)
        for ring in p.interiors:
            draw.polygon([transf(coord) for coord in ring.coords], fill=255)

    for p in polygons:
        # little bit smaller polygon does not include touched pixels outside coverage
        buffered = p.buffer(buffer, resolution=1, join_style=2)

        if buffered.is_empty: # can be empty after negative buffer
            continue

        if buffered.type == 'MultiPolygon':
            # negative buffer can turn polygon into multipolygon
            for p in buffered:
                draw_polygon(p)
        else:
            draw_polygon(buffered)

    return mask
