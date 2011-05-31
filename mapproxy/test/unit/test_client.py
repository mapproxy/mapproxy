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

from __future__ import with_statement

import os
import time
import sys

from mapproxy.client.http import HTTPClient, HTTPClientError
from mapproxy.client.tile import TMSClient, TileClient, TileURLTemplate
from mapproxy.client.wms import WMSClient, WMSInfoClient
from mapproxy.grid import tile_grid
from mapproxy.layer import MapQuery, InfoQuery
from mapproxy.request.wms import WMS111MapRequest, WMS100MapRequest,\
                                 WMS130MapRequest, WMS111FeatureInfoRequest
from mapproxy.srs import SRS
from mapproxy.test.unit.test_cache import MockHTTPClient
from mapproxy.test.http import mock_httpd, query_eq, assert_query_eq
from mapproxy.test.helper import assert_re, TempFile

from nose.tools import eq_
from nose.plugins.skip import SkipTest
from nose.plugins.attrib import attr

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
            assert_re(e.args[0], r'HTTP Error ".*": 500')
        else:
            assert False, 'expected HTTPClientError'
    def test_invalid_url_type(self):
        try:
            self.client.open('htp://example.org')
        except HTTPClientError, e:
            assert_re(e.args[0], r'No response .* "htp://example.*": unknown url type')
        else:
            assert False, 'expected HTTPClientError'
    def test_invalid_url(self):
        try:
            self.client.open('this is not a url')
        except HTTPClientError, e:
            assert_re(e.args[0], r'URL not correct "this is not.*": unknown url type')
        else:
            assert False, 'expected HTTPClientError'
    def test_unknown_host(self):
        try:
            self.client.open('http://thishostshouldnotexist000136really42.org')
        except HTTPClientError, e:
            assert_re(e.args[0], r'No response .* "http://thishost.*": .*')
        else:
            assert False, 'expected HTTPClientError'
    def test_no_connect(self):
        try:
            self.client.open('http://localhost:53871')
        except HTTPClientError, e:
            assert_re(e.args[0], r'No response .* "http://localhost.*": Connection refused')
        else:
            assert False, 'expected HTTPClientError'
    
    @attr('online')
    def test_https_no_ssl_module_error(self):
        from mapproxy.client import http
        old_ssl = http.ssl
        try:
            http.ssl = None
            try:
                self.client = HTTPClient('https://www.google.com/')
            except ImportError:
                pass
            else:
                assert False, 'no ImportError for missing ssl module'
        finally:
            http.ssl = old_ssl
    
    @attr('online')
    def test_https_no_ssl_module_insecure(self):
        from mapproxy.client import http
        old_ssl = http.ssl
        try:
            http.ssl = None
            self.client = HTTPClient('https://www.google.com/', insecure=True)
            self.client.open('https://www.google.com/')
        finally:
            http.ssl = old_ssl
    
    @attr('online')
    def test_https_valid_cert(self):
        try:
            import ssl; ssl
        except ImportError:
            raise SkipTest()
        
        cert_file = '/etc/ssl/certs/ca-certificates.crt'
        if os.path.exists(cert_file):
            self.client = HTTPClient('https://www.google.com/', ssl_ca_certs=cert_file)
            self.client.open('https://www.google.com/')
        else:
            with TempFile() as tmp:
                with open(tmp, 'w') as f:
                    f.write(GOOGLE_ROOT_CERT)
                self.client = HTTPClient('https://www.google.com/', ssl_ca_certs=tmp)
                self.client.open('https://www.google.com/')
    
    @attr('online')
    def test_https_invalid_cert(self):
        try:
            import ssl; ssl
        except ImportError:
            raise SkipTest()
        
        with TempFile() as tmp:
            self.client = HTTPClient('https://www.google.com/', ssl_ca_certs=tmp)
            try:
                self.client.open('https://www.google.com/')
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

