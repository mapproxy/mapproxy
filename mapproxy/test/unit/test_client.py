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

from __future__ import with_statement

import time
import sys

from mapproxy.client.http import HTTPClient, HTTPClientError
from mapproxy.client.tile import TMSClient, TileClient, TileURLTemplate
from mapproxy.client.wms import WMSClient, WMSInfoClient
from mapproxy.layer import MapQuery, InfoQuery
from mapproxy.request.wms import WMS111MapRequest, WMS100MapRequest,\
                                 WMS130MapRequest, WMS111FeatureInfoRequest
from mapproxy.srs import SRS
from mapproxy.test.http import mock_httpd, query_eq, assert_query_eq
from mapproxy.test.helper import assert_re, TempFile

from nose.tools import eq_
from nose.plugins.skip import SkipTest

TESTSERVER_ADDRESS = ('127.0.0.1', 56413)
TESTSERVER_URL = 'http://%s:%s' % TESTSERVER_ADDRESS

class TestHTTPClient(object):
    def setup(self):
        self.client = HTTPClient()
    
    def test_post(self):
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/service?foo=bar', 'method': 'POST'},
                                              {'status': '200', 'body': ''})]):
            self.client.open(TESTSERVER_URL + '/service', data="foo=bar")
    
    def test_internal_error_response(self):
        try:
            with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/'},
                                                  {'status': '500', 'body': ''})]):
                self.client.open(TESTSERVER_URL + '/')
        except HTTPClientError, e:
            assert_re(e.args[0], r'HTTP Error \(.*\): 500')
        else:
            assert False, 'expected HTTPClientError'
    def test_invalid_url_type(self):
        try:
            self.client.open('htp://example.org')
        except HTTPClientError, e:
            assert_re(e.args[0], r'No response .* \(htp://example.*\): unknown url type')
        else:
            assert False, 'expected HTTPClientError'
    def test_invalid_url(self):
        try:
            self.client.open('this is not a url')
        except HTTPClientError, e:
            assert_re(e.args[0], r'URL not correct \(this is not.*\): unknown url type')
        else:
            assert False, 'expected HTTPClientError'
    def test_unknown_host(self):
        try:
            self.client.open('http://thishostshouldnotexist000136really42.org')
        except HTTPClientError, e:
            assert_re(e.args[0], r'No response .* \(http://thishost.*\): .*')
        else:
            assert False, 'expected HTTPClientError'
    def test_no_connect(self):
        try:
            self.client.open('http://localhost:53871')
        except HTTPClientError, e:
            assert_re(e.args[0], r'No response .* \(http://localhost.*\): Connection refused')
        else:
            assert False, 'expected HTTPClientError'
    
    def test_https_no_ssl_module_error(self):
        from mapproxy.client import http
        old_ssl = http.ssl
        try:
            http.ssl = None
            try:
                self.client = HTTPClient('https://trac.osgeo.org/')
            except ImportError:
                pass
            else:
                assert False, 'no ImportError for missing ssl module'
        finally:
            http.ssl = old_ssl
    
    def test_https_no_ssl_module_insecure(self):
        from mapproxy.client import http
        old_ssl = http.ssl
        try:
            http.ssl = None
            self.client = HTTPClient('https://trac.osgeo.org/', insecure=True)
            self.client.open('https://trac.osgeo.org/')
        finally:
            http.ssl = old_ssl
    
    def test_https_valid_cert(self):
        try:
            import ssl; ssl
        except ImportError:
            raise SkipTest()
        
        with TempFile() as tmp:
            with open(tmp, 'w') as f:
                f.write(OSGEO_CERT)
            self.client = HTTPClient('https://trac.osgeo.org/', ssl_ca_certs=tmp)
            self.client.open('https://trac.osgeo.org/')
    
    def test_https_invalid_cert(self):
        try:
            import ssl; ssl
        except ImportError:
            raise SkipTest()
        
        with TempFile() as tmp:
            self.client = HTTPClient('https://trac.osgeo.org/', ssl_ca_certs=tmp)
            try:
                self.client.open('https://trac.osgeo.org/')
            except HTTPClientError, e:
                assert_re(e.args[0], r'Could not verify connection to URL')
        
    def test_timeouts(self):
        test_req = ({'path': '/', 'req_assert_function': lambda x: time.sleep(0.5) or True},
                    {'body': 'nothing'})

        import mapproxy.client.http

        old_timeout = mapproxy.client.http._max_set_timeout
        mapproxy.client.http._max_set_timeout = None

        client1 = HTTPClient(timeout=0.1)
        client2 = HTTPClient(timeout=0.2)
        with mock_httpd(TESTSERVER_ADDRESS, [test_req]):
            try:
                start = time.time()
                client1.open(TESTSERVER_URL+'/')
            except HTTPClientError, ex:
                assert 'timed out' in ex.args[0]
            else:
                assert False, 'HTTPClientError expected'
            duration1 = time.time() - start

        with mock_httpd(TESTSERVER_ADDRESS, [test_req]):
            try:
                start = time.time()
                client2.open(TESTSERVER_URL+'/')
            except HTTPClientError, ex:
                assert 'timed out' in ex.args[0]
            else:
                assert False, 'HTTPClientError expected'
            duration2 = time.time() - start

        if sys.version_info >= (2, 6):
            # check individual timeouts
            assert 0.1 <= duration1 < 0.2
            assert 0.2 <= duration2 < 0.3
        else:
            # use max timeout in Python 2.5
            assert 0.2 <= duration1 < 0.3
            assert 0.2 <= duration2 < 0.3

        mapproxy.client.http._max_set_timeout = old_timeout

        
