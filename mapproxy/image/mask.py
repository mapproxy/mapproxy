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

from mapproxy.platform.image import Image, ImageDraw, ImageChops
from mapproxy.srs import SRS, make_lin_transf
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions, create_image
from mapproxy.util.geom import transform_geometry, bbox_polygon, load_polygons

from shapely import wkt

def mask_image_source(img_source, bbox, bbox_srs, geom, geom_srs):
    img = img_source.as_image()
    
    img = mask_image(img, bbox, bbox_srs, geom, geom_srs)
    result = create_image(img.size, img_source.image_opts)
    
    result.paste(img, (0, 0), img)
    return ImageSource(result, image_opts=img_source.image_opts)

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

if __name__ == '__main__':
    
    img_opts = ImageOptions(transparent=False, bgcolor=(255, 255, 200))
    
    img = ImageSource(Image.open('./examples/map.png'), image_opts=img_opts)
    
    # img = Image.open('./examples/map_alpha.png')
    
    img_bg = mask_image_source(img, [629789.4377791,6675910.0948916,1411893.1110529,7284960.3361588], SRS(3857),
        load_polygons('/Users/olt/dev/world_boundaries/polygons/GM.txt')[1], SRS(3857))
    # ri = RestricedImage(img, img_opts, [5.65749477734,51.3077351406,12.683251612,54.6017808717], SRS(4326))
    # mask = ri.mask(bbox_polygon([5.65749477734, 51.3077351406, 12.683251612, 54.6017808717]), SRS(4326))
    
    # p1 = Polygon([(50, 50), (50, 800), (700, 650), (900, 100)], [[(200, 200), (400, 600), (400, 400)]])
    # p2 = Polygon([(700, 700), (700, 900), (900, 900), (900, 700)], [[(710, 710), (710, 730), (730, 730), (730, 710)]])
    # 
    # geom = MultiPolygon([p1, p2])
    
    # mask = ImageChops.invert(mask)
    # mask.show()
    # img = img.convert('RGBA')
    # if img.mode == 'RGBA': # TODO png8a
    #     img.split()[3].show()
    #     mask = ImageChops.multiply(mask, img.split()[3])
    # mask.show()

    # img.putalpha(maks.split()[3])
    
    # img_bg.paste(img, (0, 0), mask)
    # img_bg = img_bg.quantize(256, Image.FASTOCTREE)
    img_bg.save("/tmp/out.jpeg")
    
    # import os
    # os.system("open /tmp/out.png")
    