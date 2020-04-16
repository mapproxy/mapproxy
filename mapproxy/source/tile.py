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
from mapproxy.source import SourceError
from mapproxy.client.http import HTTPClientError
from mapproxy.source import InvalidSourceQuery
from mapproxy.layer import BlankImage, map_extent_from_grid, CacheMapLayer, MapLayer
from mapproxy.util.py import reraise_exception

import logging
log = logging.getLogger('mapproxy.source.tile')
log_config = logging.getLogger('mapproxy.config')

class TiledSource(MapLayer):
    def __init__(self, grid, client, coverage=None, image_opts=None, error_handler=None,
        res_range=None):
        MapLayer.__init__(self, image_opts=image_opts)
        self.grid = grid
        self.client = client
        self.image_opts = image_opts or ImageOptions()
        self.coverage = coverage
        self.extent = coverage.extent if coverage else map_extent_from_grid(grid)
        self.res_range = res_range
        self.error_handler = error_handler

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

        if self.res_range and not self.res_range.contains(query.bbox, query.size,
                                                          query.srs):
            raise BlankImage()
        if self.coverage and not self.coverage.intersects(query.bbox, query.srs):
            raise BlankImage()

        _bbox, grid, tiles = self.grid.get_affected_tiles(query.bbox, query.size)

        if grid != (1, 1):
            raise InvalidSourceQuery('BBOX does not align to tile')

        tile_coord = next(tiles)

        try:
            return self.client.get_tile(tile_coord, format=query.format)
        except HTTPClientError as e:
            if self.error_handler:
                resp = self.error_handler.handle(e.response_code, query)
                if resp:
                    return resp
            log.warning('could not retrieve tile: %s', e)
            reraise_exception(SourceError(e.args[0]), sys.exc_info())

class CacheSource(CacheMapLayer):
    def __init__(self, tile_manager, extent=None, image_opts=None,
        max_tile_limit=None, tiled_only=False):
        CacheMapLayer.__init__(self, tile_manager, extent=extent, image_opts=image_opts,
            max_tile_limit=max_tile_limit)
        self.supports_meta_tiles = not tiled_only
        self.tiled_only = tiled_only

    def get_map(self, query):
        if self.tiled_only:
            query.tiled_only = True
        return CacheMapLayer.get_map(self, query)

