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

import re

from jinja2 import Environment, PackageLoader
from mapproxy.core.exceptions import (
    RequestError,
    XMLExceptionHandler,
    PlainExceptionHandler, )

env = Environment(loader=PackageLoader('mapproxy.tms', 'templates'),
                  trim_blocks=True)

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
    
    def __init__(self, request):
        self.request = request
        self._init_request()
    
    def _init_request(self):
        """
        Initialize tile request. Sets ``tile`` and ``layer``.
        :raise RequestError: if the format is not ``/layer/z/x/y.format``
        """
        match = self.tile_req_re.search(self.request.path)
        if not match or match.group('begin') != self.req_prefix:
            raise RequestError('invalid request (%s)' % (self.request.path), request=self)
        
        self.layer = match.group('layer')
        if match.group('layer_spec') is not None:
            self.layer += '_' + match.group('layer_spec')
        self.tile = tuple([int(match.group(v)) for v in ['x', 'y', 'z']])
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
        ^.*/1\.0\.0/
        (?P<layer>[^/]+)?
        (/(?P<layer_spec>[^/]+))?
        $''', re.VERBOSE)
    use_profiles = True
    def __init__(self, request):
        self.request = request
        cap_match = self.capabilities_re.match(request.path)
        if cap_match:
            if cap_match.group('layer') is not None:
                self.layer = cap_match.group('layer')
                if cap_match.group('layer_spec') is not None:
                    self.layer += '_' + cap_match.group('layer_spec')
            self.request_handler_name = 'tms_capabilities'
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
    mimetype = 'text/xml'
    status_code = 404
    env = env
    
    def render(self, request_error):
        if request_error.internal:
            self.status_code = 500
        return XMLExceptionHandler.render(self, request_error)