from jinja2 import Environment, PackageLoader

from mapproxy.core.response import Response
from mapproxy.core.exceptions import RequestError
from mapproxy.core.server import Server
from mapproxy.core.srs import SRS
from mapproxy.core.grid import RES_TYPE_GLOBAL, RES_TYPE_SQRT2
from mapproxy.tms.request import tile_request
from mapproxy.core.config import base_config
from mapproxy.core.app import ctx

env = Environment(loader=PackageLoader('mapproxy.tms', 'templates'),
                  trim_blocks=True)

import logging
log = logging.getLogger(__name__)

class TileLayers(dict):
    def __getitem__(self, key):
        if key in self:
            return dict.__getitem__(self, key)
        if key + '_EPSG900913' in self:
            return self[key + '_EPSG900913']
        if key + '_EPSG4326' in self:
            return self[key + '_EPSG4326']
        raise KeyError
    
class TileServer(Server):
    """
    A Tile Server. Supports strict TMS and non-TMS requests. The difference is the
    support for profiles. The our internal tile cache starts with one tile at the
    first level (like KML, etc.), but the global-geodetic and global-mercator
    start with two and four tiles. The ``tile_request`` should set ``use_profiles``
    accordingly (eg. False if first level is one tile)
    """
    names = ('tiles', 'tms')
    request_parser = staticmethod(tile_request)
    request_methods = ('map', 'tms_capabilities')
    template_file = 'tms_capabilities.xml'
    layer_template_file = 'tms_tilemap_capabilities.xml'

    def __init__(self, layers, md):
        Server.__init__(self)
        self.layers = TileLayers(layers)
        self.md = md
    
    def map(self, tile_request):
        """
        :return: the requested tile
        :rtype: Response
        """
        layer = self.layer(tile_request)
        tile = layer.render(tile_request, use_profiles=tile_request.use_profiles)
        resp = Response(tile.as_buffer(), content_type='image/' + tile_request.format)
        resp.cache_headers(tile.timestamp, etag_data=(tile.timestamp, tile.size),
                           max_age=base_config().tiles.expires_hours * 60 * 60)
        resp.make_conditional(ctx.env)
        return resp
    
    def layer(self, tile_request):
        try:
            return self.layers[tile_request.layer]
        except KeyError:
            raise RequestError('unknown layer: ' + tile_request.layer, request=tile_request)
    
    def tms_capabilities(self, tms_request):
        """
        :return: the rendered tms capabilities
        :rtype: Response
        """
        service = self._service_md(tms_request)
        if hasattr(tms_request, 'layer'):
            layer = self.layer(tms_request)
            result = self._render_layer_template(layer, service)
        else:
            result = self._render_template(service)

        return Response(result, mimetype='text/xml')
    
    def _service_md(self, map_request):
        md = dict(self.md)
        md['url'] = map_request.request.base_url
        return md
    
    def _render_template(self, service):
        template = env.get_template(self.template_file)
        return template.render(service=service, layers=self.layers)
    
    def _render_layer_template(self, layer, service):
        template = env.get_template(self.layer_template_file)
        return template.render(service=service, layer=layer)

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
    
