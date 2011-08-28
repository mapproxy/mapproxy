# -:- encoding: utf-8 -:-
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

"""
Layers that can get maps/infos from different sources/caches. 
"""

from __future__ import division, with_statement
from mapproxy.grid import NoTiles, GridError, merge_resolution_range
from mapproxy.image.opts import ImageOptions
from mapproxy.image.tile import TiledImage
from mapproxy.srs import SRS, bbox_equals, merge_bbox

import logging
log = logging.getLogger(__name__)

class BlankImage(Exception):
    pass

class MapError(Exception):
    pass

class MapBBOXError(Exception):
    pass

class MapLayer(object):
    res_range = None
    
    def __init__(self, image_opts=None):
        self.image_opts = image_opts or ImageOptions()
    
    def _get_transparent(self):
        return self.image_opts.transparent
    
    def _set_transparent(self, value):
        self.image_opts.transparent = value
    
    transparent = property(_get_transparent, _set_transparent)
    
    def _get_opacity(self):
        return self.image_opts.opacity
    
    def _set_opacity(self, value):
        self.image_opts.opacity = value
    
    opacity = property(_get_opacity, _set_opacity)
    
    def is_opaque(self):
        if self.opacity is None:
            return not self.transparent
        return self.opacity >= 0.99
    
    def check_res_range(self, query):
        if (self.res_range and
          not self.res_range.contains(query.bbox, query.size, query.srs)):
            raise BlankImage()
    
    def get_map(self, query):
        raise NotImplementedError
    
    def combined_layer(self, other, query):
        return None

class InfoLayer(object):
    def get_info(self, query):
        raise NotImplementedError


class MapQuery(object):
    """
    Internal query for a map with a specific extent, size, srs, etc.
    """
    def __init__(self, bbox, size, srs, format='image/png', transparent=False,
                 tiled_only=False):
        self.bbox = bbox
        self.size = size
        self.srs = srs
        self.format = format
        self.transparent = transparent
        self.tiled_only = tiled_only


class InfoQuery(object):
    def __init__(self, bbox, size, srs, pos, info_format, format=None):
        self.bbox = bbox
        self.size = size
        self.srs = srs
        self.pos = pos
        self.info_format = info_format
        self.format = format

class LegendQuery(object):
    def __init__(self, format, scale):
        self.format = format
        self.scale = scale

def map_extent_from_grid(grid):
    """
    >>> from mapproxy.grid import tile_grid_for_epsg
    >>> map_extent_from_grid(tile_grid_for_epsg('EPSG:900913')) 
    ... #doctest: +NORMALIZE_WHITESPACE
    MapExtent((-20037508.342789244, -20037508.342789244,
               20037508.342789244, 20037508.342789244), SRS('EPSG:900913'))
    """
    return MapExtent(grid.bbox, grid.srs)

class MapExtent(object):
    """
    >>> me = MapExtent((5, 45, 15, 55), SRS(4326))
    >>> me.llbbox
    (5, 45, 15, 55)
    >>> map(int, me.bbox_for(SRS(900913)))
    [556597, 5621521, 1669792, 7361866]
    >>> map(int, me.bbox_for(SRS(4326)))
    [5, 45, 15, 55]
    """
    is_default = False
    def __init__(self, bbox, srs):
        self.llbbox = srs.transform_bbox_to(SRS(4326), bbox)
        self.bbox = bbox
        self.srs = srs
    
    def bbox_for(self, srs):
        if srs == self.srs:
            return self.bbox
        
        return self.srs.transform_bbox_to(srs, self.bbox)
    
    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.bbox, self.srs)
    
    
    def __add__(self, other):
        if not isinstance(other, MapExtent):
            raise NotImplemented
        if other.is_default:
            return self
        return MapExtent(merge_bbox(self.llbbox, other.llbbox), SRS(4326))

class DefaultMapExtent(MapExtent):
    """
    Default extent that covers the whole world.
    Will not affect other extents when added.
    
    >>> m1 = MapExtent((0, 0, 10, 10), SRS(4326))
    >>> m2 = MapExtent((10, 0, 20, 10), SRS(4326))
    >>> m3 = DefaultMapExtent()
    >>> (m1 + m2).bbox
    (0, 0, 20, 10)
    >>> (m1 + m3).bbox
    (0, 0, 10, 10)
    """
    is_default = True
    def __init__(self):
        MapExtent.__init__(self, (-180, -90, 180, 90), SRS(4326))

def merge_layer_extents(layers):
    if not layers:
        return DefaultMapExtent()
    layers = layers[:]
    extent = layers.pop().extent
    for layer in layers:
        extent = extent + layer.extent
    return extent

