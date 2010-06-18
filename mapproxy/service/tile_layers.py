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

from mapproxy.core.exceptions import RequestError
from mapproxy.core.cache import TileCacheError
from mapproxy.core.request import split_mime_type
from mapproxy.core.srs import SRS
from mapproxy.core.grid import RES_TYPE_GLOBAL, RES_TYPE_SQRT2

import logging
log = logging.getLogger(__name__)

class TileLayer(object):
    def __init__(self, md, tile_manager):
        """
        :param md: the layer metadata
        :param tile_manager: the layer tile manager
        """
        self.md = md
        self.tile_manager = tile_manager
        self.grid = TileServiceGrid(tile_manager.grid)
    
    @property
    def bbox(self):
        return self.grid.bbox

    @property
    def srs(self):
        return self.grid.srs
    
    @property
    def format(self):
        _mime_class, format, _options = split_mime_type(self.format_mime_type)
        return format
    
    @property
    def format_mime_type(self):
        return self.md.get('format', 'image/png')
    
    def _internal_tile_coord(self, tile_request, use_profiles=False):
        tile_coord = self.grid.internal_tile_coord(tile_request.tile, use_profiles)
        if tile_coord is None:
            raise RequestError('The requested tile is outside the bounding box'
                               ' of the tile map.', request=tile_request)
        return tile_coord
    
    def render(self, tile_request, use_profiles=False):
        if tile_request.format != self.format:
            raise RequestError('invalid format (%s). this tile set only supports (%s)'
                               % (tile_request.format, self.format), request=tile_request)
        tile_coord = self._internal_tile_coord(tile_request, use_profiles=use_profiles)
        try:
            return TileResponse(self.tile_manager.load_tile_coord(tile_coord, with_metadata=True))
        except TileCacheError, e:
            log.error(e)
            raise RequestError(e.args[0], request=tile_request, internal=True)

class TileResponse(object):
    def __init__(self, tile):
        self.tile = tile
    
    def as_buffer(self):
        return self.tile.source_buffer()
    
    @property
    def timestamp(self):
        return self.tile.timestamp
    
    @property
    def size(self):
        return self.tile.size

class TileServiceGrid(object):
    """
    Wraps a `TileGrid` and adds some ``TileService`` specific methods.
    """
    def __init__(self, grid):
        self.grid = grid
        if self.grid.res_type in (RES_TYPE_GLOBAL, RES_TYPE_SQRT2):
            if self.grid.srs == SRS(900913):
                self.profile = 'global-mercator'
                self.srs_name = 'OSGEO:41001' # as required by TMS 1.0.0
                self._skip_first_level = True
            elif self.grid.srs == SRS(4326):
                self.profile = 'global-geodetic'
                self.srs_name = 'EPSG:4326'
                self._skip_first_level = True
        else:
            self.profile = 'local'
            self.srs_name = self.grid.srs.srs_code
            self._skip_first_level = False
        
        self._skip_odd_level = False
        if self.grid.res_type == RES_TYPE_SQRT2:
            self._skip_odd_level = True
    
    def internal_level(self, level):
        """
        :return: the internal level
        """
        if self._skip_first_level:
            level += 1
            if self._skip_odd_level:
                level += 1
        if self._skip_odd_level:
            level *= 2
        return level
    
    @property
    def bbox(self):
        """
        :return: the bbox of all tiles of the first level
        """
        first_level = self.internal_level(0)
        grid_size = self.grid.grid_sizes[first_level]
        return self.grid._get_bbox([(0, 0, first_level), 
                                    (grid_size[0]-1, grid_size[1]-1, first_level)])
    
    def __getattr__(self, key):
        return getattr(self.grid, key)
    
    @property
    def tile_sets(self):
        """
        Get all public tile sets for this layer.
        :return: the order and resolution of each tile set 
        """
        tile_sets = []
        num_levels = self.grid.levels
        start = 0
        step = 1
        if self._skip_first_level:
            if self._skip_odd_level:
                start = 2
            else:
                start = 1
        if self._skip_odd_level:
            step = 2
        for order, level in enumerate(range(start, num_levels, step)):
            tile_sets.append((order, self.grid.resolutions[level]))
        return tile_sets
    
    def internal_tile_coord(self, tile_coord, use_profiles):
        """
        Converts public tile coords to internal tile coords.
        
        :param tile_coord: the public tile coord
        :param use_profiles: True if the tile service supports global 
                             profiles (see `mapproxy.core.server.TileServer`)
        """
        x, y, z = tile_coord
        if z < 0:
            return None
        if use_profiles and self._skip_first_level:
            z += 1
        if self._skip_odd_level:
            z *= 2
        return self.grid.limit_tile((x, y, z))
    
