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
from mapproxy.core.cache import TileCacheError, TooManyTilesError, BlankImage

from mapproxy.core.cache import MapQuery, InfoQuery

import logging
log = logging.getLogger(__name__)

class WMSLayer(object):
    
    def __init__(self, md, map_layers, info_layers=[]):
        self.md = md
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
    

