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

from mapproxy.tms import TileServiceGrid
from mapproxy.core.exceptions import RequestError
from mapproxy.core.cache import TileCacheError
from mapproxy.core.layer import Layer, LayerMetaData
from mapproxy.core.request import split_mime_type

import logging
log = logging.getLogger(__name__)

class TileServiceLayer(Layer):
    def __init__(self, md, cache):
        """
        :param md: the layer metadata
        :param cache: the layer cache
        """
        Layer.__init__(self)
        self.md = LayerMetaData(md)
        self.cache = cache
        self.grid = TileServiceGrid(cache.grid)
    
    def _bbox(self):
        return self.grid.bbox()
    
    def _srs(self):
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
            return TileResponse(self.cache.tile(tile_coord))
        except TileCacheError, e:
            log.error(e)
            raise RequestError(e.message, request=tile_request, internal=True)

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