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

from io import BytesIO

from mapproxy.compat.image import Image
from mapproxy.exception import RequestError
from mapproxy.request import url_decode
from mapproxy.request.base import Request
from mapproxy.request.wms import WMSMapRequest
from mapproxy.request.wms.exception import (
    WMS100ExceptionHandler,
    WMS111ExceptionHandler,
    WMS130ExceptionHandler,
    WMS110ExceptionHandler,
)
from mapproxy.service.ows import OWSServer
from mapproxy.test.helper import Mocker, validate_with_dtd, validate_with_xsd
from mapproxy.test.image import is_png


class ExceptionHandlerTest(Mocker):
    def setup_method(self):
        Mocker.setup_method(self)
        req = url_decode("""LAYERS=foo&FORMAT=image%2Fpng&SERVICE=WMS&VERSION=1.1.1&
REQUEST=GetMap&STYLES=&EXCEPTIONS=application%2Fvnd.ogc.se_xml&SRS=EPSG%3A900913&
BBOX=8,4,9,5&WIDTH=150&HEIGHT=100""".replace('\n', ''))
        self.req = req


class TestWMS111ExceptionHandler(Mocker):
    def test_render(self):
        req = self.mock(WMSMapRequest)
        req_ex = RequestError('the exception message', request=req)
        ex_handler = WMS111ExceptionHandler()
        self.expect(req.exception_handler).result(ex_handler)

        self.replay()
        response = req_ex.render()
        assert response.content_type == 'application/vnd.ogc.se_xml'
        expected_resp = b"""
<?xml version="1.0"?>
<!DOCTYPE ServiceExceptionReport SYSTEM "http://schemas.opengis.net/wms/1.1.1/exception_1_1_1.dtd">
<ServiceExceptionReport version="1.1.1">
    <ServiceException>the exception message</ServiceException>
</ServiceExceptionReport>
"""
        assert expected_resp.strip() == response.data
        assert validate_with_dtd(response.data, 'wms/1.1.1/exception_1_1_1.dtd')

    def test_render_w_code(self):
        req = self.mock(WMSMapRequest)
        req_ex = RequestError('the exception message', code='InvalidFormat',
                              request=req)
        ex_handler = WMS111ExceptionHandler()
        self.expect(req.exception_handler).result(ex_handler)

        self.replay()
        response = req_ex.render()
        assert response.content_type == 'application/vnd.ogc.se_xml'
        expected_resp = b"""
<?xml version="1.0"?>
<!DOCTYPE ServiceExceptionReport SYSTEM "http://schemas.opengis.net/wms/1.1.1/exception_1_1_1.dtd">
<ServiceExceptionReport version="1.1.1">
    <ServiceException code="InvalidFormat">the exception message</ServiceException>
</ServiceExceptionReport>
"""
        assert expected_resp.strip() == response.data
        assert validate_with_dtd(response.data, 'wms/1.1.1/exception_1_1_1.dtd')


class TestWMS110ExceptionHandler(Mocker):
    def test_render(self):
        req = self.mock(WMSMapRequest)
        req_ex = RequestError('the exception message', request=req)
        ex_handler = WMS110ExceptionHandler()
        self.expect(req.exception_handler).result(ex_handler)

        self.replay()
        response = req_ex.render()
        assert response.content_type == 'application/vnd.ogc.se_xml'
        expected_resp = b"""
<?xml version="1.0"?>
<!DOCTYPE ServiceExceptionReport SYSTEM "http://schemas.opengis.net/wms/1.1.0/exception_1_1_0.dtd">
<ServiceExceptionReport version="1.1.0">
    <ServiceException>the exception message</ServiceException>
</ServiceExceptionReport>
"""
        assert expected_resp.strip() == response.data
        assert validate_with_dtd(response.data, 'wms/1.1.0/exception_1_1_0.dtd')

    def test_render_w_code(self):
        req = self.mock(WMSMapRequest)
        req_ex = RequestError('the exception message', code='InvalidFormat',
                              request=req)
        ex_handler = WMS110ExceptionHandler()
        self.expect(req.exception_handler).result(ex_handler)

        self.replay()
        response = req_ex.render()
        assert response.content_type == 'application/vnd.ogc.se_xml'
        expected_resp = b"""
<?xml version="1.0"?>
<!DOCTYPE ServiceExceptionReport SYSTEM "http://schemas.opengis.net/wms/1.1.0/exception_1_1_0.dtd">
<ServiceExceptionReport version="1.1.0">
    <ServiceException code="InvalidFormat">the exception message</ServiceException>
</ServiceExceptionReport>
"""
        assert expected_resp.strip() == response.data
        assert validate_with_dtd(response.data, 'wms/1.1.0/exception_1_1_0.dtd')


