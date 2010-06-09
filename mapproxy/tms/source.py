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
Retrieve tiles from different tile servers (TMS/TileCache/etc.).
"""

import sys
from mapproxy.core.source import Source
from mapproxy.core.client import HTTPClientError
from mapproxy.core.cache import TileSourceError, InvalidSourceQuery
from mapproxy.core.utils import reraise_exception

class TiledSource(Source):
    def __init__(self, grid, client, inverse=False):
        self.grid = grid
        self.client = client
        self.inverse = inverse
    
    def get_map(self, query):
        if self.grid.tile_size != query.size:
            raise InvalidSourceQuery()
        if self.grid.srs != query.srs:
            raise InvalidSourceQuery()
        
        _bbox, grid, tiles = self.grid.get_affected_tiles(query.bbox, query.size)
        
        if grid != (1, 1):
            raise InvalidSourceQuery('bbox does not align to tile')

        tile_coord = tiles.next()
        
        if self.inverse:
            tile_coord = self.grid.flip_tile_coord(tile_coord)
        try:
            return self.client.get_tile(tile_coord)
        except HTTPClientError, e:
            reraise_exception(TileSourceError(e.args[0]), sys.exc_info())