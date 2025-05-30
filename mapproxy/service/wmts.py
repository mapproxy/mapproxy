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

import re
from functools import partial
import logging
from collections import OrderedDict

from mapproxy.request.wmts import (
    wmts_request, make_wmts_rest_request_parser,
    URLTemplateConverter,
    FeatureInfoURLTemplateConverter,
)
from mapproxy.layer import InfoQuery
from mapproxy.featureinfo import combine_docs
from mapproxy.service.base import Server
from mapproxy.response import Response
from mapproxy.exception import RequestError
from mapproxy.util.coverage import load_limited_to

from mapproxy.template import template_loader, bunch

env = {'bunch': bunch}
get_template = template_loader(__package__, 'templates', namespace=env)
log = logging.getLogger(__name__)


class WMTSServer(Server):
    service = 'wmts'

    def __init__(self, layers, md, request_parser=None, max_tile_age=None, info_formats=None):
        Server.__init__(self)
        self.request_parser = request_parser or wmts_request
        self.md = md
        self.max_tile_age = max_tile_age
        self.layers, self.matrix_sets = self._matrix_sets(layers)
        self.capabilities_class = Capabilities
        self.fi_transformers = None
        self.info_formats = info_formats or {}

    def _matrix_sets(self, layers):
        sets = {}
        layers_grids = OrderedDict()
        for layer in layers.values():
            grid = layer.grid
            if not grid.supports_access_with_origin('nw'):
                log.warning("skipping layer '%s' for WMTS, grid '%s' of cache '%s' is not compatible with WMTS",
                            layer.name, grid.name, layer.md['cache_name'])
                continue
            if grid.name not in sets:
                try:
                    sets[grid.name] = TileMatrixSet(grid)
                except AssertionError:
                    continue  # TODO
            layers_grids.setdefault(layer.name, OrderedDict())[grid.name] = layer
        wmts_layers = OrderedDict()
        for layer_name, layers in layers_grids.items():
            wmts_layers[layer_name] = WMTSTileLayer(layers)
        return wmts_layers, sets.values()

    def capabilities(self, request):
        service = self._service_md(request)
        layers = self.authorized_tile_layers(request.http.environ)

        result = self.capabilities_class(service, layers, self.matrix_sets,
                                         info_formats=self.info_formats).render(request)
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

    def featureinfo(self, request):
        infos = []
        self.check_request(request, self.info_formats)

        tile_layer = self.layers[request.layer][request.tilematrixset]
        if not request.format:
            request.format = tile_layer.format

        feature_count = None
        # WMTS REST style request do not have request params
        if hasattr(request, 'params'):
            feature_count = request.params.get('feature_count', None)

        bbox = tile_layer.grid.tile_bbox(request.tile)
        query = InfoQuery(bbox, tile_layer.grid.tile_size, tile_layer.grid.srs, request.pos,
                          request.infoformat, feature_count=feature_count)
        self.check_request_dimensions(tile_layer, request)
        coverage = self.authorize_tile_layer(tile_layer, request, featureinfo=True)

        if not tile_layer.info_sources:
            raise RequestError('layer %s not queryable' % str(request.layer),
                               code='OperationNotSupported', request=request)

        if coverage and not coverage.contains(query.coord, query.srs):
            infos = []
        else:
            for source in tile_layer.info_sources:
                info = source.get_info(query)
                if info is None:
                    continue
                infos.append(info)

        mimetype = request.infoformat

        if not infos:
            return Response('', mimetype=mimetype)

        resp, _ = combine_docs(infos)

        return Response(resp, mimetype=mimetype)

    def authorize_tile_layer(self, tile_layer, request, featureinfo=False):
        if 'mapproxy.authorize' not in request.http.environ:
            return

        query_extent = tile_layer.grid.srs.srs_code, tile_layer.tile_bbox(request)

        service = 'wmts'
        key = 'tile'
        if featureinfo:
            service += '.featureinfo'
            key = 'featureinfo'

        result = request.http.environ['mapproxy.authorize'](service, [tile_layer.name],
                                                            query_extent=query_extent, environ=request.http.environ)
        if result['authorized'] == 'unauthenticated':
            raise RequestError('unauthorized', status=401)
        if result['authorized'] == 'full':
            return
        if result['authorized'] == 'partial':
            if result['layers'].get(tile_layer.name, {}).get(key, False) is True:
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
            result = env['mapproxy.authorize']('wmts', [x for x in self.layers],
                                               query_extent=None, environ=env)
            if result['authorized'] == 'unauthenticated':
                raise RequestError('unauthorized', status=401)
            if result['authorized'] == 'full':
                return list(self.layers.values())
            if result['authorized'] == 'none':
                raise RequestError('forbidden', status=403)
            allowed_layers = []
            for layer in self.layers.values():
                if result['layers'].get(layer.name, {}).get('tile', False):
                    allowed_layers.append(layer)
            return allowed_layers
        else:
            return list(self.layers.values())

    def check_request(self, request, info_formats=None):
        request.make_request()
        if request.layer not in self.layers:
            raise RequestError('unknown layer: ' + str(request.layer),
                               code='InvalidParameterValue', request=request)
        if request.tilematrixset not in self.layers[request.layer]:
            raise RequestError('unknown tilematrixset: ' + str(request.tilematrixset),
                               code='InvalidParameterValue', request=request)

        if info_formats is not None:
            if '/' in request.infoformat:  # mimetype
                if request.infoformat not in self.info_formats.values():
                    raise RequestError('unknown infoformat: ' + str(request.infoformat),
                                       code='InvalidParameterValue', request=request)
            else:  # RESTful suffix
                if request.infoformat not in self.info_formats:
                    raise RequestError('unknown infoformat: ' + str(request.infoformat),
                                       code='InvalidParameterValue', request=request)
                # set mimetype as infoformat
                request.infoformat = self.info_formats[request.infoformat]

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
    default_info_template = '/{Layer}/{TileMatrixSet}/{TileMatrix}/{TileCol}/{TileRow}/{I}/{J}.{InfoFormat}'

    def __init__(self, layers, md, max_tile_age=None, template=None, fi_template=None, info_formats=None):
        WMTSServer.__init__(self, layers, md)
        self.max_tile_age = max_tile_age
        self.template = template or self.default_template
        self.fi_template = fi_template or self.default_info_template
        self.info_formats = info_formats or {}
        self.url_converter = URLTemplateConverter(self.template)
        self.fi_url_converter = FeatureInfoURLTemplateConverter(self.fi_template)
        self.request_parser = make_wmts_rest_request_parser(self.url_converter, self.fi_url_converter)
        self.capabilities_class = partial(
            RestfulCapabilities, url_converter=self.url_converter, fi_url_converter=self.fi_url_converter)

    def check_request_dimensions(self, tile_layer, request):
        # check that unknown dimension for this layer are set to default
        if request.dimensions:
            for dimension, value in request.dimensions.items():
                dimension = dimension.lower()
                if dimension not in tile_layer.dimensions and value != 'default':
                    raise RequestError('unknown dimension: ' + str(dimension),
                                       code='InvalidParameterValue', request=request)


