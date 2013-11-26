# -:- encoding: utf-8 -:-
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

from __future__ import division, with_statement

import math
import time

from mapproxy.compat import iteritems, itervalues
from mapproxy.response import Response
from mapproxy.exception import RequestError
from mapproxy.service.base import Server
from mapproxy.request.tile import tile_request
from mapproxy.request.base import split_mime_type
from mapproxy.layer import map_extent_from_grid
from mapproxy.source import SourceError
from mapproxy.srs import SRS
from mapproxy.grid import default_bboxs
from mapproxy.image import BlankImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.image.mask import mask_image_source_from_coverage
from mapproxy.util.ext.odict import odict
from mapproxy.util.coverage import load_limited_to

import logging
log = logging.getLogger(__name__)


from mapproxy.template import template_loader, bunch
get_template = template_loader(__name__, 'templates')

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
    request_methods = ('map', 'tms_capabilities, tms_root_resource')
    template_file = 'tms_capabilities.xml'
    layer_template_file = 'tms_tilemap_capabilities.xml'
    root_resource_template_file = 'tms_root_resource.xml'

    def __init__(self, layers, md, max_tile_age=None, use_dimension_layers=False, origin=None):
        Server.__init__(self)
        self.layers = layers
        self.md = md
        self.max_tile_age = max_tile_age
        self.use_dimension_layers = use_dimension_layers
        self.origin = origin

    def map(self, tile_request):
        """
        :return: the requested tile
        :rtype: Response
        """
        if self.origin and not tile_request.origin:
            tile_request.origin = self.origin
        layer, limit_to = self.layer(tile_request)

        def decorate_img(image):
            query_extent = (layer.grid.srs.srs_code,
                layer.tile_bbox(tile_request, use_profiles=tile_request.use_profiles))
            return self.decorate_img(image, 'tms', [layer.name], tile_request.http.environ, query_extent)

        tile = layer.render(tile_request, use_profiles=tile_request.use_profiles, coverage=limit_to, decorate_img=decorate_img)

        tile_format = getattr(tile, 'format', tile_request.format)
        resp = Response(tile.as_buffer(), content_type='image/' + tile_format)
        if tile.cacheable:
            resp.cache_headers(tile.timestamp, etag_data=(tile.timestamp, tile.size),
                               max_age=self.max_tile_age)
        else:
            resp.cache_headers(no_cache=True)
        resp.make_conditional(tile_request.http)
        return resp

    def _internal_layer(self, tile_request):
        if '_layer_spec' in tile_request.dimensions:
            name = tile_request.layer + '_' + tile_request.dimensions['_layer_spec']
        else:
            name = tile_request.layer
        if name in self.layers:
            return self.layers[name]
        if name + '_EPSG900913' in self.layers:
            return self.layers[name + '_EPSG900913']
        if name + '_EPSG4326' in self.layers:
            return self.layers[name + '_EPSG4326']
        return None

    def _internal_dimension_layer(self, tile_request):
        key = (tile_request.layer, tile_request.dimensions.get('_layer_spec'))
        return self.layers.get(key)

    def layer(self, tile_request):
        if self.use_dimension_layers:
            internal_layer = self._internal_dimension_layer(tile_request)
        else:
            internal_layer = self._internal_layer(tile_request)
        if internal_layer is None:
            raise RequestError('unknown layer: ' + tile_request.layer, request=tile_request)

        limit_to = self.authorize_tile_layer(internal_layer, tile_request)
        return internal_layer, limit_to

    def authorize_tile_layer(self, tile_layer, request):
        if 'mapproxy.authorize' in request.http.environ:
            if request.tile:
                query_extent = (tile_layer.grid.srs.srs_code,
                    tile_layer.tile_bbox(request, use_profiles=request.use_profiles))
            else:
                query_extent = None # for layer capabilities
            result = request.http.environ['mapproxy.authorize']('tms', [tile_layer.name],
                query_extent=query_extent, environ=request.http.environ)
            if result['authorized'] == 'unauthenticated':
                raise RequestError('unauthorized', status=401)
            if result['authorized'] == 'full':
                return
            if result['authorized'] == 'partial':
                if result['layers'].get(tile_layer.name, {}).get('tile', False) == True:
                    limited_to = result['layers'][tile_layer.name].get('limited_to')
                    if not limited_to:
                        limited_to = result.get('limited_to')
                    if limited_to:
                        return load_limited_to(limited_to)
                    else:
                        return None
            raise RequestError('forbidden', status=403)

    def authorized_tile_layers(self, env):
        if 'mapproxy.authorize' in env:
            result = env['mapproxy.authorize']('tms', [l for l in self.layers],
                query_extent=None, environ=env)
            if result['authorized'] == 'unauthenticated':
                raise RequestError('unauthorized', status=401)
            if result['authorized'] == 'full':
                return self.layers
            if result['authorized'] == 'none':
                raise RequestError('forbidden', status=403)
            allowed_layers = odict()
            for layer in itervalues(self.layers):
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
            layer, limit_to = self.layer(tms_request)
            result = self._render_layer_template(layer, service)
        else:
            layers = self.authorized_tile_layers(tms_request.http.environ)
            result = self._render_template(layers, service)

        return Response(result, mimetype='text/xml')

    def tms_root_resource(self, tms_request):
        """
        :return: root resource with all available versions of the service
        :rtype: Response
        """
        service = self._service_md(tms_request)
        result = self._render_root_resource_template(service)
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

    def _render_root_resource_template(self, service):
        template = get_template(self.root_resource_template_file)
        return template.substitute(service=bunch(default='', **service))

