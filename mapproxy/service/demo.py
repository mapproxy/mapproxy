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
Demo service handler
"""
import os
import mimetypes
from urllib2 import urlopen
from collections import defaultdict

from mapproxy.service.base import Server
from mapproxy.response import Response
from mapproxy.config import base_config

from mapproxy.template import template_loader, bunch
env = {'bunch': bunch}
get_template = template_loader(__file__, 'templates', namespace=env)

import logging
log = logging.getLogger(__name__)

class DemoServer(Server):
    names = ('demo',)
    def __init__(self, layers, md, request_parser=None, tile_layers=None,
                 srs=None, image_formats=None):
        Server.__init__(self)
        self.layers = layers
        self.tile_layers = tile_layers or {}
        self.md = md
        self.image_formats = image_formats or base_config().wms.image_formats
        filter_image_format = []
        for format in self.image_formats:
            if 'image/jpeg' == format or 'image/png' == format:
                filter_image_format.append(format)
        self.image_formats = filter_image_format
        self.srs = srs or base_config().wms.srs

    def handle(self, req):
        if req.path.startswith('/demo/static/'):
            filename = os.path.realpath(req.path).lstrip('/')
            static_file = os.path.join(os.path.dirname(__file__), 'templates', filename)
            type, encoding = mimetypes.guess_type(filename)
            return Response(open(static_file, 'rb'), content_type=type)
        
        # we don't authorize the static files (css, js)
        # since they are not confidetial
        if not self.authorized_demo(req.environ):
            return Response('forbidden', content_type='text/plain', status=403)
        
        if 'wms_layer' in req.args:
            demo = self._render_wms_template('demo/wms_demo.html', req)
        elif 'tms_layer' in req.args:
            demo = self._render_tms_template('demo/tms_demo.html', req)
        elif 'wms_capabilities' in req.args:
            url = '%s/service?REQUEST=GetCapabilities'%(req.script_url)
            capabilities = urlopen(url)
            demo = self._render_capabilities_template('demo/capabilities_demo.html', capabilities, 'WMS', url)
        elif 'wmsc_capabilities' in req.args:
            url = '%s/service?REQUEST=GetCapabilities&tiled=true'%(req.script_url)
            capabilities = urlopen(url)
            demo = self._render_capabilities_template('demo/capabilities_demo.html', capabilities, 'WMS-C', url)
        elif 'tms_capabilities' in req.args:
            if 'layer' in req.args and 'srs' in req.args:
                url = '%s/tms/1.0.0/%s_%s'%(req.script_url, req.args['layer'], req.args['srs'])
                capabilities = urlopen(url)
            else:
                url = '%s/tms/1.0.0/'%(req.script_url)
                capabilities = urlopen(url)
            demo = self._render_capabilities_template('demo/capabilities_demo.html', capabilities, 'TMS', url)
        elif req.path == '/demo/':
            demo = self._render_template('demo/demo.html')
        else:
            resp = Response('', status=301)
            resp.headers['Location'] = req.script_url.rstrip('/') + '/demo/'
            return resp
        return Response(demo, content_type='text/html')

    def _render_template(self, template):
        template = get_template(template, default_inherit="demo/static.html")
        tms_tile_layers = defaultdict(list)
        for layer in self.tile_layers:
            name = self.tile_layers[layer].md.get('name')
            tms_tile_layers[name].append(self.tile_layers[layer])

        return template.substitute(layers = self.layers,
                                   formats = self.image_formats,
                                   tms_layers = tms_tile_layers)

    def _render_wms_template(self, template, req):
        template = get_template(template, default_inherit="demo/static.html")
        return template.substitute(layer = self.layers[req.args['wms_layer']],
                                   format = req.args['format'])

    def _render_tms_template(self, template, req):
        template = get_template(template, default_inherit="demo/static.html")
        tile_layer = self.tile_layers['_'.join([req.args['tms_layer'], req.args['srs'].replace(':','')])]
        resolutions = tile_layer.grid.tile_sets
        res = []
        for level, resolution in resolutions:
            res.append(resolution)

        if tile_layer.grid.srs.is_latlong:
            units = 'degree'
        else:
            units = 'm'

        if tile_layer.grid.profile == 'local':
            add_res_to_options = True
        else:
            add_res_to_options = False
        return template.substitute(layer = tile_layer,
                                   srs = req.args['srs'],
                                   format = req.args['format'],
                                   resolutions = res,
                                   units = units,
                                   add_res_to_options = add_res_to_options,
                                   all_tile_layers = self.tile_layers)

    def _render_capabilities_template(self, template, xmlfile, service, url):
        template = get_template(template, default_inherit="demo/static.html")
        return template.substitute(capabilities = xmlfile,
                                   service = service,
                                   url = url)

    def authorized_demo(self, environ):
        if 'mapproxy.authorize' in environ:
            result = environ['mapproxy.authorize']('demo', [])
            if result['authorized'] == 'full':
                return True
            return False
        return True
