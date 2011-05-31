# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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
Demo service handler
"""
import os
import mimetypes
from urllib2 import urlopen
from collections import defaultdict

from mapproxy.exception import RequestError
from mapproxy.service.base import Server
from mapproxy.response import Response

from mapproxy.template import template_loader, bunch
env = {'bunch': bunch}
get_template = template_loader(__file__, 'templates', namespace=env)


class DemoServer(Server):
    names = ('demo',)
    def __init__(self, layers, md, request_parser=None, tile_layers=None,
                 srs=None, image_formats=None):
        Server.__init__(self)
        self.layers = layers
        self.tile_layers = tile_layers or {}
        self.md = md
        self.image_formats = image_formats
        filter_image_format = []
        for format in self.image_formats:
            if 'image/jpeg' == format or 'image/png' == format:
                filter_image_format.append(format)
        self.image_formats = filter_image_format
        self.srs = srs

    def handle(self, req):
        if req.path.startswith('/demo/static/'):
            filename = req.path.lstrip('/')
            template_dir = os.path.join(os.path.dirname(__file__), 'templates')
            static_file = os.path.abspath(os.path.join(template_dir, filename))
            if (not static_file.startswith(template_dir) or
                not os.path.isfile(static_file)):
                return Response('file not found', content_type='text/plain', status=404)
            type, encoding = mimetypes.guess_type(filename)
            return Response(open(static_file, 'rb'), content_type=type)
        
        # we don't authorize the static files (css, js)
        # since they are not confidential
        try:
            authorized = self.authorized_demo(req.environ)
        except RequestError, ex:
            return ex.render()
        if not authorized:
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
            result = environ['mapproxy.authorize']('demo', [], environ=environ)
            if result['authorized'] == 'unauthenticated':
                raise RequestError('unauthorized', status=401)
            if result['authorized'] == 'full':
                return True
            return False
        return True