OSGEO_CERT = """
-----BEGIN CERTIFICATE-----
MIIE2DCCBEGgAwIBAgIEN0rSQzANBgkqhkiG9w0BAQUFADCBwzELMAkGA1UEBhMC
VVMxFDASBgNVBAoTC0VudHJ1c3QubmV0MTswOQYDVQQLEzJ3d3cuZW50cnVzdC5u
ZXQvQ1BTIGluY29ycC4gYnkgcmVmLiAobGltaXRzIGxpYWIuKTElMCMGA1UECxMc
KGMpIDE5OTkgRW50cnVzdC5uZXQgTGltaXRlZDE6MDgGA1UEAxMxRW50cnVzdC5u
ZXQgU2VjdXJlIFNlcnZlciBDZXJ0aWZpY2F0aW9uIEF1dGhvcml0eTAeFw05OTA1
MjUxNjA5NDBaFw0xOTA1MjUxNjM5NDBaMIHDMQswCQYDVQQGEwJVUzEUMBIGA1UE
ChMLRW50cnVzdC5uZXQxOzA5BgNVBAsTMnd3dy5lbnRydXN0Lm5ldC9DUFMgaW5j
b3JwLiBieSByZWYuIChsaW1pdHMgbGlhYi4pMSUwIwYDVQQLExwoYykgMTk5OSBF
bnRydXN0Lm5ldCBMaW1pdGVkMTowOAYDVQQDEzFFbnRydXN0Lm5ldCBTZWN1cmUg
U2VydmVyIENlcnRpZmljYXRpb24gQXV0aG9yaXR5MIGdMA0GCSqGSIb3DQEBAQUA
A4GLADCBhwKBgQDNKIM0VBuJ8w+vN5Ex/68xYMmo6LIQaO2f55M28Qpku0f1BBc/
I0dNxScZgSYMVHINiC3ZH5oSn7yzcdOAGT9HZnuMNSjSuQrfJNqc1lB5gXpa0zf3
wkrYKZImZNHkmGw6AIr1NJtl+O3jEP/9uElY3KDegjlrgbEWGWG5VLbmQwIBA6OC
AdcwggHTMBEGCWCGSAGG+EIBAQQEAwIABzCCARkGA1UdHwSCARAwggEMMIHeoIHb
oIHYpIHVMIHSMQswCQYDVQQGEwJVUzEUMBIGA1UEChMLRW50cnVzdC5uZXQxOzA5
BgNVBAsTMnd3dy5lbnRydXN0Lm5ldC9DUFMgaW5jb3JwLiBieSByZWYuIChsaW1p
dHMgbGlhYi4pMSUwIwYDVQQLExwoYykgMTk5OSBFbnRydXN0Lm5ldCBMaW1pdGVk
MTowOAYDVQQDEzFFbnRydXN0Lm5ldCBTZWN1cmUgU2VydmVyIENlcnRpZmljYXRp
b24gQXV0aG9yaXR5MQ0wCwYDVQQDEwRDUkwxMCmgJ6AlhiNodHRwOi8vd3d3LmVu
dHJ1c3QubmV0L0NSTC9uZXQxLmNybDArBgNVHRAEJDAigA8xOTk5MDUyNTE2MDk0
MFqBDzIwMTkwNTI1MTYwOTQwWjALBgNVHQ8EBAMCAQYwHwYDVR0jBBgwFoAU8Bdi
E1U9s/8KAGv7UISX8+1i0BowHQYDVR0OBBYEFPAXYhNVPbP/CgBr+1CEl/PtYtAa
MAwGA1UdEwQFMAMBAf8wGQYJKoZIhvZ9B0EABAwwChsEVjQuMAMCBJAwDQYJKoZI
hvcNAQEFBQADgYEAkNwwAvpkdMKnCqV8IY00F6j7Rw7/JXyNEwr75Ji174z4xRAN
95K+8cPV1ZVqBLssziY2ZcgxxufuP+NXdYR6Ee9GTxj005i7qIcyunL2POI9n9cd
2cNgQ4xYDiKWL2KjLB+6rQXvqzJ4h6BUcxm1XAX5Uj5tLUUL9wqT6u0G+bI=
-----END CERTIFICATE-----

"""

