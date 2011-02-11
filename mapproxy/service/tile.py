# -:- encoding: utf-8 -:-
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

from __future__ import division

import math
import time

from mapproxy.response import Response
from mapproxy.exception import RequestError
from mapproxy.service.base import Server
from mapproxy.request.tile import tile_request
from mapproxy.request.base import split_mime_type
from mapproxy.config import base_config
from mapproxy.layer import map_extent_from_grid
from mapproxy.source import SourceError
from mapproxy.srs import SRS
from mapproxy.grid import default_bboxs
from mapproxy.image import BlankImageSource
from mapproxy.util.ext.odict import odict

import logging
log = logging.getLogger(__name__)


from mapproxy.template import template_loader, bunch
get_template = template_loader(__file__, 'templates')

import logging
log = logging.getLogger(__name__)

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
        self.layers = layers
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
        resp.make_conditional(tile_request.http)
        return resp
    
    def _internal_layer(self, name):
        if name in self.layers:
            return self.layers[name]
        if name + '_EPSG900913' in self.layers:
            return self.layers[name + '_EPSG900913']
        if name + '_EPSG4326' in self.layers:
            return self.layers[name + '_EPSG4326']
        return None
    
    def layer(self, tile_request):
        internal_layer = self._internal_layer(tile_request.layer)
        if internal_layer is None:
            raise RequestError('unknown layer: ' + tile_request.layer, request=tile_request)
        self.authorize_tile_layer(internal_layer.name, tile_request.http.environ)
        return internal_layer
    
    def authorize_tile_layer(self, layer_name, env):
        if 'mapproxy.authorize' in env:
            result = env['mapproxy.authorize']('tms', [layer_name])
            if result['authorized'] == 'full':
                return
            if result['authorized'] == 'partial':
                if result['layers'].get(layer_name, {}).get('tile', False) == True:
                    return
            raise RequestError('forbidden', status=403)
    
    def authorized_tile_layers(self, env):
        if 'mapproxy.authorize' in env:
            result = env['mapproxy.authorize']('tms', [l for l in self.layers])
            if result['authorized'] == 'full':
                return self.layers
            if result['authorized'] == 'none':
                raise RequestError('forbidden', status=403)
            allowed_layers = odict()
            for layer in self.layers.itervalues():
                if result['layers'].get(layer.name, {}).get('tile', False) == True:
                    allowed_layers[layer.name] = layer
            return allowed_layers
        else:
            return self.layers
    
    def tms_capabilities(self, tms_request):
        """
        :return: the rendered tms capabilities
        :rtype: Response
        """
        service = self._service_md(tms_request)
        if hasattr(tms_request, 'layer'):
            layer = self.layer(tms_request)
            self.authorize_tile_layer(layer.name, tms_request.http.environ)
            result = self._render_layer_template(layer, service)
        else:
            layers = self.authorized_tile_layers(tms_request.http.environ)
            result = self._render_template(layers, service)

        return Response(result, mimetype='text/xml')
    
    def _service_md(self, map_request):
        md = dict(self.md)
        md['url'] = map_request.http.base_url
        return md
    
    def _render_template(self, layers, service):
        template = get_template(self.template_file)
        return template.substitute(service=bunch(default='', **service), layers=layers)
    
    def _render_layer_template(self, layer, service):
        template = get_template(self.layer_template_file)
        return template.substitute(service=bunch(default='', **service), layer=layer)

class TileLayer(object):
    def __init__(self, name, title, md, tile_manager):
        """
        :param md: the layer metadata
        :param tile_manager: the layer tile manager
        """
        self.name = name
        self.title = title
        self.md = md
        self.tile_manager = tile_manager
        self.grid = TileServiceGrid(tile_manager.grid)
        self.extent = map_extent_from_grid(self.grid)
        self._empty_tile = None
    
    @property
    def bbox(self):
        return self.grid.bbox

    @property
    def srs(self):
        return self.grid.srs
    
    @property
    def format(self):
        _mime_class, format, _options = split_mime_type(self.format_mime_type)
        return format
    
    @property
    def format_mime_type(self):
        return self.md.get('format', 'image/png')
    
    def _internal_tile_coord(self, tile_request, use_profiles=False):
        tile_coord = self.grid.internal_tile_coord(tile_request.tile, use_profiles)
        if tile_coord is None:
            raise RequestError('The requested tile is outside the bounding box'
                               ' of the tile map.', request=tile_request)
        if tile_request.origin == 'nw':
            tile_coord = self.grid.flip_tile_coord(tile_coord)
        return tile_coord
    
    def empty_response(self):
        if not self._empty_tile:
            img = BlankImageSource(size=self.grid.tile_size, transparent=True)
            self._empty_tile = img.as_buffer(self.format)
        return ImageResponse(self._empty_tile, time.time())
    
    def render(self, tile_request, use_profiles=False):
        if tile_request.format != self.format:
            raise RequestError('invalid format (%s). this tile set only supports (%s)'
                               % (tile_request.format, self.format), request=tile_request)
        tile_coord = self._internal_tile_coord(tile_request, use_profiles=use_profiles)
        try:
            tile = self.tile_manager.load_tile_coord(tile_coord, with_metadata=True)
            if tile.source is None: return self.empty_response()
            return TileResponse(tile)
        except SourceError, e:
            log.error(e)
            raise RequestError(e.args[0], request=tile_request, internal=True)

class ImageResponse(object):
    """
    Response from an image.
    """
    def __init__(self, img, timestamp):
        self.img = img
        self.timestamp = 0
        self.size = 0
    
    def as_buffer(self):
        return self.img
    

class TileResponse(object):
    """
    Response from a Tile.
    """
    def __init__(self, tile, timestamp=None):
        self.tile = tile
    
    def as_buffer(self):
        return self.tile.source_buffer()
    
    @property
    def timestamp(self):
        return self.tile.timestamp
    
    @property
    def size(self):
        return self.tile.size
    

class TileServiceGrid(object):
    """
    Wraps a `TileGrid` and adds some ``TileService`` specific methods.
    """
    def __init__(self, grid):
        self.grid = grid
        self.profile = None
        
        if self.grid.srs == SRS(900913) and self.grid.bbox == default_bboxs[SRS((900913))]:
            self.profile = 'global-mercator'
            self.srs_name = 'OSGEO:41001' # as required by TMS 1.0.0
            self._skip_first_level = True
        
        elif self.grid.srs == SRS(4326) and self.grid.bbox == default_bboxs[SRS((4326))]:
            self.profile = 'global-geodetic'
            self.srs_name = 'EPSG:4326'
            self._skip_first_level = True
        else:
            self.profile = 'local'
            self.srs_name = self.grid.srs.srs_code
            self._skip_first_level = False
        
        self._skip_odd_level = False

        res_factor = self.grid.resolutions[0]/self.grid.resolutions[1]
        if res_factor == math.sqrt(2):
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
    
    @property
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
    
    def external_tile_coord(self, tile_coord, use_profiles):
        """
        Converts internal tile coords to external tile coords.
        
        :param tile_coord: the internal tile coord
        :param use_profiles: True if the tile service supports global 
                             profiles (see `mapproxy.core.server.TileServer`)
        """
        x, y, z = tile_coord
        if z < 0:
            return None
        if use_profiles and self._skip_first_level:
            z -= 1
        if self._skip_odd_level:
            z //= 2
        return (x, y, z)
