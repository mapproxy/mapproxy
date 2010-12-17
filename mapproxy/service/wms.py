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
from mapproxy.request.wms import wms_request, WMS111LegendGraphicRequest
from mapproxy.srs import merge_bbox, SRS, TransformationError
from mapproxy.service.base import Server
from mapproxy.response import Response
from mapproxy.exception import RequestError
from mapproxy.config import base_config
from mapproxy.image import concat_legends
from mapproxy.image.message import attribution_image

from mapproxy.layer import BlankImage, MapQuery, InfoQuery, LegendQuery, MapError, MapBBOXError, merge_layer_extents
from mapproxy.util.ext.odict import odict

from mapproxy.template import template_loader, bunch
from mapproxy.service import template_helper

get_template = template_loader(__file__, 'templates', namespace=template_helper.__dict__)

import logging
log = logging.getLogger(__name__)

class WMSServer(Server):
    names = ('service',)
    request_methods = ('map', 'capabilities', 'featureinfo', 'legendgraphic')
    
    def __init__(self, root_layer, md, layer_merger=None, request_parser=None, tile_layers=None,
        attribution=None, srs=None, image_formats=None, strict=False):
        Server.__init__(self)
        self.request_parser = request_parser or partial(wms_request, strict=strict)
        self.root_layer = root_layer
        self.layers = root_layer.child_layers()
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
        
        p = map_request.params
        query = MapQuery(p.bbox, p.size, SRS(p.srs), p.format)
        
        render_layers = []
        for layer_name in map_request.params.layers:
            layer = self.layers[layer_name]
            # only add if layer reders the query
            if layer.renders_query(query):
                # if layer is not transparent but will be rendered,
                # remove already added (hidden) layers 
                if not layer.transparent:
                    render_layers = []
                render_layers.append(layer)
        
        for layer in render_layers:
            merger.add(layer.render(map_request, query=query))
            
        params = map_request.params
        if self.attribution:
            merger.add(attribution_image(self.attribution['text'], params.size))
        result = merger.merge(params.format, params.size,
                              bgcolor=params.bgcolor,
                              transparent=params.transparent)
        return Response(result.as_buffer(format=params.format),
                        content_type=params.format_mime_type)
    def capabilities(self, map_request):
        # TODO: debug layer
        # if '__debug__' in map_request.params:
        #     layers = self.layers.values()
        # else:
        #     layers = [layer for name, layer in self.layers.iteritems()
        #               if name != '__debug__']
        
        if map_request.params.get('tiled', 'false').lower() == 'true':
            tile_layers = self.tile_layers.values()
        else:
            tile_layers = []
            
        service = self._service_md(map_request)
        result = Capabilities(service, self.root_layer, tile_layers, self.image_formats, self.srs).render(map_request)
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

    def check_legend_request(self, request):
        if request.params.layer not in self.layers:
            raise RequestError('unknown layer: ' + request.params.layer,
                               code='LayerNotDefined', request=request)
    
    #TODO: If layer not in self.layers raise RequestError
    def legendgraphic(self, request):
        legends = []
        self.check_legend_request(request)
        layer = request.params.layer
        if not self.layers[layer].has_legend:
            raise RequestError('layer %s has no legend graphic' % layer, request=request)
        legend = self.layers[layer].legend(request)
        
        [legends.append(i) for i in legend if i is not None]
        result = concat_legends(legends)
        if 'format' in request.params:
            mimetype = request.params.format_mime_type
        else:
            mimetype = 'image/png'
        return Response(result.as_buffer(format=request.params.format).read(), mimetype=mimetype)
    
    def _service_md(self, map_request):
        md = dict(self.md)
        md['url'] = map_request.url
        md['has_legend'] = self.root_layer.has_legend
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
        doc = template.substitute(service=bunch(default='', **self.service),
                                   layers=self.layers,
                                   formats=self.image_formats,
                                   srs=self.srs,
                                   tile_layers=self.tile_layers)
        # strip blank lines
        doc = '\n'.join(l for l in doc.split('\n') if l.rstrip())
        return doc