# class TestWMSClient(object):
#     def setup(self):
#         self.req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo')
#         self.wms = WMSClient(self.req)
#     def test_request(self):
#         expected_req = ({'path': r'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
#                                   '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326'
#                                   '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,90.0&WIDTH=512&STYLES='},
#                         {'body': 'no image', 'headers': {'content-type': 'image/png'}})
#         with mock_httpd(TESTSERVER_ADDRESS, [expected_req]):
#             req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
#                                    param={'layers': 'foo', 'bbox': '-180.0,-90.0,180.0,90.0'})
#             req.params.size = (512, 256)
#             req.params['format'] = 'image/png'
#             req.params['srs'] = 'EPSG:4326'
#             resp = self.wms.get_map(req)
#     
#     def test_request_w_auth(self):
#         wms = WMSClient(self.req, http_client=HTTPClient(self.req.url, username='foo', password='bar'))
#         def assert_auth(req_handler):
#             assert 'Authorization' in req_handler.headers
#             auth_data = req_handler.headers['Authorization'].split()[1]
#             auth_data = auth_data.decode('base64')
#             eq_(auth_data, 'foo:bar')
#             return True
#         expected_req = ({'path': r'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
#                                   '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326'
#                                   '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,90.0&WIDTH=512&STYLES=',
#                          'require_basic_auth': True,
#                          'req_assert_function': assert_auth},
#                         {'body': 'no image', 'headers': {'content-type': 'image/png'}})
#         with mock_httpd(TESTSERVER_ADDRESS, [expected_req]):
#             req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
#                                    param={'layers': 'foo', 'bbox': '-180.0,-90.0,180.0,90.0'})
#             req.params.size = (512, 256)
#             req.params['format'] = 'image/png'
#             req.params['srs'] = 'EPSG:4326'
#             resp = wms.get_map(req)
# 
#     def test_get_tile_non_image_content_type(self):
#         expected_req = ({'path': r'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
#                                   '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&STYLES='
#                                   '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,90.0&WIDTH=512'},
#                         {'body': 'error', 'headers': {'content-type': 'text/plain'}})
#         with mock_httpd(TESTSERVER_ADDRESS, [expected_req]):
#             try:
#                 req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
#                                        param={'layers': 'foo', 'bbox': '-180.0,-90.0,180.0,90.0'})
#                 req.params.size = (512, 256)
#                 req.params['format'] = 'image/png'
#                 req.params['srs'] = 'EPSG:4326'
#                 resp = self.wms.get_map(req)
#             except HTTPClientError, e:
#                 assert_re(e.args[0], r'response is not an image')
#             else:
#                 assert False, 'expected HTTPClientError'
#     
#     def test__transform_fi_request(self):
#         default_req = WMS111MapRequest(url_decode('srs=EPSG%3A4326'))
#         fi_req = Request(make_wsgi_env('''LAYERS=mapserver_cache&
#          QUERY_LAYERS=mapnik_mapserver&X=601&Y=528&FORMAT=image%2Fpng&SERVICE=WMS&
#          VERSION=1.1.1&REQUEST=GetFeatureInfo&STYLES=&
#          EXCEPTIONS=application%2Fvnd.ogc.se_inimage&SRS=EPSG%3A900913&
#          BBOX=730930.9303206909,6866851.379301955,1031481.3254841676,7170153.507483206&
#          WIDTH=983&HEIGHT=992'''.replace('\n', '').replace(' ', '')))
#         wms_client = WMSClient(default_req)
#         orig_req = wms_request(fi_req)
#         req = wms_request(fi_req)
#         wms_client._transform_fi_request(req)
#         
#         eq_(req.params.srs, 'EPSG:4326')
#         eq_(req.params.pos, (601, 523))
# 
#         default_req = WMS111MapRequest(url_decode('srs=EPSG%3A900913'))
#         wms_client = WMSClient(default_req)
#         wms_client._transform_fi_request(req)
#         
#         eq_(req.params.srs, 'EPSG:900913')
#         eq_(req.params.pos, (601, 528))
#         assert bbox_equals(orig_req.params.bbox, req.params.bbox, 0.1)
        