class TileLayer(object):
    def __init__(self, name, title, md, tile_manager, dimensions=None):
        """
        :param md: the layer metadata
        :param tile_manager: the layer tile manager
        """
        self.name = name
        self.title = title
        self.md = md
        self.tile_manager = tile_manager
        self.dimensions = dimensions
        self.grid = TileServiceGrid(tile_manager.grid)
        self.extent = map_extent_from_grid(self.grid)
        self._empty_tile = None
        self._mixed_format = True if self.md.get('format', False) == 'mixed' else False
        self.empty_response_as_png = True

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
        # force png format for capabilities & requests if mixed format
        if self._mixed_format:
            return 'image/png'
        return self.md.get('format', 'image/png')

    def _internal_tile_coord(self, tile_request, use_profiles=False):
        tile_coord = self.grid.internal_tile_coord(tile_request.tile, use_profiles)
        if tile_coord is None:
            raise RequestError('The requested tile is outside the bounding box'
                               ' of the tile map.', request=tile_request,
                               code='TileOutOfRange')
        if tile_request.origin == 'nw' and self.grid.origin not in ('ul', 'nw'):
            tile_coord = self.grid.flip_tile_coord(tile_coord)
        elif tile_request.origin == 'sw' and self.grid.origin not in ('ll', 'sw', None):
            tile_coord = self.grid.flip_tile_coord(tile_coord)

        return tile_coord

    def empty_response(self):
        if self.empty_response_as_png:
            format = 'png'
        else:
            format = self.format
        if not self._empty_tile:
            img = BlankImageSource(size=self.grid.tile_size,
                image_opts=ImageOptions(format=format, transparent=True))
            self._empty_tile = img.as_buffer().read()
        return ImageResponse(self._empty_tile, format=format, timestamp=time.time())

    def tile_bbox(self, tile_request, use_profiles=False, limit=False):
        tile_coord = self._internal_tile_coord(tile_request, use_profiles=use_profiles)
        return self.grid.tile_bbox(tile_coord, limit=limit)

    def checked_dimensions(self, tile_request):
        dimensions = {}

        for dimension, values in iteritems(self.dimensions):
            value = tile_request.dimensions.get(dimension)
            if value in values:
                dimensions[dimension] = value
            elif not value or value == 'default':
                dimensions[dimension] = values.default
            else:
                raise RequestError('invalid dimension value (%s=%s).'
                    % (dimension, value), request=tile_request,
                       code='InvalidParameterValue')
        return dimensions

    def render(self, tile_request, use_profiles=False, coverage=None, decorate_img=None):
        if tile_request.format != self.format:
            raise RequestError('invalid format (%s). this tile set only supports (%s)'
                               % (tile_request.format, self.format), request=tile_request,
                               code='InvalidParameterValue')

        tile_coord = self._internal_tile_coord(tile_request, use_profiles=use_profiles)

        coverage_intersects = False
        if coverage:
            tile_bbox = self.grid.tile_bbox(tile_coord)
            if coverage.contains(tile_bbox, self.grid.srs):
                pass
            elif coverage.intersects(tile_bbox, self.grid.srs):
                coverage_intersects = True
            else:
                return self.empty_response()

        dimensions = self.checked_dimensions(tile_request)

        try:
            with self.tile_manager.session():
                tile = self.tile_manager.load_tile_coord(tile_coord,
                    dimensions=dimensions, with_metadata=True)
            if tile.source is None:
                return self.empty_response()

            # Provide the wrapping WSGI app or filter the opportunity to process the
            # image before it's wrapped up in a response
            if decorate_img:
                tile.source = decorate_img(tile.source)

            if coverage_intersects:
                if self.empty_response_as_png:
                    format = 'png'
                    image_opts = ImageOptions(transparent=True, format='png')
                else:
                    format = self.format
                    image_opts = tile.source.image_opts

                tile.source = mask_image_source_from_coverage(
                    tile.source, tile_bbox, self.grid.srs, coverage, image_opts)

                return TileResponse(tile, format=format, image_opts=image_opts)

            format = None if self._mixed_format else tile_request.format
            return TileResponse(tile, format=format, image_opts=self.tile_manager.image_opts)
        except SourceError as e:
            raise RequestError(e.args[0], request=tile_request, internal=True)

class ImageResponse(object):
    """
    Response from an image.
    """
    def __init__(self, img, format, timestamp):
        self.img = img
        self.timestamp = timestamp
        self.format = format
        self.size = 0
        self.cacheable = True

    def as_buffer(self):
        return self.img


class TileResponse(object):
    """
    Response from a Tile.
    """
    def __init__(self, tile, format=None, timestamp=None, image_opts=None):
        self.tile = tile
        self.timestamp = tile.timestamp
        self.size = tile.size
        self.cacheable = tile.cacheable
        self._buf = self.tile.source_buffer(format=format, image_opts=image_opts)
        self.format = format or self._format_from_magic_bytes()

    def as_buffer(self):
        return self._buf

    def _format_from_magic_bytes(self):
        #read the 2 magic bytes from the buffer
        magic_bytes = self._buf.read(2)
        self._buf.seek(0)
        if magic_bytes == b'\xFF\xD8':
            return 'jpeg'
        return 'png'

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
        if int(z) < 0:
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
