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
Service exception handling (WMS exceptions, XML, in_image, etc.).
"""
import cgi
from mapproxy.response import Response

class RequestError(Exception):
    """
    Exception for all request related errors.
    
    :ivar internal: True if the error was an internal error, ie. the request itself
                    was valid (e.g. the source server is unreachable
    """
    def __init__(self, message, code=None, request=None, internal=False, status=None):
        Exception.__init__(self, message)
        self.msg = message
        self.code = code
        self.request = request
        self.internal = internal
        self.status = status
    
    def render(self):
        """
        Return a response with the rendered exception.
        The rendering is delegated to the ``exception_handler`` that issued
        the ``RequestError``.
        
        :rtype: `Response`
        """
        if self.request is not None:
            handler = self.request.exception_handler
            return handler.render(self)
        elif self.status is not None:
            return Response(self.msg, status=self.status)
        else:
            return Response('internal error: %s' % self.msg, status=500)
    
    def __str__(self):
        return 'RequestError("%s", code=%r, request=%r)' % (self.msg, self.code,
                                                            self.request)


class ExceptionHandler(object):
    """
    Base class for exception handler.
    """
    def render(self, request_error):
        """
        Return a response with the rendered exception.
        
        :param request_error: the exception to render
        :type request_error: `RequestError`
        :rtype: `Response`
        """
        raise NotImplementedError()

def _not_implemented(*args, **kw):
    raise NotImplementedError()

class XMLExceptionHandler(ExceptionHandler):
    """
    Mixin class for tempita-based template renderer.
    """
    template_file = None
    """The filename of the tempita xml template"""
    
    content_type = None
    """
    The mime type of the exception response (use this or mimetype).
    The content_type is sent as defined here.
    """
    
    status_code = 200
    """
    The HTTP status code.
    """
    
    status_codes = {}
    """
    Mapping of exceptionCodes to status_codes. If not defined
    status_code is used.
    """
    
    mimetype = None
    """
    The mime type of the exception response. (use this or content_type).
    A character encoding might be added to the mimetype (like text/xml;charset=UTF-8) 
    """
    
    template_func = _not_implemented
    """
    Function that returns the named template.
    """
    
    def render(self, request_error):
        """
        Render the template of this exception handler. Passes the 
        ``request_error.msg`` and ``request_error.code`` to the template.
        
        :type request_error: `RequestError`
        """
        status_code = self.status_codes.get(request_error.code, self.status_code)
        # escape &<> in error message (e.g. URL params)
        msg = cgi.escape(request_error.msg)
        result = self.template.substitute(exception=msg,
                                          code=request_error.code)
        return Response(result, mimetype=self.mimetype, content_type=self.content_type,
                        status=status_code)
    
    @property
    def template(self):
        """
        The template for this ExceptionHandler.
        """
        return self.template_func(self.template_file)

class PlainExceptionHandler(ExceptionHandler):
    mimetype = 'text/plain'
    status_code = 404

    def render(self, request_error):
        if request_error.internal:
            self.status_code = 500
        return Response(request_error.msg, status=self.status_code,
                        mimetype=self.mimetype)