class TestTMSClient(object):
    def setup(self):
        self.client = TMSClient(TESTSERVER_URL)
    def test_get_tile(self):
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/9/5/13.png'},
                                                {'body': 'tile', 'headers': {'content-type': 'image/png'}})]):
            resp = self.client.get_tile((5, 13, 9)).source.read()
            eq_(resp, 'tile')

class TestTileClient(object):
    def test_tc_path(self):
        template = TileURLTemplate(TESTSERVER_URL + '/%(tc_path)s.png')
        client = TileClient(template)
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/09/000/000/005/000/000/013.png'},
                                              {'body': 'tile',
                                               'headers': {'content-type': 'image/png'}})]):
            resp = client.get_tile((5, 13, 9)).source.read()
            eq_(resp, 'tile')

    def test_quadkey(self):
        template = TileURLTemplate(TESTSERVER_URL + '/key=%(quadkey)s&format=%(format)s')
        client = TileClient(template)
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/key=000002303&format=png'},
                                              {'body': 'tile',
                                               'headers': {'content-type': 'image/png'}})]):
            resp = client.get_tile((5, 13, 9)).source.read()
            eq_(resp, 'tile')
    def test_xyz(self):
        template = TileURLTemplate(TESTSERVER_URL + '/x=%(x)s&y=%(y)s&z=%(z)s&format=%(format)s')
        client = TileClient(template)
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/x=5&y=13&z=9&format=png'},
                                              {'body': 'tile',
                                               'headers': {'content-type': 'image/png'}})]):
            resp = client.get_tile((5, 13, 9)).source.read()
            eq_(resp, 'tile')

