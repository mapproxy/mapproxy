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
Service handler (WMS, TMS, etc.).
"""
from mapproxy.core.exceptions import RequestError
from mapproxy.core.utils import replace_instancemethod
from mapproxy.core.response import Response
from mapproxy.core.app import ctx

class Server(object):
    names = tuple()
    request_parser = lambda x: None
    request_methods = ()
    
    def handle(self, req):
        try:
            parsed_req = self.parse_request(req)
            handler = getattr(self, parsed_req.request_handler_name)
            return handler(parsed_req)
        except RequestError, e:
            return e.render()
    
    def parse_request(self, req):
        return self.request_parser(req)

