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
from mapproxy.core.cache import TileSource, TileSourceError
from mapproxy.core.client import TMSClient, HTTPClientError

class TMSTileSource(TileSource):
    """
    This `TileSource` retrieves new tiles from a TMS server.
    """
    def __init__(self, grid, url='', format='png', inverse=False):
        TileSource.__init__(self)
        self.grid = grid
        self.tms_client = TMSClient(url, format) 
        self.inverse = inverse
    
    def id(self):
        return self.tms_client.url
    
    def create_tile(self, tile, _tile_map):
        """Retrieve the requested `tile`."""
        if self.inverse:
            coord = self.grid.flip_tile_coord(tile.coord)
        else:
            coord = tile.coord
        try:
            buf = StringIO(self.tms_client.get_tile(coord).read())
            tile.source = ImageSource(buf)
        except HTTPClientError, e:
            reraise_exception(TileSourceError(e.message), sys.exc_info())
        return [tile]
    
    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.tms_client)
