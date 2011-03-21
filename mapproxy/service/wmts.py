# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

"""
WMS service handler
"""
from itertools import chain
from mapproxy.request.wmts import wmts_request
from mapproxy.srs import merge_bbox, SRS, TransformationError
from mapproxy.service.base import Server
from mapproxy.response import Response
from mapproxy.exception import RequestError
from mapproxy.config import base_config
from mapproxy.image.message import attribution_image

from mapproxy.layer import BlankImage, MapQuery, InfoQuery, MapError, MapBBOXError
from mapproxy.source import SourceError

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
        self.layers = layers
        self.md = md
        self.matrix_sets = self._matrix_sets()
    
    def _matrix_sets(self):
        sets = {}
        for layer in self.layers.values():
            grid = layer.grid
            if grid.name not in sets:
                try:
                    sets[grid.name] = TileMatrixSet(grid)
                except AssertionError:
                    pass # TODO
        return sets.values()
        
    def capabilities(self, request):
        service = self._service_md(request)
        result = Capabilities(service, self.layers.values(), self.matrix_sets).render(request)
        return Response(result, mimetype='application/xml')
    
    def tile(self, request):
        tile_layer = self.layers[request.params.layer]
        request.format = request.params.format # TODO
        request.tile = tuple(map(int, request.params.coord)) # TODO
        request.origin = 'nw'
        tile = tile_layer.render(request)
        resp = Response(tile.as_buffer(), content_type='image/' + request.format)
        
        return resp
    
    def check_request(self, request):
        query_layers = request.params.query_layers if hasattr(request, 'query_layers') else []
        for layer in chain(request.params.layers, query_layers):
            if layer not in self.layers:
                raise RequestError('unknown layer: ' + str(layer), code='LayerNotDefined',
                                   request=request)
    
    def _service_md(self, tile_request):
        md = dict(self.md)
        md['url'] = tile_request.url
        return md

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
    
    def _render_template(self, template):
        template = get_template(template)
        doc = template.substitute(service=bunch(default='', **self.service),
                                   layers=self.layers,
                                   tile_matrix_sets=self.matrix_sets)
        # strip blank lines
        doc = '\n'.join(l for l in doc.split('\n') if l.rstrip())
        return doc

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
        origin = self.grid.origin_tile(0, 'ul')
    
    def __iter__(self):
        for level, res in enumerate(self.grid.resolutions):
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