class TestWMS130ExceptionHandler(Mocker):
    def test_render(self):
        req = self.mock(WMSMapRequest)
        req_ex = RequestError('the exception message', request=req)
        ex_handler = WMS130ExceptionHandler()
        self.expect(req.exception_handler).result(ex_handler)

        self.replay()
        response = req_ex.render()
        assert response.content_type == 'text/xml; charset=utf-8'
        expected_resp = b"""
<?xml version="1.0"?>
<ServiceExceptionReport version="1.3.0"
  xmlns="http://www.opengis.net/ogc"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.opengis.net/ogc
http://schemas.opengis.net/wms/1.3.0/exceptions_1_3_0.xsd">
    <ServiceException>the exception message</ServiceException>
</ServiceExceptionReport>
"""
        assert expected_resp.strip() == response.data
        assert validate_with_xsd(response.data, 'wms/1.3.0/exceptions_1_3_0.xsd')

    def test_render_w_code(self):
        req = self.mock(WMSMapRequest)
        req_ex = RequestError('the exception message', code='InvalidFormat',
                              request=req)
        ex_handler = WMS130ExceptionHandler()
        self.expect(req.exception_handler).result(ex_handler)

        self.replay()
        response = req_ex.render()
        assert response.content_type == 'text/xml; charset=utf-8'
        expected_resp = b"""
<?xml version="1.0"?>
<ServiceExceptionReport version="1.3.0"
  xmlns="http://www.opengis.net/ogc"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.opengis.net/ogc
http://schemas.opengis.net/wms/1.3.0/exceptions_1_3_0.xsd">
    <ServiceException code="InvalidFormat">the exception message</ServiceException>
</ServiceExceptionReport>
"""
        assert expected_resp.strip() == response.data
        assert validate_with_xsd(response.data, 'wms/1.3.0/exceptions_1_3_0.xsd')

    def test_missing_service_request(self):
        reqString = "REQUEST=GetCapabilities"
        conf = {
            'QUERY_STRING': reqString,
            'wsgi.url_scheme': 'http',
            'HTTP_HOST': 'localhost',
        }
        req = Request(conf)
        ows_services = []
        server = OWSServer(ows_services)
        response = server.handle(req)

        expected_resp = """
<?xml version="1.0"?>
<ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows/1.1"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.opengis.net/ows/1.1 http://schemas.opengis.net/ows/1.1.0/owsExceptionReport.xsd"
  version="1.0.0" xml:lang="en">
  <ows:Exception exceptionCode="MissingParameterValue"
      locator="service">
    <ows:ExceptionText>The service parameter is missing</ows:ExceptionText>
  </ows:Exception>
</ows:ExceptionReport>
"""

        assert expected_resp.strip() == response.response.strip()
        assert response.content_type == 'text/xml; charset=utf-8'
        assert response.status == '400 Bad Request'
        assert validate_with_xsd(response.response, 'ows/1.1.0/owsExceptionReport.xsd')

    def test_invalid_service_request(self):
        reqString = "REQUEST=GetCapabilities&SERVICE=wms"
        conf = {
            'QUERY_STRING': reqString,
            'wsgi.url_scheme': 'http',
            'HTTP_HOST': 'localhost',
        }
        req = Request(conf)
        ows_services = []
        server = OWSServer(ows_services)
        response = server.handle(req)

        expected_resp = """
<?xml version="1.0"?>
<ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows/1.1"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.opengis.net/ows/1.1 http://schemas.opengis.net/ows/1.1.0/owsExceptionReport.xsd"
  version="1.0.0" xml:lang="en">
  <ows:Exception exceptionCode="InvalidParameterValue"
      locator="service">
    <ows:ExceptionText>The value of the service parameter &quot;wms&quot; is invalid</ows:ExceptionText>
  </ows:Exception>
</ows:ExceptionReport>
"""

        assert expected_resp.strip() == response.response
        assert response.content_type == 'text/xml; charset=utf-8'
        assert response.status == '400 Bad Request'
        assert validate_with_xsd(response.response, 'ows/1.1.0/owsExceptionReport.xsd')

    def test_valid_service_request(self):
        reqString = "REQUEST=GetCapabilities&SERVICE=wms"
        conf = {
            'QUERY_STRING': reqString,
            'wsgi.url_scheme': 'http',
            'HTTP_HOST': 'localhost',
        }
        req = Request(conf)

        class Service(object):

            def __init__(self, service):
                self.service = service

            def handle(self, req):
                return 'all good'

        ows_services = [Service('wms')]
        server = OWSServer(ows_services)
        response = server.handle(req)

        expected_resp = 'all good'
        assert expected_resp == response


