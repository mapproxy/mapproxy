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

import re

from mapproxy.exception import (
    RequestError,
    XMLExceptionHandler,
    PlainExceptionHandler, )

import mapproxy.service
from mapproxy.template import template_loader
get_template = template_loader(mapproxy.service.__name__, 'templates')

class TileRequest(object):
    """
    Class for tile requests.
    """
    request_handler_name = 'map'
    tile_req_re = re.compile(r'''^(?P<begin>/[^/]+)/
            ((?P<version>1\.0\.0)/)?
            (?P<layer>[^/]+)/
            ((?P<layer_spec>[^/]+)/)?
            (?P<z>-?\d+)/
            (?P<x>-?\d+)/
            (?P<y>-?\d+)\.(?P<format>\w+)''', re.VERBOSE)
    use_profiles = False
    req_prefix = '/tiles'
    origin = None
    dimensions = {}

    def __init__(self, request):
        self.tile = None
        self.format = None
        self.http = request
        self._init_request()
        self.origin = self.http.args.get('origin')
        if self.origin not in ('sw', 'nw', None):
            self.origin = None

    def _init_request(self):
        """
        Initialize tile request. Sets ``tile`` and ``layer``.
        :raise RequestError: if the format is not ``/layer/z/x/y.format``
        """
        match = self.tile_req_re.search(self.http.path)
        if not match or match.group('begin') != self.req_prefix:
            raise RequestError('invalid request (%s)' % (self.http.path), request=self)

        self.layer = match.group('layer')
        self.dimensions = {}
        if match.group('layer_spec') is not None:
            self.dimensions['_layer_spec'] = match.group('layer_spec')
        if not self.tile:
            self.tile = tuple([int(match.group(v)) for v in ['x', 'y', 'z']])
        if not self.format:
            self.format = match.group('format')

    @property
    def exception_handler(self):
        return PlainExceptionHandler()


class TMSRequest(TileRequest):
    """
    Class for TMS 1.0.0 requests.
    """
    request_handler_name = 'map'
    req_prefix = '/tms'
    capabilities_re = re.compile(r'''
        ^.*/1\.0\.0/?
        (/(?P<layer>[^/]+))?
        (/(?P<layer_spec>[^/]+))?
        $''', re.VERBOSE)
    root_request_re = re.compile(r'/tms/?$')
    use_profiles = True
    origin = 'sw'

    def __init__(self, request):
        self.tile = None
        self.format = None
        self.http = request
        cap_match = self.capabilities_re.match(request.path)
        root_match = self.root_request_re.match(request.path)
        if cap_match:
            if cap_match.group('layer') is not None:
                self.layer = cap_match.group('layer')
                self.dimensions = {}
                if cap_match.group('layer_spec') is not None:
                    self.dimensions['_layer_spec'] = cap_match.group('layer_spec')
            self.request_handler_name = 'tms_capabilities'
        elif root_match:
            self.request_handler_name = 'tms_root_resource'
        else:
            self._init_request()

    @property
    def exception_handler(self):
        return TMSExceptionHandler()

def tile_request(req):
    if req.path.startswith('/tms'):
        return TMSRequest(req)
    else:
        return TileRequest(req)

class TMSExceptionHandler(XMLExceptionHandler):
    template_file = 'tms_exception.xml'
    template_func = get_template
    mimetype = 'text/xml'
    status_code = 404

    def render(self, request_error):
        if request_error.internal:
            self.status_code = 500
        return XMLExceptionHandler.render(self, request_error)