class WMSLayerBase(object):
    """
    Base class for WMS layer (layer groups and leaf layers).
    """
    
    "True if layer is an actual layer (not a group only)"
    is_active = True
    
    "list of sublayers"
    layers = []
    
    "metadata dictionary with tile, name, etc."
    md = {}
    
    "True if .info() is supported"
    queryable = False

    transparent = False

    "True is .legend() is supported"
    has_legend = False
    legend_url = None
    legend_size = None
    
    "resolution range (i.e. ScaleHint) of the layer"
    res_range = None
    "MapExtend of the layer"
    extent = None
    
    def render(self, request, query=None):
        raise NotImplementedError()
    
    def legend(self, query):
        raise NotImplementedError()
    
    def info(self, query):
        raise NotImplementedError()
    
class WMSLayer(WMSLayerBase):
    is_active = True
    layers = []
    def __init__(self, md, map_layers, info_layers=[], legend_layers=[], res_range=None):
        self.md = md
        self.map_layers = map_layers
        self.info_layers = info_layers
        self.legend_layers = legend_layers
        self.extent = merge_layer_extents(map_layers)
        if res_range is None:
            res_range = map_layers[0].res_range #TODO
        self.res_range = res_range
        self.queryable = True if info_layers else False
        self.transparent = any(map_lyr.transparent for map_lyr in self.map_layers)
        self.has_legend = True if legend_layers else False
    
    def renders_query(self, query):
        if self.res_range and not self.res_range.contains(query.bbox, query.size, query.srs):
            return False
        return True
    
    def render(self, request, query=None):
        if query is None:
            p = request.params
            query = MapQuery(p.bbox, p.size, SRS(p.srs), p.format)

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
    
    def legend(self, request):
        p = request.params
        query = LegendQuery(p.format, p.scale)
        
        for lyr in self.legend_layers:
            yield lyr.get_legend(query)
    
    @property
    def legend_size(self):
        width = 0
        height = 0
        for layer in self.legend_layers:
            width = max(layer.size[0], width)
            height += layer.size[1]
        return (width, height)
    
    @property
    def legend_url(self):
        if self.has_legend:
            req = WMS111LegendGraphicRequest(url='?',
                param=dict(format='image/png', layer=self.md['name'], sld_version='1.1.0'))
            return req.complete_url
        else:
            return None

class WMSGroupLayer(WMSLayerBase):
    def __init__(self, md, this, layers):
        self.this = this
        self.md = md
        self.is_active = True if this is not None else False
        self.layers = layers
        self.transparent = True if this and this.transparent or any(l.transparent for l in layers) else False
        self.has_legend = True if this and this.has_legend or any(l.has_legend for l in layers) else False
        self.queryable = True if this and this.queryable or any(l.queryable for l in layers) else False
        self.extent = merge_layer_extents(layers + ([self.this] if self.this else []))
        self.res_range = layers[0].res_range #TODO
    
    @property
    def legend_size(self):
        return self.this.legend_size()

    @property
    def legend_url(self):
        return self.this.legend_url()
    
    def renders_query(self, query):
        if self.res_range and not self.res_range.contains(query.bbox, query.size, query.srs):
            return False
        return True
    
    def render(self, request, query=None):
        if self.this:
            yield self.this.render(request, query)
        else:
            for layer in self.layers:
                yield layer.render(request, query)
    
    def info(self, request):
        if self.this:
            yield self.this.info(request)
        else:
            for layer in self.layers:
                yield layer.info(request)
    
    def child_layers(self):
        layers = odict()
        if self.md.get('name'):
            layers[self.md['name']] = self
        for lyr in self.layers:
            if hasattr(lyr, 'child_layers'):
                layers.update(lyr.child_layers())
            elif lyr.md.get('name'):
                layers[lyr.md['name']] = lyr
        return layers