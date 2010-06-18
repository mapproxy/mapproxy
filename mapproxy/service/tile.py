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


from mapproxy.response import Response
from mapproxy.exception import RequestError
from mapproxy.service.base import Server
from mapproxy.request.tile import tile_request
from mapproxy.config import base_config
from mapproxy.wsgiapp import ctx

from mapproxy.template import template_loader, bunch
get_template = template_loader(__file__, 'templates')

import logging
log = logging.getLogger(__name__)

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
    request_methods = ('map', 'tms_capabilities')
    template_file = 'tms_capabilities.xml'
    layer_template_file = 'tms_tilemap_capabilities.xml'

    def __init__(self, layers, md):
        Server.__init__(self)
        self.layers = layers
        self.md = md
    
    def map(self, tile_request):
        """
        :return: the requested tile
        :rtype: Response
        """
        layer = self.layer(tile_request)
        tile = layer.render(tile_request, use_profiles=tile_request.use_profiles)
        resp = Response(tile.as_buffer(), content_type='image/' + tile_request.format)
        resp.cache_headers(tile.timestamp, etag_data=(tile.timestamp, tile.size),
                           max_age=base_config().tiles.expires_hours * 60 * 60)
        resp.make_conditional(ctx.env)
        return resp
    
    def _internal_layer(self, name):
        if name in self.layers:
            return self.layers[name]
        if name + '_EPSG900913' in self.layers:
            return self.layers[name + '_EPSG900913']
        if name + '_EPSG4326' in self.layers:
            return self.layers[name + '_EPSG4326']
        return None
    
    def layer(self, tile_request):
        internal_layer = self._internal_layer(tile_request.layer)
        if internal_layer is None:
            raise RequestError('unknown layer: ' + tile_request.layer, request=tile_request)
        return internal_layer
    
    def tms_capabilities(self, tms_request):
        """
        :return: the rendered tms capabilities
        :rtype: Response
        """
        service = self._service_md(tms_request)
        if hasattr(tms_request, 'layer'):
            layer = self.layer(tms_request)
            result = self._render_layer_template(layer, service)
        else:
            result = self._render_template(service)

        return Response(result, mimetype='text/xml')
    
    def _service_md(self, map_request):
        md = dict(self.md)
        md['url'] = map_request.request.base_url
        return md
    
    def _render_template(self, service):
        template = get_template(self.template_file)
        return template.substitute(service=bunch(default='', **service), layers=self.layers)
    
    def _render_layer_template(self, layer, service):
        template = get_template(self.layer_template_file)
        return template.substitute(service=bunch(default='', **service), layer=layer)