class Capabilities(object):
    """
    Renders WMS capabilities documents.
    """

    def __init__(self, server_md, layers, matrix_sets, info_formats=None):
        self.service = server_md
        self.layers = layers
        self.info_formats = info_formats or {}
        self.matrix_sets = matrix_sets

    def render(self, _map_request):
        return self._render_template(_map_request.capabilities_template)

    def template_context(self):
        service = bunch(default='', **self.service)
        base_url = re.sub(r'/service$', '', service.url)
        legendurls = {}
        for layer in self.layers:
            if layer.md['wmts_kvp_legendurl'] is not None:
                legendurls[layer.name] = (
                    layer.md['wmts_kvp_legendurl']
                    .replace('{base_url}', base_url)
                    .replace('{layer_name}', layer.name)
                )
            else:
                legendurls[layer.name] = None

        return dict(service=service,
                    restful=False,
                    layers=self.layers,
                    info_formats=self.info_formats,
                    tile_matrix_sets=self.matrix_sets,
                    legendurls=legendurls)

    def _render_template(self, template):
        template = get_template(template)
        doc = template.substitute(**self.template_context())
        # strip blank lines
        doc = '\n'.join(x for x in doc.split('\n') if x.rstrip())
        return doc


class RestfulCapabilities(Capabilities):
    def __init__(self, server_md, layers, matrix_sets, url_converter, fi_url_converter, info_formats=None):
        Capabilities.__init__(self, server_md, layers, matrix_sets, info_formats=info_formats)
        self.url_converter = url_converter
        self.fi_url_converter = fi_url_converter

    def template_context(self):
        service = bunch(default='', **self.service)
        base_url = re.sub(r'/wmts$', '', service.url)
        legendurls = {}
        for layer in self.layers:
            if layer.md['wmts_rest_legendurl'] is not None:
                legendurls[layer.name] = (
                    layer.md['wmts_rest_legendurl']
                    .replace('{base_url}', base_url)
                    .replace('{layer_name}', layer.name)
                )
            else:
                legendurls[layer.name] = None

        return dict(service=service,
                    restful=True,
                    layers=self.layers,
                    info_formats=self.info_formats,
                    tile_matrix_sets=self.matrix_sets,
                    resource_template=self.url_converter.template,
                    fi_resource_template=self.fi_url_converter.template,
                    # dimension_key maps lowercase dimensions to the actual
                    # casing from the restful template
                    dimension_keys=dict((k.lower(), k) for k in self.url_converter.dimensions),
                    format_resource_template=format_resource_template,
                    format_info_resource_template=format_info_resource_template,
                    legendurls=legendurls
                    )


def format_resource_template(layer, template, service):
    if '{Format}' in template:
        template = template.replace('{Format}', layer.format)

    if '{Layer}' in template:
        template = template.replace('{Layer}', layer.name)

    return service.url + template


def format_info_resource_template(layer, template, info_format, service):
    if '{InfoFormat}' in template:
        template = template.replace('{InfoFormat}', info_format)

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
        self._layer = layers[list(layers.keys())[0]]

    def __getattr__(self, name):
        return getattr(self._layer, name)

    def __contains__(self, gridname):
        return gridname in self.layers

    def __getitem__(self, gridname):
        return self.layers[gridname]


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
            scale_denom = round(res / (0.28 / 1000) * meter_per_unit(self.grid.srs), 10)
            yield bunch(
                identifier=level,
                topleft=topleft,
                grid_size=grid_size,
                scale_denom=f'{scale_denom}'.strip('0').strip('.'),
                tile_size=self.grid.tile_size,
            )
