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
Service handler (WMS, TMS, etc.).
"""
from mapproxy.exception import RequestError

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

