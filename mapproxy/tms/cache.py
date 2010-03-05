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
