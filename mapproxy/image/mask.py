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

from mapproxy.platform.image import Image, ImageDraw
from mapproxy.srs import SRS, make_lin_transf
from mapproxy.image import ImageSource
from mapproxy.image.opts import create_image

def mask_image_source_from_coverage(img_source, bbox, bbox_srs, coverage):
    img = img_source.as_image()
    img = mask_image(img, bbox, bbox_srs, coverage)
    result = create_image(img.size, img_source.image_opts)
    result.paste(img, (0, 0), img)
    return ImageSource(result, image_opts=img_source.image_opts)

def mask_image(img, bbox, bbox_srs, coverage):
    geom = mask_polygons(bbox, SRS(bbox_srs), coverage)
    mask = image_mask_from_geom(img, bbox, geom)
    img = img.convert('RGBA')
    img.paste((255, 255, 255, 0), (0, 0), mask)
    return img

def mask_polygons(bbox, bbox_srs, coverage):
    coverage = coverage.transform_to(bbox_srs)
    coverage = coverage.intersection(bbox, bbox_srs)
    geom = coverage.geom
    if geom.type == 'Polygon':
        geom = [geom]
    return geom

def image_mask_from_geom(img, bbox, polygons):
    transf = make_lin_transf(bbox, (0, 0) + img.size)
    
    mask = Image.new('L', img.size, 255)
    draw = ImageDraw.Draw(mask)
    
    for p in polygons:
        draw.polygon([transf(coord) for coord in p.exterior.coords], fill=0)
        for ring in p.interiors:
            draw.polygon([transf(coord) for coord in ring.coords], fill=255)
    
    return mask
    