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
Tile caching (creation, caching and retrieval of tiles).
"""

from __future__ import with_statement
import sys
from cStringIO import StringIO

from mapproxy.core.grid import MetaGrid
from mapproxy.core.client import HTTPClientError
from mapproxy.wms.request import WMSMapRequest
from mapproxy.core.utils import reraise_exception
from mapproxy.core.image import TileSplitter, ImageSource, merge_images

from mapproxy.core.cache import _Tile, TileSource, TileSourceError

import logging
log = logging.getLogger(__name__)


class WMSTileSource(TileSource):
    """
    This `TileSource` retrieves new tiles from a WMS server.
    
    This class is able to request maps that are larger than one tile and
    split the large map into multiple tiles. The ``meta_size``
    defines how many tiles should be generated per request.
    """
    def __init__(self, grid, clients, format=None,
                 meta_buffer=0, meta_size=(2, 2)):
        """
        :param grid: the associated grid
        :param clients: WMSClient for each distinct WMS source
        :type clients: [`mapproxy.wms.client.WMSClient`,...]
        :param format: internal image format, if not set use format from first WMS client
        :param meta_size: the number of tiles to get per request
        :type meta_size: ``(x_size, y_size)``
        :param meta_buffer: the buffer size in pixel that is added to each grid.
            the number is added to all four borders.
            this buffer may improve the handling of labels overlapping (meta)tile borders.
        :type meta_buffer: pixel
        """
        TileSource.__init__(self)
        self.grid = grid
        self.clients = clients
        if format is None:
            format = clients[0].request_template.params.format
        self.format = format
        self.transparent = self._has_transparent_sources()
        self.meta_grid = MetaGrid(grid=self.grid, meta_size=meta_size,
                                  meta_buffer=meta_buffer)
    
    def _has_transparent_sources(self):
        for client in self.clients:
            if (client.request_template.params.get('transparent', 'false').lower()
                == 'true'):
                return True
        return False
    
    def id(self):
        return '|'.join(client.request_template.complete_url for client in self.clients)
    
    def lock_filename(self, tile):
        """
        Returns a lock for one fixed tile per metatile.
        """
        tiles = self.meta_grid.tiles(tile.coord)
        first_tile, _ = tiles.next()
        return TileSource.lock_filename(self, _Tile(first_tile))
    
    def create_tile(self, tile, tile_map):
        """
        Retrieve the metatile that contains the requested `tile` and save
        all tiles.
        """
        meta_tile = self._get_meta_tile(tile)
        tiles = self.meta_grid.tiles(tile.coord)
        return self._split_meta_tile(meta_tile, tiles, tile_map=tile_map)
    
    def _get_meta_tile(self, tile):
        bbox = self.meta_grid.meta_bbox(tile.coord)
        size = self.meta_grid.tile_size(tile.coord[2])
        responses = []
        for client in self.clients:
            request = WMSMapRequest()
            request.params.bbox = bbox
            request.params.size = size
            try:
                resp = client.get_map(request).as_buffer()
            except HTTPClientError, e:
                reraise_exception(TileSourceError(e.message), sys.exc_info())
            responses.append(ImageSource(StringIO(resp.read()), size=size))
        if len(responses) > 1:
            return merge_images(responses, transparent=True)
        else:
            return responses[0]
    
    def _split_meta_tile(self, meta_tile, tiles, tile_map):
        try:
            format = self.format
            if not self.transparent and format == 'png':
                format = 'png8'
            splitter = TileSplitter(meta_tile, format)
        except IOError, e:
            reraise_exception(TileSourceError('could not read WMS response: %s' % 
                                              e.message), sys.exc_info())
        split_tiles = []
        for tile in tiles:
            tile_coord, crop_coord = tile
            data = splitter.get_tile(crop_coord, self.grid.tile_size)
            new_tile = tile_map(tile_coord)
            new_tile.source = data
            split_tiles.append(new_tile)
        return split_tiles
    
    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.clients)