class ResolutionConditional(MapLayer):
    def __init__(self, one, two, resolution, srs, extent, opacity=None):
        MapLayer.__init__(self)
        self.one = one
        self.two = two
        self.res_range = merge_layer_res_ranges([one, two])
        self.resolution = resolution
        self.srs = srs
        
        #TODO
        self.transparent = self.one.transparent
        self.opacity = opacity
        self.extent = extent
    
    def get_map(self, query):
        self.check_res_range(query)
        bbox = query.bbox
        if query.srs != self.srs:
            bbox = query.srs.transform_bbox_to(self.srs, bbox)
        
        xres = (bbox[2] - bbox[0]) / query.size[0]
        yres = (bbox[3] - bbox[1]) / query.size[1]
        res = min(xres, yres)
        log.debug('actual res: %s, threshold res: %s', res, self.resolution)
        
        if res > self.resolution:
            return self.one.get_map(query)
        else:
            return self.two.get_map(query)

class SRSConditional(MapLayer):
    PROJECTED = 'PROJECTED'
    GEOGRAPHIC = 'GEOGRAPHIC'
    
    def __init__(self, layers, extent, transparent=False, opacity=None):
        MapLayer.__init__(self)
        self.transparent = transparent
        # TODO geographic/projected fallback
        self.srs_map = {}
        self.res_range = merge_layer_res_ranges([l[0] for l in layers])
        for layer, srss in layers:
            for srs in srss:
                self.srs_map[srs] = layer
        
        self.extent = extent
        self.opacity = opacity
    
    def get_map(self, query):
        self.check_res_range(query)
        layer = self._select_layer(query.srs)
        return layer.get_map(query)
    
    def _select_layer(self, query_srs):
        # srs exists
        if query_srs in self.srs_map:
            return self.srs_map[query_srs]
        
        # srs_type exists
        srs_type = self.GEOGRAPHIC if query_srs.is_latlong else self.PROJECTED
        if srs_type in self.srs_map:
            return self.srs_map[srs_type]
        
        # first with same type
        is_latlong = query_srs.is_latlong
        for srs in self.srs_map:
            if hasattr(srs, 'is_latlong') and srs.is_latlong == is_latlong:
                return self.srs_map[srs]
        
        # return first
        return self.srs_map.itervalues().next()
        

class DirectMapLayer(MapLayer):
    def __init__(self, source, extent):
        MapLayer.__init__(self)
        self.source = source
        self.res_range = getattr(source, 'res_range', None)
        self.extent = extent
    
    def get_map(self, query):
        self.check_res_range(query)
        return self.source.get_map(query)


def merge_layer_res_ranges(layers):
    ranges = [s.res_range for s in layers
              if hasattr(s, 'res_range')]
    if ranges:
        ranges = reduce(merge_resolution_range, ranges)

    return ranges


class CacheMapLayer(MapLayer):
    def __init__(self, tile_manager, extent=None, image_opts=None,
        max_tile_limit=None):
        MapLayer.__init__(self, image_opts=image_opts)
        self.tile_manager = tile_manager
        self.grid = tile_manager.grid
        self.extent = extent or map_extent_from_grid(self.grid)
        self.res_range = merge_layer_res_ranges(self.tile_manager.sources)
        self.transparent = tile_manager.transparent
        self.max_tile_limit = max_tile_limit
    
    def get_map(self, query):
        self.check_res_range(query)
        
        if query.tiled_only:
            self._check_tiled(query)
        
        result = self._image(query)
        return result

    def _check_tiled(self, query):
        if query.format != self.tile_manager.format:
            raise MapError("invalid tile format, use %s" % self.tile_manager.format)
        if query.size != self.grid.tile_size:
            raise MapError("invalid tile size (use %dx%d)" % self.grid.tile_size)
    
    def _image(self, query):
        try:
            src_bbox, tile_grid, affected_tile_coords = \
                self.grid.get_affected_tiles(query.bbox, query.size,
                                             req_srs=query.srs)
        except NoTiles:
            raise BlankImage()
        except GridError, ex:
            raise MapBBOXError(ex.args[0])
        
        num_tiles = tile_grid[0] * tile_grid[1]
        
        if self.max_tile_limit and num_tiles >= self.max_tile_limit:
            raise MapBBOXError("to many tiles")
        
        if query.tiled_only:
            if num_tiles > 1: 
                raise MapBBOXError("not a single tile")
            bbox = query.bbox
            if not bbox_equals(bbox, src_bbox, (bbox[2]-bbox[0]/query.size[0]/10),
                                               (bbox[3]-bbox[1]/query.size[1]/10)):
                raise MapBBOXError("query does not align to tile boundaries")
        
        with self.tile_manager.session():
            tile_collection = self.tile_manager.load_tile_coords(affected_tile_coords)
        
        if tile_collection.empty:
            raise BlankImage()
        
        if query.tiled_only:
            tile = tile_collection[0].source
            tile.image_opts = self.tile_manager.image_opts
            return tile
        
        tile_sources = [tile.source for tile in tile_collection]
        tiled_image = TiledImage(tile_sources, src_bbox=src_bbox, src_srs=self.grid.srs,
                          tile_grid=tile_grid, tile_size=self.grid.tile_size)
        return tiled_image.transform(query.bbox, query.srs, query.size, 
                                       self.tile_manager.image_opts)

class DirectInfoLayer(InfoLayer):
    def __init__(self, source):
        self.source = source
    
    def get_info(self, query):
        return self.source.get_info(query)

