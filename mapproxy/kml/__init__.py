import re
from jinja2 import Environment, PackageLoader

from mapproxy.core.response import Response
from mapproxy.core.exceptions import RequestError, PlainExceptionHandler
from mapproxy.core.server import Server
from mapproxy.tms.request import TileRequest
from mapproxy.core.srs import SRS
from mapproxy.core.app import ctx
from mapproxy.core.config import base_config

env = Environment(loader=PackageLoader('mapproxy.kml', 'templates'),
                  trim_blocks=True)

class KMLRequest(TileRequest):
    """
    Class for TMS-like KML requests.
    """
    request_handler_name = 'map'
    req_prefix = '/kml'
    tile_req_re = re.compile(r'''^(?P<begin>/kml)/
            (?P<layer>[^/]+)/
            ((?P<layer_spec>[^/]+)/)?
            (?P<z>-?\d+)/
            (?P<x>-?\d+)/
            (?P<y>-?\d+)\.(?P<format>\w+)''', re.VERBOSE)
    
    def __init__(self, request):
        TileRequest.__init__(self, request)
        if self.format == 'kml':
            self.request_handler_name = 'kml'
    
    @property
    def exception_handler(self):
        return PlainExceptionHandler()

def kml_request(req):
    return KMLRequest(req)

class KMLServer(Server):
    """
    OGC KML 2.2 Server 
    """
    names = ('kml',)
    request_parser = staticmethod(kml_request)
    request_methods = ('map', 'kml')
    template_file = 'kml.xml'
    
    def __init__(self, layers, md):
        Server.__init__(self)
        self.layers = layers
        self.md = md
        
        self.max_age = base_config().tiles.expires_hours * 60 * 60
    
    def map(self, map_request):
        """
        :return: the requested tile
        """
        layer = self.layer(map_request)
        tile = layer.render(map_request)
        resp = Response(tile.as_buffer(),
                        content_type='image/' + map_request.format)
        resp.cache_headers(tile.timestamp, etag_data=(tile.timestamp, tile.size),
                           max_age=base_config().tiles.expires_hours * 60 * 60)
        resp.make_conditional(ctx.env)
        return resp

    def layer(self, tile_request):
        if tile_request.layer in self.layers:
            return self.layers[tile_request.layer]
        if tile_request.layer + '_EPSG4326' in self.layers:
            return self.layers[tile_request.layer + '_EPSG4326']
        if tile_request.layer + '_EPSG900913' in self.layers:
            return self.layers[tile_request.layer + '_EPSG900913']
        raise RequestError('unknown layer: ' + tile_request.layer, request=tile_request)

    def kml(self, map_request):
        """
        :return: the rendered KML response
        """
        layer = self.layer(map_request)
        tile_coord = map_request.tile
        
        initial_level = False
        if tile_coord[2] == 0:
            initial_level = True
        
        bbox = self._tile_bbox(tile_coord, layer.grid)
        if bbox is None:
            raise RequestError('The requested tile is outside the bounding box '
                               'of the tile map.', request=map_request)
        tile = SubTile(tile_coord, bbox)
        
        subtiles = self._get_subtiles(tile_coord, layer)
        layer = {'name': map_request.layer, 'format': layer.format, 'md': layer.md}
        service = {'url': map_request.request.script_url.rstrip('/')}
        template = env.get_template(self.template_file)
        result = template.render(tile=tile, subtiles=subtiles, layer=layer,
                                 service=service, initial_level=initial_level)
        resp = Response(result, content_type='application/vnd.google-earth.kml+xml')
        resp.cache_headers(etag_data=(result,), max_age=self.max_age)
        resp.make_conditional(ctx.env)
        return resp

    def _get_subtiles(self, tile, layer):
        """
        Create four `SubTile` for the next level of `tile`.
        """
        x, y, z = tile
        subtiles = []
        for coord in [(x*2, y*2, z+1), (x*2+1, y*2, z+1), 
                      (x*2+1, y*2+1, z+1), (x*2, y*2+1, z+1)]:
            bbox = self._tile_bbox(coord, layer.grid)
            if bbox is not None:
                subtiles.append(SubTile(coord, bbox))
        return subtiles
    
    def _tile_bbox(self, tile_coord, grid):
        tile_coord = grid.internal_tile_coord(tile_coord, use_profiles=False)
        if tile_coord is None:
            return None
        src_bbox = grid.tile_bbox(tile_coord)
        bbox = grid.srs.transform_bbox_to(SRS(4326), src_bbox, with_points=4)
        if grid.srs == SRS(900913):
            bbox = list(bbox)
            if abs(src_bbox[1] -  -20037508.342789244) < 0.1:
                bbox[1] = -90.0
            if abs(src_bbox[3] -  20037508.342789244) < 0.1:
                bbox[3] = 90.0
        return bbox
    
    def check_map_request(self, map_request):
        if map_request.layer not in self.layers:
            raise RequestError('unknown layer: ' + map_request.layer, request=map_request)


class SubTile(object):
    """
    Contains the ``bbox`` and ``coord`` of a sub tile.
    """
    def __init__(self, coord, bbox):
        self.coord = coord
        self.bbox = bbox