from mapproxy.test.unit.test_cache import MockHTTPClient
class TestWMSClient(object):
    def setup(self):
        self.req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo', param={'layers':'foo'})
        self.http = MockHTTPClient()
        self.wms = WMSClient(self.req, http_client=self.http, supported_srs=[SRS(4326)])
    def test_request(self):
        req = MapQuery((-180.0, -90.0, 180.0, 90.0), (512, 256), SRS(4326), 'png')
        self.wms.get_map(req)
        eq_(len(self.http.requested), 1)
        assert_query_eq(self.http.requested[0],
            TESTSERVER_URL+'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                           '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326'
                           '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,90.0&WIDTH=512&STYLES=')

    def test_transformed_request(self):
        req = MapQuery((-200000, -200000, 200000, 200000), (512, 512), SRS(900913), 'png')
        resp = self.wms.get_map(req)
        eq_(len(self.http.requested), 1)
        
        assert_query_eq(self.http.requested[0], 
            TESTSERVER_URL+'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                           '&REQUEST=GetMap&HEIGHT=512&SRS=EPSG%3A4326'
                           '&VERSION=1.1.1&WIDTH=512&STYLES='
                           '&BBOX=-1.79663056824,-1.7963362121,1.79663056824,1.7963362121')
        img = resp.as_image()
        assert img.mode in ('P', 'RGB')

    def test_similar_srs(self):
        # request in 3857 and source supports only 900913
        # 3857 and 900913 are equal but the client requests must use 900913
        self.req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
                                    param={'layers':'foo', 'transparent': 'true'})
        self.wms = WMSClient(self.req, http_client=self.http, supported_srs=[SRS(900913)])

        req = MapQuery((-200000, -200000, 200000, 200000), (512, 512), SRS(3857), 'png')
        self.wms.get_map(req)
        eq_(len(self.http.requested), 1)
        
        assert_query_eq(self.http.requested[0],
            TESTSERVER_URL+'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                           '&REQUEST=GetMap&HEIGHT=512&SRS=EPSG%3A900913'
                           '&VERSION=1.1.1&WIDTH=512&STYLES=&transparent=true'
                           '&BBOX=-200000,-200000,200000,200000')

    def test_transformed_request_transparent(self):
        self.req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
                                    param={'layers':'foo', 'transparent': 'true'})
        self.wms = WMSClient(self.req, http_client=self.http, supported_srs=[SRS(4326)])

        req = MapQuery((-200000, -200000, 200000, 200000), (512, 512), SRS(900913), 'png')
        resp = self.wms.get_map(req)
        eq_(len(self.http.requested), 1)
        
        assert_query_eq(self.http.requested[0],
            TESTSERVER_URL+'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                           '&REQUEST=GetMap&HEIGHT=512&SRS=EPSG%3A4326'
                           '&VERSION=1.1.1&WIDTH=512&STYLES=&transparent=true'
                           '&BBOX=-1.79663056824,-1.7963362121,1.79663056824,1.7963362121')
        img = resp.as_image()
        assert img.mode in ('P', 'RGBA')
        img = img.convert('RGBA')
        eq_(img.getpixel((5, 5))[3], 0)

class TestCombinedWMSClient(object):
    def setup(self):
        self.http = MockHTTPClient()
    def test_combine(self):
        req1 = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
                                    param={'layers':'foo', 'transparent': 'true'})
        wms1 = WMSClient(req1, http_client=self.http, supported_srs=[SRS(4326)])
        req2 = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
                                    param={'layers':'bar', 'transparent': 'true'})
        wms2 = WMSClient(req2, http_client=self.http, supported_srs=[SRS(4326)])
        
        req = MapQuery((-200000, -200000, 200000, 200000), (512, 512), SRS(900913), 'png')
        
        combined = wms1.combined_client(wms2, req)
        eq_(combined.request_template.params.layers, ['foo', 'bar'])
        eq_(combined.request_template.url, TESTSERVER_URL + '/service?map=foo')

    def test_combine_different_url(self):
        req1 = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=bar',
                                    param={'layers':'foo', 'transparent': 'true'})
        wms1 = WMSClient(req1, http_client=self.http, supported_srs=[SRS(4326)])
        req2 = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
                                    param={'layers':'bar', 'transparent': 'true'})
        wms2 = WMSClient(req2, http_client=self.http, supported_srs=[SRS(4326)])
        
        req = MapQuery((-200000, -200000, 200000, 200000), (512, 512), SRS(900913), 'png')
        
        combined = wms1.combined_client(wms2, req)
        assert combined is None
        
