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
Service exception handling (WMS exceptions, XML, in_image, etc.).
"""
from mapproxy.core.response import Response

class RequestError(Exception):
    """
    Exception for all request related errors.
    
    :ivar internal: True if the error was an internal error, ie. the request itself
                    was valid (e.g. the source server is unreachable
    """
    def __init__(self, message, code=None, request=None, internal=False):
        Exception.__init__(self)
        self.message = message
        self.code = code
        self.request = request
        self.internal = internal
    
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
        else:
            return Response('internal error: %s' % self.message, status=500)
    
    def __str__(self):
        return 'RequestError("%s", code=%r, request=%r)' % (self.message, self.code,
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


class XMLExceptionHandler(ExceptionHandler):
    """
    Mixin class for jinja-based template renderer.
    """
    template_file = None
    """The filename of the jinja xml template"""
    
    content_type = None
    """
    The mime type of the exception response (use this or mimetype).
    The content_type is sent as defined here.
    """
    
    status_code = 200
    """
    The HTTP status code.
    """
    
    mimetype = None
    """
    The mime type of the exception response. (use this or content_type).
    A character encoding might be added to the mimetype (like text/xml;charset=UTF-8) 
    """
    
    env = None
    """
    Jinja template environment.
    """
    
    def render(self, request_error):
        """
        Render the template of this exception handler. Passes the 
        ``request_error.message`` and ``request_error.code`` to the template.
        
        :type request_error: `RequestError`
        """
        result = self.template.render(exception=request_error.message,
                                      code=request_error.code)
        return Response(result, mimetype=self.mimetype, content_type=self.content_type,
                        status=self.status_code)
    
    @property
    def template(self):
        """
        The template for this ExceptionHandler.
        """
        return self.env.get_template(self.template_file)

class PlainExceptionHandler(ExceptionHandler):
    mimetype = 'text/plain'
    status_code = 404

    def render(self, request_error):
        if request_error.internal:
            self.status_code = 500
        return Response(request_error.message, status=self.status_code,
                        mimetype=self.mimetype)
