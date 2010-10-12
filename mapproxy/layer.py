# -:- encoding: utf-8 -:-
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

"""
Layers that can get maps/infos from different sources/caches. 
"""

from __future__ import division
from mapproxy.config import base_config
from mapproxy.grid import NoTiles, GridError
from mapproxy.image.tile import TiledImage
from mapproxy.srs import SRS, bbox_equals

import logging
log = logging.getLogger(__name__)

class BlankImage(Exception):
    pass

class MapError(Exception):
    pass

class MapBBOXError(Exception):
    pass

class MapLayer(object):
    def get_map(self, query):
        raise NotImplementedError

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


class ResolutionConditional(MapLayer):
    def __init__(self, one, two, resolution, srs, extent):
        self.one = one
        self.two = two
        self.resolution = resolution
        self.srs = srs
        
        #TODO
        self.transparent = self.one.transparent
        self.extent = extent
    
    def get_map(self, query):
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
    
    def __init__(self, layers, extent, transparent=False):
        self.transparent = transparent
        # TODO geographic/projected fallback
        self.srs_map = {}
        for layer, srss in layers:
            for srs in srss:
                self.srs_map[srs] = layer
        
        self.extent = extent
    
    def get_map(self, query):
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
        self.source = source
        self.extent = extent
    
    def get_map(self, query):
        return self.source.get_map(query)

class CacheMapLayer(MapLayer):
    def __init__(self, tile_manager, resampling=None):
        self.tile_manager = tile_manager
        self.grid = tile_manager.grid
        self.resampling = resampling or base_config().image.resampling_method
        self.extent = map_extent_from_grid(self.grid)
        self.transparent = tile_manager.transparent
    
    def get_map(self, query):
        if query.tiled_only:
            self._check_tiled(query)
        
        tiled_image = self._tiled_image(query.bbox, query.size, query.srs,
                                        query.tiled_only)
        result = tiled_image.transform(query.bbox, query.srs, query.size, 
                                       self.resampling)
        return result

    def _check_tiled(self, query):
        if query.format != self.tile_manager.format:
            raise MapError("invalid tile format, use %s" % self.tile_manager.format)
        if query.size != self.grid.tile_size:
            raise MapError("invalid tile size (use %dx%d)" % self.grid.tile_size)
    
    
    def _tiled_image(self, bbox, size, srs, tiled_only):
        try:
            src_bbox, tile_grid, affected_tile_coords = \
                self.grid.get_affected_tiles(bbox, size, req_srs=srs)
        except NoTiles:
            raise BlankImage()
        except GridError, ex:
            raise MapBBOXError(ex.args[0])
        
        num_tiles = tile_grid[0] * tile_grid[1]
        if num_tiles >= base_config().cache.max_tile_limit:
            raise MapBBOXError("to many tiles")
        
        if tiled_only:
            if num_tiles > 1: 
                raise MapBBOXError("not a single tile")
            if not bbox_equals(bbox, src_bbox, (bbox[2]-bbox[0]/size[0]/10),
                                               (bbox[3]-bbox[1]/size[1]/10)):
                raise MapBBOXError("query does not align to tile boundaries")
        
        tile_sources = [tile.source for tile in self.tile_manager.load_tile_coords(affected_tile_coords)]
        return TiledImage(tile_sources, src_bbox=src_bbox, src_srs=self.grid.srs,
                          tile_grid=tile_grid, tile_size=self.grid.tile_size,
                          transparent=self.transparent)
    

class DirectInfoLayer(InfoLayer):
    def __init__(self, source):
        self.source = source
    
    def get_info(self, query):
        return self.source.get_info(query)

