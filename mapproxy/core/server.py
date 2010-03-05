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

