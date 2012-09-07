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
from mapproxy.exception import ExceptionHandler, XMLExceptionHandler
from mapproxy.response import Response
from mapproxy.image.message import message_image
from mapproxy.image.opts import ImageOptions
import mapproxy.service
from mapproxy.template import template_loader
get_template = template_loader(mapproxy.service.__name__, 'templates')

class WMSXMLExceptionHandler(XMLExceptionHandler):
    template_func = get_template

class WMS100ExceptionHandler(WMSXMLExceptionHandler):
    """
    Exception handler for OGC WMS 1.0.0 ServiceExceptionReports
    """
    template_file = 'wms100exception.xml'
    content_type = 'text/xml'

class WMS110ExceptionHandler(WMSXMLExceptionHandler):
    """
    Exception handler for OGC WMS 1.1.0 ServiceExceptionReports
    """
    template_file = 'wms110exception.xml'
    mimetype = 'application/vnd.ogc.se_xml'

class WMS111ExceptionHandler(WMSXMLExceptionHandler):
    """
    Exception handler for OGC WMS 1.1.1 ServiceExceptionReports
    """
    template_file = 'wms111exception.xml'
    mimetype = 'application/vnd.ogc.se_xml'

class WMS130ExceptionHandler(WMSXMLExceptionHandler):
    """
    Exception handler for OGC WMS 1.3.0 ServiceExceptionReports
    """
    template_file = 'wms130exception.xml'
    mimetype = 'text/xml'

class WMSImageExceptionHandler(ExceptionHandler):
    """
    Exception handler for image exceptions.
    """
    def render(self, request_error):
        request = request_error.request
        params = request.params
        format = params.format
        size = params.size
        if size is None:
            size = (256, 256)
        transparent = ('transparent' in params
                       and params['transparent'].lower() == 'true')
        bgcolor = WMSImageExceptionHandler._bgcolor(request.params)
        image_opts = ImageOptions(format=format, bgcolor=bgcolor, transparent=transparent)
        result = message_image(request_error.msg, size=size, image_opts=image_opts)
        return Response(result.as_buffer(), content_type=params.format_mime_type)

    @staticmethod
    def _bgcolor(params):
        """
        >>> WMSImageExceptionHandler._bgcolor({'bgcolor': '0Xf0ea42'})
        '#f0ea42'
        >>> WMSImageExceptionHandler._bgcolor({})
        '#ffffff'
        """
        if 'bgcolor' in params:
            color = params['bgcolor']
            if color.lower().startswith('0x'):
                color = '#' + color[2:]
        else:
            color = '#ffffff'
        return color

class WMSBlankExceptionHandler(WMSImageExceptionHandler):
    """
    Exception handler for blank image exceptions.
    """

    def render(self, request_error):
        request_error.msg = ''
        return WMSImageExceptionHandler.render(self, request_error)
