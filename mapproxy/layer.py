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

from mapproxy.core.config import base_config
from mapproxy.core.cache import (
    map_extend_from_grid,
    TileCacheError,
    BlankImage,
    TooManyTilesError,
)
from mapproxy.core.grid import NoTiles
from mapproxy.core.image import TiledImage

class MapLayer(object):
    def get_map(self, query):
        raise NotImplementedError

class InfoLayer(object):
    def get_info(self, query):
        raise NotImplementedError

class ResolutionConditional(MapLayer):
    def __init__(self, one, two, resolution, srs, extend):
        self.one = one
        self.two = two
        self.resolution = resolution
        self.srs = srs
        
        #TODO
        self.transparent = self.one.transparent
        self.extend = extend
    
    def get_map(self, query):
        bbox = query.bbox
        if query.srs != self.srs:
            bbox = query.srs.transform_bbox_to(self.srs, bbox)
        
        xres = (bbox[2] - bbox[0]) / query.size[0]
        yres = (bbox[3] - bbox[1]) / query.size[1]
        res = min(xres, yres)
        print res, self.resolution
        
        if res > self.resolution:
            return self.one.get_map(query)
        else:
            return self.two.get_map(query)

class SRSConditional(MapLayer):
    PROJECTED = 'PROJECTED'
    GEOGRAPHIC = 'GEOGRAPHIC'
    
    def __init__(self, layers, extend, transparent=False):
        self.transparent = transparent
        # TODO geographic/projected fallback
        self.srs_map = {}
        for layer, srss in layers:
            for srs in srss:
                self.srs_map[srs] = layer
        
        self.extend = extend
    
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
    def __init__(self, source, extend):
        self.source = source
        self.extend = extend
    
    def get_map(self, query):
        return self.source.get_map(query)

class CacheMapLayer(MapLayer):
    def __init__(self, tile_manager, resampling=None):
        self.tile_manager = tile_manager
        self.grid = tile_manager.grid
        self.resampling = resampling or base_config().image.resampling_method
        self.extend = map_extend_from_grid(self.grid)
        self.transparent = tile_manager.transparent
    
    def get_map(self, query):
        tiled_image = self._tiled_image(query.bbox, query.size, query.srs)
        return tiled_image.transform(query.bbox, query.srs, query.size, 
            self.resampling)
    
    def _tiled_image(self, bbox, size, srs):
        try:
            src_bbox, tile_grid, affected_tile_coords = \
                self.grid.get_affected_tiles(bbox, size, req_srs=srs)
        except IndexError:
            raise TileCacheError('Invalid BBOX')
        except NoTiles:
            raise BlankImage()
        
        num_tiles = tile_grid[0] * tile_grid[1]
        if num_tiles >= base_config().cache.max_tile_limit:
            raise TooManyTilesError()
        
        tile_sources = [tile.source for tile in self.tile_manager.load_tile_coords(affected_tile_coords)]
        return TiledImage(tile_sources, src_bbox=src_bbox, src_srs=self.grid.srs,
                          tile_grid=tile_grid, tile_size=self.grid.tile_size,
                          transparent=self.transparent)
    

class DirectInfoLayer(InfoLayer):
    def __init__(self, source):
        self.source = source
    
    def get_info(self, query):
        return self.source.get_info(query)

