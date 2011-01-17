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
from mapproxy.source import Source, SourceError
from mapproxy.client.http import HTTPClientError
from mapproxy.source import InvalidSourceQuery
from mapproxy.layer import BlankImage, map_extent_from_grid
from mapproxy.util import reraise_exception

class TiledSource(Source):
    def __init__(self, grid, client, inverse=False, coverage=None, opacity=None,
                 transparent=False):
        self.grid = grid
        self.client = client
        self.inverse = inverse
        self.transparent = True if opacity else transparent
        self.opacity = opacity
        self.coverage = coverage
        self.extent = coverage.extent if coverage else map_extent_from_grid(grid)
    
    def get_map(self, query):
        if self.grid.tile_size != query.size:
            raise InvalidSourceQuery()
        if self.grid.srs != query.srs:
            raise InvalidSourceQuery()
        if self.coverage and not self.coverage.intersects(query.bbox, query.srs):
            raise BlankImage()
        
        _bbox, grid, tiles = self.grid.get_affected_tiles(query.bbox, query.size)
        
        if grid != (1, 1):
            raise InvalidSourceQuery('bbox does not align to tile')

        tile_coord = tiles.next()
        
        if self.inverse:
            tile_coord = self.grid.flip_tile_coord(tile_coord)
        try:
            return self.client.get_tile(tile_coord, format=query.format)
        except HTTPClientError, e:
            reraise_exception(SourceError(e.args[0]), sys.exc_info())