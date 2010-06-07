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

"""
Layer classes (direct, cached, etc.).

.. classtree:: mapproxy.core.layer._WMSLayer
.. classtree:: mapproxy.core.layer.MetaDataMixin

"""
from mapproxy.core.srs import SRS, TransformationError
from mapproxy.core.exceptions import RequestError
from mapproxy.core.client import HTTPClientError
from mapproxy.core.cache import TileCacheError, TooManyTilesError, BlankImage, NoTiles
from mapproxy.core.layer import Layer, LayerMetaData
from mapproxy.core.image import message_image, attribution_image

from mapproxy.core.cache import MapQuery, InfoQuery

import logging
log = logging.getLogger(__name__)

class FeatureInfoSource(object):
    def __init__(self, fi_sources):
        self.fi_sources = fi_sources
    def info(self, request):
        for fi_source in self.fi_sources:
            try:
                yield fi_source.get_info(request)
            except HTTPClientError:
                raise RequestError('unable to retrieve feature info')


class WMSLayer(object):
    
    def __init__(self, md, map_layers, info_layers=[]):
        self.md = LayerMetaData(md)
        self.map_layers = map_layers
        self.info_layers = info_layers
        self.extend = map_layers[0].extend #TODO
        self.queryable = True if info_layers else False
        self.transparent = any(map_lyr.transparent for map_lyr in self.map_layers)
        
        
    def render(self, request):
        p = request.params
        query = MapQuery(p.bbox, p.size, SRS(p.srs))
        for layer in self.map_layers:
            yield self._render_layer(layer, query, request)
    
    def _render_layer(self, layer, query, request):
        try:
            return layer.get_map(query)
        except TooManyTilesError:
            raise RequestError('Request too large or invalid BBOX.', request=request)
        except TransformationError:
            raise RequestError('Could not transform BBOX: Invalid result.',
                request=request)
        except TileCacheError, e:
            log.error(e)
            raise RequestError(e.args[0], request=request)
        except BlankImage:
            return None
    
    def info(self, request):
        p = request.params
        query = InfoQuery(p.bbox, p.size, SRS(p.srs), p.pos,
            p['info_format'])
        
        for lyr in self.info_layers:
            yield lyr.get_info(query)
        
class _WMSLayer(Layer):
    """
    Base class for all renderable layers.
    """
    def __init__(self, md, **kw):
        Layer.__init__(self, **kw)
        if md is None:
            md = {}
        self.md = LayerMetaData(md)
    def info(self, request):
        raise RequestError('layer %s is not queryable' % self.md.name, request=request)    
    def has_info(self):
        return False
    def caches(self, _request):
        return []
    

class VLayer(_WMSLayer):
    """
    A layer with multiple sources.
    """
    def __init__(self, md, sources):
        """
        :param md: the layer metadata
        :param sources: a list with layers
        :type sources: [`_WMSLayer`]
        """
        _WMSLayer.__init__(self, md, transparent=sources[0].transparent)
        self.sources = sources
    
    def _bbox(self):
        return self.sources[0].bbox
    
    def _srs(self):
        return self.sources[0].srs
    
    def render(self, request):
        for source in self.sources:
            img = None
            try:
                img = source.render(request)
            except BlankImage:
                pass
            if img is not None:
                yield img
    
    def caches(self, request):
        result = []
        for source in self.sources:
            result.extend(source.caches(request))
        return result
    
    def has_info(self):
        return any(source.has_info() for source in self.sources)
        
    def info(self, request):
        for source in self.sources:
            info = source.info(request)
            if info is None or isinstance(info, basestring):
                yield info
            else:
                for i in info:
                    yield i
    
    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.md, self.sources)


class DebugLayer(_WMSLayer):
    """
    A transparent layer with debug information.
    """
    def __init__(self, md=None):
        _WMSLayer.__init__(self, md)
        if md is None:
            md = {'name': '__debug__', 'title': 'Debug Layer'}
    
    def info(self, request):
        return None
    
    def render(self, request):
        bbox = request.params.bbox
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        res_x = w/request.params.size[0]
        res_y = h/request.params.size[1]
        debug_info = "bbox: %r\nres: %.8f(%.8f)" % (bbox, res_x, res_y)
        return message_image(debug_info, size=request.params.size, transparent=True)

class AttributionLayer(_WMSLayer):
    """
    A layer with an attribution line (e.g. copyright, etc).
    """
    def __init__(self, attribution, inverse=False):
        """
        :param attribution: the attribution message to add to the rendered output
        """
        _WMSLayer.__init__(self, {})
        self.attribution = attribution
        self.inverse = inverse
    
    def info(self, request):
        return None
    
    def render(self, request):
        if request.params.size == (256, 256):
            return None
        return attribution_image(self.attribution, size=request.params.size,
                                 transparent=True, inverse=self.inverse)

class DirectLayer(_WMSLayer):
    """
    A layer that passes the request to a wms.
    """
    def __init__(self, wms, queryable=False):
        _WMSLayer.__init__(self, {})
        self.wms = wms
        self.queryable = queryable
    
    def _bbox(self):
        return None
    
    def _srs(self):
        srs = self.wms.request_template.params.srs
        if srs is not None:
            srs = SRS(srs)
        return srs
    
    def render(self, request):
        try:
            return self.wms.get_map(request)
        except HTTPClientError, ex:
            log.warn('unable to get map for direct layer: %r', ex)
            raise RequestError('unable to get map for layers: %s' % 
                               ','.join(request.params.layers), request=request)
    
    def has_info(self):
        return self.queryable
        
    def info(self, request):
        return self.wms.get_info(request)

class WMSCacheLayer(_WMSLayer):
    """
    This is a layer that caches the data.
    """
    def __init__(self, cache, fi_source=None):
        _WMSLayer.__init__(self, {}, transparent=cache.transparent)
        self.cache = cache
        self.fi_source = fi_source
    
    def _bbox(self):
        return self.cache.extend.bbox_for(self.srs)
    
    def _srs(self):
        return self.cache.extend._srs
    
    def has_info(self):
        return self.fi_source is not None
    
    def info(self, request):
        return self.fi_source.info(request)
    
    def caches(self, _request):
        return [self.cache]
    
    def render(self, map_request):
        """
        Render the request.
        
        :param map_request: the map request to render
        """
        params = map_request.params
        req_bbox = params.bbox
        size = params.size
        req_srs = SRS(params.srs)
        
        try:
            return self.cache.get_map(MapQuery(req_bbox, size, req_srs))
        except TooManyTilesError:
            raise RequestError('Request too large or invalid BBOX.', request=map_request)
        except TransformationError:
            raise RequestError('Could not transform BBOX: Invalid result.',
                request=map_request)
        except TileCacheError, e:
            log.error(e)
            raise RequestError(e.args[0], request=map_request)
        except BlankImage:
            return None
    

