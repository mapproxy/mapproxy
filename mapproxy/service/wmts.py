# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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
WMS service handler
"""
from __future__ import print_function

from functools import partial

from mapproxy.compat import iteritems, itervalues, iterkeys
from mapproxy.request.wmts import (
    wmts_request, make_wmts_rest_request_parser,
    URLTemplateConverter,
)
from mapproxy.service.base import Server
from mapproxy.response import Response
from mapproxy.exception import RequestError
from mapproxy.util.coverage import load_limited_to
from mapproxy.util.ext.odict import odict

from mapproxy.template import template_loader, bunch
env = {'bunch': bunch}
get_template = template_loader(__name__, 'templates', namespace=env)

import logging
log = logging.getLogger(__name__)

class WMTSServer(Server):
    service = 'wmts'

    def __init__(self, layers, md, request_parser=None, max_tile_age=None):
        Server.__init__(self)
        self.request_parser = request_parser or wmts_request
        self.md = md
        self.max_tile_age = max_tile_age
        self.layers, self.matrix_sets = self._matrix_sets(layers)
        self.capabilities_class = Capabilities

    def _matrix_sets(self, layers):
        sets = {}
        layers_grids = odict()
        for layer in layers.values():
            grid = layer.grid
            if not grid.supports_access_with_origin('nw'):
                log.warn("skipping layer '%s' for WMTS, grid '%s' of cache '%s' is not compatible with WMTS",
                    layer.name, grid.name, layer.md['cache_name'])
                continue
            if grid.name not in sets:
                try:
                    sets[grid.name] = TileMatrixSet(grid)
                except AssertionError:
                    continue # TODO
            layers_grids.setdefault(layer.name, odict())[grid.name] = layer
        wmts_layers = odict()
        for layer_name, layers in layers_grids.items():
            wmts_layers[layer_name] = WMTSTileLayer(layers)
        return wmts_layers, sets.values()

    def capabilities(self, request):
        service = self._service_md(request)
        layers = self.authorized_tile_layers(request.http.environ)
        result = self.capabilities_class(service, layers, self.matrix_sets).render(request)
        return Response(result, mimetype='application/xml')

    def tile(self, request):
        self.check_request(request)

        tile_layer = self.layers[request.layer][request.tilematrixset]
        if not request.format:
            request.format = tile_layer.format

        self.check_request_dimensions(tile_layer, request)

        limited_to = self.authorize_tile_layer(tile_layer, request)

        def decorate_img(image):
            query_extent = tile_layer.grid.srs.srs_code, tile_layer.tile_bbox(request)
            return self.decorate_img(image, 'wmts', [tile_layer.name], request.http.environ, query_extent)

        tile = tile_layer.render(request, coverage=limited_to, decorate_img=decorate_img)

        # set the content_type to tile.format and not to request.format ( to support mixed_mode)
        resp = Response(tile.as_buffer(), content_type='image/' + tile.format)
        resp.cache_headers(tile.timestamp, etag_data=(tile.timestamp, tile.size),
                           max_age=self.max_tile_age)
        resp.make_conditional(request.http)
        return resp

    def authorize_tile_layer(self, tile_layer, request):
        if 'mapproxy.authorize' in request.http.environ:
            query_extent = tile_layer.grid.srs.srs_code, tile_layer.tile_bbox(request)
            result = request.http.environ['mapproxy.authorize']('wmts', [tile_layer.name],
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
            result = env['mapproxy.authorize']('wmts', [l for l in self.layers],
                query_extent=None, environ=env)
            if result['authorized'] == 'unauthenticated':
                raise RequestError('unauthorized', status=401)
            if result['authorized'] == 'full':
                return self.layers.values()
            if result['authorized'] == 'none':
                raise RequestError('forbidden', status=403)
            allowed_layers = []
            for layer in itervalues(self.layers):
                if result['layers'].get(layer.name, {}).get('tile', False) == True:
                    allowed_layers.append(layer)
            return allowed_layers
        else:
            return self.layers.values()

    def check_request(self, request):
        request.make_tile_request()
        if request.layer not in self.layers:
            raise RequestError('unknown layer: ' + str(request.layer),
                code='InvalidParameterValue', request=request)
        if request.tilematrixset not in self.layers[request.layer]:
            raise RequestError('unknown tilematrixset: ' + str(request.tilematrixset),
                code='InvalidParameterValue', request=request)

    def check_request_dimensions(self, tile_layer, request):
        # allow arbitrary dimensions in KVP service
        # actual used values are checked later in TileLayer
        pass

    def _service_md(self, tile_request):
        md = dict(self.md)
        md['url'] = tile_request.url
        return md


class WMTSRestServer(WMTSServer):
    """
    OGC WMTS 1.0.0 RESTful Server
    """
    service = None
    names = ('wmts',)
    request_methods = ('tile', 'capabilities')
    default_template = '/{Layer}/{TileMatrixSet}/{TileMatrix}/{TileCol}/{TileRow}.{Format}'

    def __init__(self, layers, md, max_tile_age=None, template=None):
        WMTSServer.__init__(self, layers, md)
        self.max_tile_age = max_tile_age
        self.template = template or self.default_template
        self.url_converter = URLTemplateConverter(self.template)
        self.request_parser = make_wmts_rest_request_parser(self.url_converter)
        self.capabilities_class = partial(RestfulCapabilities, url_converter=self.url_converter)

    def check_request_dimensions(self, tile_layer, request):
        # check that unknown dimension for this layer are set to default
        if request.dimensions:
            for dimension, value in iteritems(request.dimensions):
                dimension = dimension.lower()
                if dimension not in tile_layer.dimensions and value != 'default':
                    raise RequestError('unknown dimension: ' + str(dimension),
                        code='InvalidParameterValue', request=request)


class Capabilities(object):
    """
    Renders WMS capabilities documents.
    """
    def __init__(self, server_md, layers, matrix_sets):
        self.service = server_md
        self.layers = layers
        self.matrix_sets = matrix_sets

    def render(self, _map_request):
        return self._render_template(_map_request.capabilities_template)

    def template_context(self):
        return dict(service=bunch(default='', **self.service),
                    restful=False,
                    layers=self.layers,
                    tile_matrix_sets=self.matrix_sets)

    def _render_template(self, template):
        template = get_template(template)
        doc = template.substitute(**self.template_context())
        # strip blank lines
        doc = '\n'.join(l for l in doc.split('\n') if l.rstrip())
        return doc

class RestfulCapabilities(Capabilities):
    def __init__(self, server_md, layers, matrix_sets, url_converter):
        Capabilities.__init__(self, server_md, layers, matrix_sets)
        self.url_converter = url_converter

    def template_context(self):
        return dict(service=bunch(default='', **self.service),
                    restful=True,
                    layers=self.layers,
                    tile_matrix_sets=self.matrix_sets,
                    resource_template=self.url_converter.template,
                    # dimension_key maps lowercase dimensions to the actual
                    # casing from the restful template
                    dimension_keys=dict((k.lower(), k) for k in self.url_converter.dimensions),
                    format_resource_template=format_resource_template,
                    )

def format_resource_template(layer, template, service):
    # TODO: remove {{Format}} in 1.6
    if '{{Format}}' in template:
        template = template.replace('{{Format}}', layer.format)
    if '{Format}' in template:
        template = template.replace('{Format}', layer.format)

    if '{Layer}' in template:
        template = template.replace('{Layer}', layer.name)

    return service.url + template

class WMTSTileLayer(object):
    """
    Wrap multiple TileLayers for the same cache but with different grids.
    """
    def __init__(self, layers):
        self.grids = [lyr.grid for lyr in layers.values()]
        self.layers = layers
        self._layer = layers[next(iterkeys(layers))]

    def __getattr__(self, name):
        return getattr(self._layer, name)

    def __contains__(self, gridname):
        return gridname in self.layers

    def __getitem__(self, gridname):
        return self.layers[gridname]


from mapproxy.grid import tile_grid

# calculated from well-known scale set GoogleCRS84Quad
METERS_PER_DEEGREE = 111319.4907932736

def meter_per_unit(srs):
    if srs.is_latlong:
        return METERS_PER_DEEGREE
    return 1

class TileMatrixSet(object):
    def __init__(self, grid):
        self.grid = grid
        self.name = grid.name
        self.srs_name = grid.srs.srs_code
        self.tile_matrices = list(self._tile_matrices())

    def __iter__(self):
        return iter(self.tile_matrices)

    def _tile_matrices(self):
        for level, res in self.grid.resolutions.iteritems():
            origin = self.grid.origin_tile(level, 'ul')
            bbox = self.grid.tile_bbox(origin)
            topleft = bbox[0], bbox[3]
            if self.grid.srs.is_axis_order_ne:
                topleft = bbox[3], bbox[0]
            grid_size = self.grid.grid_sizes[level]
            scale_denom = res / (0.28 / 1000) * meter_per_unit(self.grid.srs)
            yield bunch(
                identifier=level,
                topleft=topleft,
                grid_size=grid_size,
                scale_denom=scale_denom,
                tile_size=self.grid.tile_size,
            )

if __name__ == '__main__':
    print(TileMatrixSet(tile_grid(900913)).tile_matrixes())
    print(TileMatrixSet(tile_grid(4326, origin='ul')).tile_matrixes())