class TestWMS100ExceptionHandler(Mocker):
    def test_render(self):
        req = self.mock(WMSMapRequest)
        req_ex = RequestError('the exception message', request=req)
        ex_handler = WMS100ExceptionHandler()
        self.expect(req.exception_handler).result(ex_handler)

        self.replay()
        response = req_ex.render()

        assert response.content_type == 'text/xml'
        expected_resp = b"""
<?xml version="1.0"?>
<WMTException version="1.0.0">
the exception message
</WMTException>
"""
        assert expected_resp.strip() == response.data


class TestWMSImageExceptionHandler(ExceptionHandlerTest):
    def test_exception(self):
        self.req.set('exceptions', 'inimage')
        self.req.set('transparent', 'true')

        req = WMSMapRequest(self.req)
        req_ex = RequestError('the exception message', request=req)

        response = req_ex.render()
        assert response.content_type == 'image/png'
        data = BytesIO(response.data)
        assert is_png(data)
        img = Image.open(data)
        assert img.size == (150, 100)

    def test_exception_w_transparent(self):
        self.req.set('exceptions', 'inimage')
        self.req.set('transparent', 'true')

        req = WMSMapRequest(self.req)
        req_ex = RequestError('the exception message', request=req)

        response = req_ex.render()
        assert response.content_type == 'image/png'
        data = BytesIO(response.data)
        assert is_png(data)
        img = Image.open(data)
        assert img.size == (150, 100)
        img = img.convert('RGBA')
        assert img.getpixel((0, 0))[3] == 0
        extrema = img.getextrema()
        assert extrema != ((255, 255), (255, 255), (255, 255), (0, 0))


class TestWMSBlankExceptionHandler(ExceptionHandlerTest):
    def test_exception(self):
        self.req['exceptions'] = 'blank'
        req = WMSMapRequest(self.req)
        req_ex = RequestError('the exception message', request=req)

        response = req_ex.render()
        assert response.content_type == 'image/png'
        data = BytesIO(response.data)
        assert is_png(data)
        img = Image.open(data)
        assert img.size == (150, 100)
        assert img.getpixel((0, 0)) == 0  # pallete image
        assert img.getpalette()[0:3] == [255, 255, 255]

    def test_exception_w_bgcolor(self):
        self.req.set('exceptions', 'blank')
        self.req.set('bgcolor', '0xff00ff')

        req = WMSMapRequest(self.req)
        req_ex = RequestError('the exception message', request=req)

        response = req_ex.render()
        assert response.content_type == 'image/png'
        data = BytesIO(response.data)
        assert is_png(data)
        img = Image.open(data)
        assert img.size == (150, 100)
        assert img.getpixel((0, 0)) == 0  # pallete image
        assert img.getpalette()[0:3] == [255, 0, 255]

    def test_exception_w_transparent(self):
        self.req.set('exceptions', 'blank')
        self.req.set('transparent', 'true')

        req = WMSMapRequest(self.req)
        req_ex = RequestError('the exception message', request=req)

        response = req_ex.render()
        assert response.content_type == 'image/png'
        data = BytesIO(response.data)
        assert is_png(data)
        img = Image.open(data)
        assert img.size == (150, 100)
        assert img.mode == 'P'
        img = img.convert('RGBA')
        assert img.getpixel((0, 0))[3] == 0
