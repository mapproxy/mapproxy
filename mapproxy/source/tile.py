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
Retrieve tiles from different tile servers (TMS/TileCache/etc.).
"""

import sys
from mapproxy.image.opts import ImageOptions
from mapproxy.source import Source, SourceError
from mapproxy.client.http import HTTPClientError
from mapproxy.source import InvalidSourceQuery
from mapproxy.layer import BlankImage, map_extent_from_grid
from mapproxy.util import reraise_exception

import logging
log = logging.getLogger('mapproxy.source.tile')
log_config = logging.getLogger('mapproxy.config')
class TiledSource(Source):
    def __init__(self, grid, client, inverse=False, coverage=None, image_opts=None):
        Source.__init__(self, image_opts=image_opts)
        self.grid = grid
        self.client = client
        self.inverse = inverse
        self.image_opts = image_opts or ImageOptions()
        self.coverage = coverage
        self.extent = coverage.extent if coverage else map_extent_from_grid(grid)
    
    def get_map(self, query):
        if self.grid.tile_size != query.size:
            ex = InvalidSourceQuery(
                'tile size of cache and tile source do not match: %s != %s'
                 % (self.grid.tile_size, query.size)
            )
            log_config.error(ex)
            raise ex
            
        if self.grid.srs != query.srs:
            ex = InvalidSourceQuery(
                'SRS of cache and tile source do not match: %r != %r'
                % (self.grid.srs, query.srs)
            )
            log_config.error(ex)
            raise ex

        if self.coverage and not self.coverage.intersects(query.bbox, query.srs):
            raise BlankImage()
        
        _bbox, grid, tiles = self.grid.get_affected_tiles(query.bbox, query.size)
        
        if grid != (1, 1):
            raise InvalidSourceQuery('BBOX does not align to tile')

        tile_coord = tiles.next()
        
        if self.inverse:
            tile_coord = self.grid.flip_tile_coord(tile_coord)
        try:
            return self.client.get_tile(tile_coord, format=query.format)
        except HTTPClientError, e:
            log.warn('could not retrieve tile: %s', e)
            reraise_exception(SourceError(e.args[0]), sys.exc_info())