class TestWMSInfoClient(object):
    def test_transform_fi_request_supported_srs(self):
        req = WMS111FeatureInfoRequest(url=TESTSERVER_URL + '/service?map=foo', param={'layers':'foo'})
        http = MockHTTPClient()
        wms = WMSInfoClient(req, http_client=http, supported_srs=[SRS(31467)])
        fi_req = InfoQuery((8, 50, 9, 51), (512, 512),
                           SRS(4326), (256, 256), 'text/plain')
        
        wms.get_info(fi_req)
        
        assert_query_eq(http.requested[0],
            TESTSERVER_URL+'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                           '&REQUEST=GetFeatureInfo&HEIGHT=512&SRS=EPSG%3A31467&info_format=text/plain'
                           '&query_layers=foo'
                           '&VERSION=1.1.1&WIDTH=512&STYLES=&x=259&y=255'
                           '&BBOX=3428376.92835,5540409.81393,3500072.08248,5652124.61616')

    def test_transform_fi_request(self):
        req = WMS111FeatureInfoRequest(url=TESTSERVER_URL + '/service?map=foo', param={'layers':'foo', 'srs': 'EPSG:31467'})
        http = MockHTTPClient()
        wms = WMSInfoClient(req, http_client=http)
        fi_req = InfoQuery((8, 50, 9, 51), (512, 512),
                           SRS(4326), (256, 256), 'text/plain')
        
        wms.get_info(fi_req)
        
        assert_query_eq(http.requested[0],
            TESTSERVER_URL+'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                           '&REQUEST=GetFeatureInfo&HEIGHT=512&SRS=EPSG%3A31467&info_format=text/plain'
                           '&query_layers=foo'
                           '&VERSION=1.1.1&WIDTH=512&STYLES=&x=259&y=255'
                           '&BBOX=3428376.92835,5540409.81393,3500072.08248,5652124.61616')

class TestWMSMapRequest100(object):
    def setup(self):
        self.r = WMS100MapRequest(param=dict(layers='foo', version='1.1.1', request='GetMap'))
        self.r.params = self.r.adapt_params_to_version()
    def test_version(self):
        eq_(self.r.params['WMTVER'], '1.0.0')
        assert 'VERSION' not in self.r.params
    def test_service(self):
        assert 'SERVICE' not in self.r.params 
    def test_request(self):
        eq_(self.r.params['request'], 'map')
    def test_str(self):
        assert_query_eq(str(self.r.params), 'layers=foo&styles=&request=map&wmtver=1.0.0')

class TestWMSMapRequest130(object):
    def setup(self):
        self.r = WMS130MapRequest(param=dict(layers='foo', WMTVER='1.0.0'))
        self.r.params = self.r.adapt_params_to_version()
    def test_version(self):
        eq_(self.r.params['version'], '1.3.0')
        assert 'WMTVER' not in self.r.params
    def test_service(self):
        eq_(self.r.params['service'], 'WMS' )
    def test_request(self):
        eq_(self.r.params['request'], 'GetMap')
    def test_str(self):
        query_eq(str(self.r.params), 'layers=foo&styles=&service=WMS&request=GetMap&version=1.3.0')

class TestWMSMapRequest111(object):
    def setup(self):
        self.r = WMS111MapRequest(param=dict(layers='foo', WMTVER='1.0.0'))
        self.r.params = self.r.adapt_params_to_version()
    def test_version(self):
        eq_(self.r.params['version'], '1.1.1')
        assert 'WMTVER' not in self.r.params