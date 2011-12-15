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

from functools import partial

from mapproxy.request.wmts import wmts_request, make_wmts_rest_request_parser
from mapproxy.service.base import Server
from mapproxy.response import Response
from mapproxy.exception import RequestError

from mapproxy.template import template_loader, bunch
env = {'bunch': bunch}
get_template = template_loader(__file__, 'templates', namespace=env)

import logging
log = logging.getLogger(__name__)

class WMTSServer(Server):
    service = 'wmts'
    
    def __init__(self, layers, md, request_parser=None):
        Server.__init__(self)
        self.request_parser = request_parser or wmts_request
        self.md = md
        self.max_tile_age = None # TODO
        self.layers, self.matrix_sets = self._matrix_sets(layers)
        self.capabilities_class = Capabilities
    
    def _matrix_sets(self, layers):
        sets = {}
        layers_grids = {}
        for layer in layers.values():
            grid = layer.grid
            if grid.name not in sets:
                try:
                    sets[grid.name] = TileMatrixSet(grid)
                except AssertionError:
                    continue # TODO
            layers_grids.setdefault(layer.name, {})[grid.name] = layer
        wmts_layers = {}
        for layer_name, layers in layers_grids.items():
            wmts_layers[layer_name] = WMTSTileLayer(layers)
        return wmts_layers, sets.values()
        
    def capabilities(self, request):
        service = self._service_md(request)
        result = self.capabilities_class(service, self.layers.values(), self.matrix_sets).render(request)
        return Response(result, mimetype='application/xml')
    
    def tile(self, request):
        self.check_request(request)
        tile_layer = self.layers[request.layer][request.tilematrixset]
        if not request.format:
            request.format = tile_layer.format

        tile = tile_layer.render(request)
        resp = Response(tile.as_buffer(), content_type='image/' + request.format)
        resp.cache_headers(tile.timestamp, etag_data=(tile.timestamp, tile.size),
                           max_age=self.max_tile_age)
        resp.make_conditional(request.http)
        return resp
    
    def check_request(self, request):
        request.make_tile_request()
        if request.layer not in self.layers:
            raise RequestError('unknown layer: ' + str(request.layer),
                code='InvalidParameterValue', request=request)
        if request.tilematrixset not in self.layers[request.layer]:
            raise RequestError('unknown tilematrixset: ' + str(request.tilematrixset),
                code='InvalidParameterValue', request=request)

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
    default_template = '/{{Layer}}/{{TileMatrixSet}}/{{TileMatrix}}/{{TileCol}}/{{TileRow}}.{{Format}}'
    
    def __init__(self, layers, md, max_tile_age=None, template=None):
        WMTSServer.__init__(self, layers, md)
        self.max_tile_age = max_tile_age
        self.template = template or self.default_template
        self.request_parser = make_wmts_rest_request_parser(self.template)
        self.capabilities_class = partial(RestfulCapabilities, template=self.template)
    

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
    def __init__(self, server_md, layers, matrix_sets, template):
        Capabilities.__init__(self, server_md, layers, matrix_sets)
        self.template = template
    
    def template_context(self):
        return dict(service=bunch(default='', **self.service),
                    restful=True,
                    layers=self.layers,
                    tile_matrix_sets=self.matrix_sets,
                    resource_template=self.template,
                    format_resource_template=format_resource_template,
                    )

def format_resource_template(layer, template, service):
    if '{{Format}}' in template:
        template = template.replace('{{Format}}', layer.format)
    
    return service.url + template

class WMTSTileLayer(object):
    """
    Wrap multiple TileLayers for the same cache but with different grids.
    """
    def __init__(self, layers):
        self.grids = [lyr.grid for lyr in layers.values()]
        self.layers = layers
        self._layer = layers[layers.keys()[0]]
    
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
    
    def __iter__(self):
        for level, res in self.grid.resolutions.iteritems():
            origin = self.grid.origin_tile(level, 'ul')
            bbox = self.grid.tile_bbox(origin)
            grid_size = self.grid.grid_sizes[level]
            scale_denom = res / (0.28 / 1000) * meter_per_unit(self.grid.srs)
            yield bunch(
                identifier=level,
                bbox=bbox,
                grid_size=grid_size,
                scale_denom=scale_denom,
                tile_size=self.grid.tile_size,
            )

if __name__ == '__main__':
    print TileMatrixSet(tile_grid(900913)).tile_matrixes()
    print TileMatrixSet(tile_grid(4326, origin='ul')).tile_matrixes()