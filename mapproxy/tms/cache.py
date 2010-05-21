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

import sys
from cStringIO import StringIO

from mapproxy.core.utils import reraise_exception
from mapproxy.core.image import ImageSource
from mapproxy.core import cache, client


class TileSource(cache.TileSource):
    """
    This `TileSource` retrieves new tiles from a tile server.
    """
    def __init__(self, grid, tile_client, inverse=False):
        cache.TileSource.__init__(self)
        self.grid = grid
        self.tile_client = tile_client 
        self.inverse = inverse
    
    def id(self):
        return self.tile_client.url
    
    def create_tile(self, tile, _tile_map):
        """Retrieve the requested `tile`."""
        if self.inverse:
            coord = self.grid.flip_tile_coord(tile.coord)
        else:
            coord = tile.coord
        try:
            buf = StringIO(self.tile_client.get_tile(coord).read())
            tile.source = ImageSource(buf)
        except client.HTTPClientError, e:
            reraise_exception(cache.TileSourceError(e.args[0]), sys.exc_info())
        return [tile]
    
    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.tms_client)

# TODO remove in 0.9
TMSTileSource = TileSource