# Equifax Secure Certificate Authority
# Expires: 2018-08-22
GOOGLE_ROOT_CERT = """
-----BEGIN CERTIFICATE-----
MIIDIDCCAomgAwIBAgIENd70zzANBgkqhkiG9w0BAQUFADBOMQswCQYDVQQGEwJV
UzEQMA4GA1UEChMHRXF1aWZheDEtMCsGA1UECxMkRXF1aWZheCBTZWN1cmUgQ2Vy
dGlmaWNhdGUgQXV0aG9yaXR5MB4XDTk4MDgyMjE2NDE1MVoXDTE4MDgyMjE2NDE1
MVowTjELMAkGA1UEBhMCVVMxEDAOBgNVBAoTB0VxdWlmYXgxLTArBgNVBAsTJEVx
dWlmYXggU2VjdXJlIENlcnRpZmljYXRlIEF1dGhvcml0eTCBnzANBgkqhkiG9w0B
AQEFAAOBjQAwgYkCgYEAwV2xWGcIYu6gmi0fCG2RFGiYCh7+2gRvE4RiIcPRfM6f
BeC4AfBONOziipUEZKzxa1NfBbPLZ4C/QgKO/t0BCezhABRP/PvwDN1Dulsr4R+A
cJkVV5MW8Q+XarfCaCMczE1ZMKxRHjuvK9buY0V7xdlfUNLjUA86iOe/FP3gx7kC
AwEAAaOCAQkwggEFMHAGA1UdHwRpMGcwZaBjoGGkXzBdMQswCQYDVQQGEwJVUzEQ
MA4GA1UEChMHRXF1aWZheDEtMCsGA1UECxMkRXF1aWZheCBTZWN1cmUgQ2VydGlm
aWNhdGUgQXV0aG9yaXR5MQ0wCwYDVQQDEwRDUkwxMBoGA1UdEAQTMBGBDzIwMTgw
ODIyMTY0MTUxWjALBgNVHQ8EBAMCAQYwHwYDVR0jBBgwFoAUSOZo+SvSspXXR9gj
IBBPM5iQn9QwHQYDVR0OBBYEFEjmaPkr0rKV10fYIyAQTzOYkJ/UMAwGA1UdEwQF
MAMBAf8wGgYJKoZIhvZ9B0EABA0wCxsFVjMuMGMDAgbAMA0GCSqGSIb3DQEBBQUA
A4GBAFjOKer89961zgK5F7WF0bnj4JXMJTENAKaSbn+2kmOeUJXRmm/kEd5jhW6Y
7qj/WsjTVbJmcVfewCHrPSqnI0kBBIZCe/zuf6IWUrVnZ9NA2zsmWLIodz2uFHdh
1voqZiegDfqnc1zqcPGUIWVEX/r87yloqaKHee9570+sB3c4
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

    def test_arcgiscache_path(self):
        template = TileURLTemplate(TESTSERVER_URL + '/%(arcgiscache_path)s.png')
        client = TileClient(template)
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/L09/R0000000d/C00000005.png'},
                                              {'body': 'tile',
                                               'headers': {'content-type': 'image/png'}})]):
            resp = client.get_tile((5, 13, 9)).source.read()
            eq_(resp, 'tile')

    def test_bbox(self):
        grid = tile_grid(4326)
        template = TileURLTemplate(TESTSERVER_URL + '/service?BBOX=%(bbox)s')
        client = TileClient(template, grid=grid)
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/service?BBOX=-180.00000000,0.00000000,-90.00000000,90.00000000'},
                                              {'body': 'tile',
                                               'headers': {'content-type': 'image/png'}})]):
            resp = client.get_tile((0, 1, 2)).source.read()
            eq_(resp, 'tile')

class TestCombinedWMSClient(object):
    def setup(self):
        self.http = MockHTTPClient()
    def test_combine(self):
        req1 = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
                                    param={'layers':'foo', 'transparent': 'true'})
        wms1 = WMSClient(req1, http_client=self.http)
        req2 = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
                                    param={'layers':'bar', 'transparent': 'true'})
        wms2 = WMSClient(req2, http_client=self.http)
        
        req = MapQuery((-200000, -200000, 200000, 200000), (512, 512), SRS(900913), 'png')
        
        combined = wms1.combined_client(wms2, req)
        eq_(combined.request_template.params.layers, ['foo', 'bar'])
        eq_(combined.request_template.url, TESTSERVER_URL + '/service?map=foo')

    def test_combine_different_url(self):
        req1 = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=bar',
                                    param={'layers':'foo', 'transparent': 'true'})
        wms1 = WMSClient(req1, http_client=self.http)
        req2 = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
                                    param={'layers':'bar', 'transparent': 'true'})
        wms2 = WMSClient(req2, http_client=self.http)
        
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
