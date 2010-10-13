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

"""
WMS service handler
"""
from itertools import chain
from functools import partial
from mapproxy.request.wms import wms_request
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

class WMSServer(Server):
    names = ('service',)
    request_methods = ('map', 'capabilities', 'featureinfo')
    
    def __init__(self, layers, md, layer_merger=None, request_parser=None, tile_layers=None,
        attribution=None, srs=None, image_formats=None, strict=False):
        Server.__init__(self)
        self.request_parser = request_parser or partial(wms_request, strict=strict)
        self.layers = layers
        self.tile_layers = tile_layers or {}
        self.strict = strict
        if layer_merger is None:
            from mapproxy.image import LayerMerger
            layer_merger = LayerMerger
        self.merger = layer_merger
        self.attribution = attribution
        self.md = md
        self.image_formats = image_formats or base_config().wms.image_formats
        self.srs = srs or base_config().wms.srs
                
    def map(self, map_request):
        merger = self.merger()
        self.check_request(map_request)
        
        render_layers = []
        for layer_name in map_request.params.layers:
            layer = self.layers[layer_name]
            if not layer.transparent:
                render_layers = []
            render_layers.append(layer)
        
        for layer in render_layers:
            merger.add(layer.render(map_request))
            
        params = map_request.params
        if self.attribution:
            merger.add(attribution_image(self.attribution['text'], params.size))
        result = merger.merge(params.format, params.size,
                              bgcolor=params.bgcolor,
                              transparent=params.transparent)
        return Response(result.as_buffer(format=params.format),
                        content_type=params.format_mime_type)
    def capabilities(self, map_request):
        if '__debug__' in map_request.params:
            layers = self.layers.values()
        else:
            layers = [layer for name, layer in self.layers.iteritems()
                      if name != '__debug__']
        
        if map_request.params.get('tiled', 'false').lower() == 'true':
            tile_layers = self.tile_layers.values()
        else:
            tile_layers = []
        service = self._service_md(map_request)
        result = Capabilities(service, layers, tile_layers, self.image_formats, self.srs).render(map_request)
        return Response(result, mimetype=map_request.mime_type)
    
    def featureinfo(self, request):
        infos = []
        self.check_request(request)
        for layer in request.params.query_layers:
            if not self.layers[layer].queryable:
                raise RequestError('layer %s is not queryable' % layer, request=request)
            info = self.layers[layer].info(request)
            if info is None:
                continue
            if isinstance(info, basestring):
                infos.append(info)
            else:
                [infos.append(i) for i in info if i is not None]
        if 'info_format' in request.params:
            mimetype = request.params.info_format
        else:
            mimetype = 'text/plain'
        return Response('\n'.join(infos), mimetype=mimetype)
    
    def check_request(self, request):
        query_layers = request.params.query_layers if hasattr(request, 'query_layers') else []
        for layer in chain(request.params.layers, query_layers):
            if layer not in self.layers:
                raise RequestError('unknown layer: ' + str(layer), code='LayerNotDefined',
                                   request=request)
    
    def _service_md(self, map_request):
        md = dict(self.md)
        md['url'] = map_request.url
        return md

class Capabilities(object):
    """
    Renders WMS capabilities documents.
    """
    def __init__(self, server_md, layers, tile_layers, image_formats, srs):
        self.service = server_md
        self.layers = layers
        self.tile_layers = tile_layers
        self.image_formats = image_formats
        self.srs = srs
    
    def render(self, _map_request):
        return self._render_template(_map_request.capabilities_template)
    
    def _render_template(self, template):
        template = get_template(template)
        server_bbox = self._create_server_bbox()
        return template.substitute(service=bunch(default='', **self.service),
                                   layers=self.layers,
                                   server_llbbox=server_bbox,
                                   formats=self.image_formats,
                                   srs=self.srs,
                                   tile_layers=self.tile_layers)
    
    def _create_server_bbox(self):
        bbox = self.layers[0].extent.llbbox
        for layer in self.layers[1:]:
            bbox = merge_bbox(bbox, layer.extent.llbbox)
        return bbox

def wms100format_filter(format):
    """
    >>> wms100format_filter('image/png')
    'PNG'
    >>> wms100format_filter('image/GeoTIFF')
    """
    _mime_class, sub_type = format.split('/')
    sub_type = sub_type.upper()
    if sub_type in ['PNG', 'TIFF', 'GIF', 'JPEG']:
        return sub_type
    else:
        return None

env['wms100format'] = wms100format_filter

class WMSLayer(object):
    
    def __init__(self, md, map_layers, info_layers=[]):
        self.md = md
        self.map_layers = map_layers
        self.info_layers = info_layers
        self.extent = map_layers[0].extent #TODO
        self.queryable = True if info_layers else False
        self.transparent = any(map_lyr.transparent for map_lyr in self.map_layers)
        
        
    def render(self, request):
        p = request.params
        query = MapQuery(p.bbox, p.size, SRS(p.srs), request.params.format)
        if request.params.get('tiled', 'false').lower() == 'true':
            query.tiled_only = True
        for layer in self.map_layers:
            yield self._render_layer(layer, query, request)
    
    def _render_layer(self, layer, query, request):
        try:
            return layer.get_map(query)
        except MapBBOXError:
            raise RequestError('Request too large or invalid BBOX.', request=request)
        except MapError, e:
            raise RequestError('Invalid request: %s' % e.args[0], request=request)
        except TransformationError:
            raise RequestError('Could not transform BBOX: Invalid result.',
                request=request)
        except BlankImage:
            return None
    
    def info(self, request):
        p = request.params
        query = InfoQuery(p.bbox, p.size, SRS(p.srs), p.pos,
            p['info_format'], format=request.params.format or None)
        
        for lyr in self.info_layers:
            yield lyr.get_info(query)
    
