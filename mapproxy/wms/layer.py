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

.. classtree:: mapproxy.core.layer.WMSLayer
.. classtree:: mapproxy.core.layer.MetaDataMixin

"""
from mapproxy.core.srs import SRS, TransformationError
from mapproxy.core.exceptions import RequestError
from mapproxy.core.client import HTTPClientError
from mapproxy.core.cache import TileCacheError, TooManyTilesError
from mapproxy.core.layer import Layer, LayerMetaData
from mapproxy.core.image import message_image, attribution_image

import logging
log = logging.getLogger(__name__)

class FeatureInfoSource(object):
    def __init__(self, fi_sources):
        self.fi_sources = fi_sources
    def info(self, request):
        for fi_source in self.fi_sources:
            try:
                yield fi_source.get_info(request)
            except HTTPClientError, ex:
                raise RequestError('unable to retrieve feature info')

class WMSLayer(Layer):
    """
    Base class for all renderable layers.
    """
    def __init__(self, md):
        Layer.__init__(self)
        if md is None:
            md = {}
        self.md = LayerMetaData(md)
    def info(self, request):
        raise RequestError('layer %s is not queryable' % self.md.name, request=request)    
    def has_info(self):
        return False
    def caches(self, _request):
        return []
    

class VLayer(WMSLayer):
    """
    A layer with multiple sources.
    """
    def __init__(self, md, sources):
        """
        :param md: the layer metadata
        :param sources: a list with layers
        :type sources: [`WMSLayer`]
        """
        WMSLayer.__init__(self, md)
        self.sources = sources
    
    def _bbox(self):
        return self.sources[0].bbox
    
    def _srs(self):
        return self.sources[0].srs
    
    def render(self, request):
        for source in self.sources:
            yield source.render(request)
    
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


class DebugLayer(WMSLayer):
    """
    A transparent layer with debug information.
    """
    def __init__(self, md=None):
        WMSLayer.__init__(self, md)
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

class AttributionLayer(WMSLayer):
    """
    A layer with an attribution line (e.g. copyright, etc).
    """
    def __init__(self, attribution, inverse=False):
        """
        :param attribution: the attribution message to add to the rendered output
        """
        WMSLayer.__init__(self, {})
        self.attribution = attribution
        self.inverse = inverse
    
    def info(self, request):
        return None
    
    def render(self, request):
        if request.params.size == (256, 256):
            return None
        return attribution_image(self.attribution, size=request.params.size,
                                 transparent=True, inverse=self.inverse)

class DirectLayer(WMSLayer):
    """
    A layer that passes the request to a wms.
    """
    def __init__(self, wms, queryable=False):
        WMSLayer.__init__(self, {})
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

class WMSCacheLayer(WMSLayer):
    """
    This is a layer that caches the data.
    """
    def __init__(self, cache, fi_source=None):
        WMSLayer.__init__(self, {})
        self.cache = cache
        self.fi_source = fi_source
    
    def _bbox(self):
        return self.cache.grid.bbox
    
    def _srs(self):
        return self.cache.grid.srs
    
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
            return self.cache.image(req_bbox, req_srs, size)
        except TooManyTilesError:
            raise RequestError('Request too large or invalid BBOX.', request=map_request)
        except TransformationError:
            raise RequestError('Could not transform BBOX: Invalid result.',
                request=map_request)
        except TileCacheError, e:
            log.error(e)
            raise RequestError(e.message, request=map_request)
    

def srs_dispatcher(layers, srs):
    latlong = SRS(srs).is_latlong
    for layer in layers:
        if layer.srs.is_latlong == latlong:
            return layer
    return layers[0]

class MultiLayer(WMSLayer):
    """
    This layer dispatches requests to other layers. 
    """
    def __init__(self, layers, md, dispatcher=None):
        WMSLayer.__init__(self, md)
        self.layers = layers
        if dispatcher is None:
            dispatcher = srs_dispatcher
        self.dispatcher = dispatcher
    
    def _bbox(self):
        return self.layers[0].bbox
    
    def _srs(self):
        return self.layers[0].srs
    
    def render(self, map_request):
        srs = map_request.params.srs
        layer = self.dispatcher(self.layers, srs)
        return layer.render(map_request)
    
    def caches(self, request):
        layer = self.dispatcher(self.layers, request.params.srs)
        return layer.caches(request)
    
    def has_info(self):
        return self.layers[0].has_info()
    
    def info(self, request):
        srs = request.params.srs
        layer = self.dispatcher(self.layers, srs)
        return layer.info(request)