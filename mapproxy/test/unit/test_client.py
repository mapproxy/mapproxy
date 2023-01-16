# This file is part of the MapProxy project.
# Copyright (C) 2010-2017 Omniscale <http://omniscale.de>
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


import os
import time

import pytest

from mapproxy.client.http import HTTPClient, HTTPClientError, supports_ssl_default_context
from mapproxy.client.tile import TileClient, TileURLTemplate
from mapproxy.client.wms import WMSClient, WMSInfoClient
from mapproxy.grid import tile_grid
from mapproxy.layer import MapQuery, InfoQuery
from mapproxy.request.wms import (
    WMS111MapRequest,
    WMS100MapRequest,
    WMS130MapRequest,
    WMS111FeatureInfoRequest,
)
from mapproxy.source import SourceError
from mapproxy.srs import SRS, SupportedSRS
from mapproxy.test.helper import assert_re, TempFile
from mapproxy.test.http import mock_httpd, query_eq, assert_query_eq, wms_query_eq
from mapproxy.test.unit.test_cache import MockHTTPClient


TESTSERVER_ADDRESS = ('127.0.0.1', 56413)
TESTSERVER_URL = 'http://%s:%s' % TESTSERVER_ADDRESS


class TestHTTPClient(object):
    def setup(self):
        self.client = HTTPClient()

    def test_post(self):
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/service?foo=bar', 'method': 'POST'},
                                              {'status': '200', 'body': b''})]):
            self.client.open(TESTSERVER_URL + '/service', data=b"foo=bar")

    def test_internal_error_response(self):
        try:
            with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/'},
                                                  {'status': '500', 'body': b''})]):
                self.client.open(TESTSERVER_URL + '/')
        except HTTPClientError as e:
            assert_re(e.args[0], r'HTTP Error ".*": 500')
        else:
            assert False, 'expected HTTPClientError'

    def test_invalid_url_type(self):
        try:
            self.client.open('htp://example.org')
        except HTTPClientError as e:
            assert_re(e.args[0], r'No response .* "htp://example.*": unknown url type')
        else:
            assert False, 'expected HTTPClientError'

    def test_invalid_url(self):
        try:
            self.client.open('this is not a url')
        except HTTPClientError as e:
            assert_re(e.args[0], r'URL not correct "this is not.*": unknown url type')
        else:
            assert False, 'expected HTTPClientError'

    def test_unknown_host(self):
        try:
            self.client.open('http://thishostshouldnotexist000136really42.org')
        except HTTPClientError as e:
            assert_re(e.args[0], r'No response .* "http://thishost.*": .*')
        else:
            assert False, 'expected HTTPClientError'

    def test_no_connect(self):
        try:
            self.client.open('http://localhost:53871')
        except HTTPClientError as e:
            assert_re(e.args[0], r'No response .* "http://localhost.*": Connection refused')
        else:
            assert False, 'expected HTTPClientError'

    def test_internal_error_hide_error_details(self):
        try:
            with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/'},
                                                  {'status': '500', 'body': b''})]):
                HTTPClient(hide_error_details=True).open(TESTSERVER_URL + '/')
        except HTTPClientError as e:
            assert_re(e.args[0], r'HTTP Error \(see logs for URL and reason\).')
        else:
            assert False, 'expected HTTPClientError'

    @pytest.mark.online
    def test_https_untrusted_root(self):
        if not supports_ssl_default_context:
            raise pytest.skip("old python versions require ssl_ca_certs")
        self.client = HTTPClient('https://untrusted-root.badssl.com/')
        try:
            self.client.open('https://untrusted-root.badssl.com/')
        except HTTPClientError as e:
            assert_re(e.args[0], r'Could not verify connection to URL')

    @pytest.mark.online
    def test_https_insecure(self):
        self.client = HTTPClient(
            'https://untrusted-root.badssl.com/', insecure=True)
        self.client.open('https://untrusted-root.badssl.com/')

    @pytest.mark.online
    def test_https_valid_ca_cert_file(self):
        # verify with fixed ca_certs file
        cert_file = '/etc/ssl/certs/ca-certificates.crt'
        if os.path.exists(cert_file):
            self.client = HTTPClient('https://www.google.com/', ssl_ca_certs=cert_file)
            self.client.open('https://www.google.com/')
        else:
            with TempFile() as tmp:
                with open(tmp, 'wb') as f:
                    f.write(GOOGLE_ROOT_CERT)
                self.client = HTTPClient('https://www.google.com/', ssl_ca_certs=tmp)
                self.client.open('https://www.google.com/')

    @pytest.mark.online
    def test_https_valid_default_cert(self):
        # modern python should verify by default
        if not supports_ssl_default_context:
            raise pytest.skip("old python versions require ssl_ca_certs")
        self.client = HTTPClient('https://www.google.com/')
        self.client.open('https://www.google.com/')

    @pytest.mark.online
    def test_https_invalid_cert(self):
        # load 'wrong' root cert
        with TempFile() as tmp:
            with open(tmp, 'wb') as f:
                f.write(GOOGLE_ROOT_CERT)
            self.client = HTTPClient(
                'https://untrusted-root.badssl.com/', ssl_ca_certs=tmp)
            try:
                self.client.open('https://untrusted-root.badssl.com/')
            except HTTPClientError as e:
                assert_re(e.args[0], r'Could not verify connection to URL')

    def test_timeouts(self):
        test_req = ({'path': '/', 'req_assert_function': lambda x: time.sleep(0.9) or True},
                    {'body': b'nothing'})

        import mapproxy.client.http

        client1 = HTTPClient(timeout=0.1)
        client2 = HTTPClient(timeout=0.5)
        with mock_httpd(TESTSERVER_ADDRESS, [test_req]):
            try:
                start = time.time()
                client1.open(TESTSERVER_URL + '/')
            except HTTPClientError as ex:
                assert 'timed out' in ex.args[0]
            else:
                assert False, 'HTTPClientError expected'
            duration1 = time.time() - start

        with mock_httpd(TESTSERVER_ADDRESS, [test_req]):
            try:
                start = time.time()
                client2.open(TESTSERVER_URL + '/')
            except HTTPClientError as ex:
                assert 'timed out' in ex.args[0]
            else:
                assert False, 'HTTPClientError expected'
            duration2 = time.time() - start

        # check individual timeouts
        assert 0.1 <= duration1 < 0.5, duration1
        assert 0.5 <= duration2 < 0.9, duration2

    def test_manage_cookies_off(self):
        """
        Test the behavior when manage_cookies is off (the default). Cookies shouldn't be sent
        """
        self.client = HTTPClient()

        def assert_no_cookie(req_handler):
            return 'Cookie' not in req_handler.headers

        test_requests = [
            (
                {'path': '/', 'req_assert_function': assert_no_cookie},
                {'body': b'nothing', 'headers': {'Set-Cookie': "testcookie=42"}}
            ),
            (
                {'path': '/', 'req_assert_function': assert_no_cookie},
                {'body': b'nothing'}
            )
        ]
        with mock_httpd(TESTSERVER_ADDRESS, test_requests):
            self.client.open(TESTSERVER_URL + '/')
            self.client.open(TESTSERVER_URL + '/')

    def test_manage_cookies_on(self):
        """
        Test behavior of manage_cookies=True. Once the remote server sends a cookie back, it should
        be included in future requests
        """
        self.client = HTTPClient(manage_cookies=True)

        def assert_no_cookie(req_handler):
            return 'Cookie' not in req_handler.headers

        def assert_cookie(req_handler):
            assert 'Cookie' in req_handler.headers
            cookie_name, cookie_val = req_handler.headers['Cookie'].split(';')[0].split('=')
            assert cookie_name == 'testcookie'
            assert cookie_val == '42'
            return True

        test_requests = [
            (
                {'path': '/', 'req_assert_function': assert_no_cookie},
                {'body': b'nothing', 'headers': {'Set-Cookie': "testcookie=42"}}
            ),
            (
                {'path': '/', 'req_assert_function': assert_cookie},
                {'body': b'nothing'}
            )
        ]
        with mock_httpd(TESTSERVER_ADDRESS, test_requests):
            self.client.open(TESTSERVER_URL + '/')
            self.client.open(TESTSERVER_URL + '/')


# root certificates for google.com, if no ca-certificates.cert
# file is found
GOOGLE_ROOT_CERT = b"""
-----BEGIN CERTIFICATE-----
MIIDVDCCAjygAwIBAgIDAjRWMA0GCSqGSIb3DQEBBQUAMEIxCzAJBgNVBAYTAlVT
MRYwFAYDVQQKEw1HZW9UcnVzdCBJbmMuMRswGQYDVQQDExJHZW9UcnVzdCBHbG9i
YWwgQ0EwHhcNMDIwNTIxMDQwMDAwWhcNMjIwNTIxMDQwMDAwWjBCMQswCQYDVQQG
EwJVUzEWMBQGA1UEChMNR2VvVHJ1c3QgSW5jLjEbMBkGA1UEAxMSR2VvVHJ1c3Qg
R2xvYmFsIENBMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2swYYzD9
9BcjGlZ+W988bDjkcbd4kdS8odhM+KhDtgPpTSEHCIjaWC9mOSm9BXiLnTjoBbdq
fnGk5sRgprDvgOSJKA+eJdbtg/OtppHHmMlCGDUUna2YRpIuT8rxh0PBFpVXLVDv
iS2Aelet8u5fa9IAjbkU+BQVNdnARqN7csiRv8lVK83Qlz6cJmTM386DGXHKTubU
1XupGc1V3sjs0l44U+VcT4wt/lAjNvxm5suOpDkZALeVAjmRCw7+OC7RHQWa9k0+
bw8HHa8sHo9gOeL6NlMTOdReJivbPagUvTLrGAMoUgRx5aszPeE4uwc2hGKceeoW
MPRfwCvocWvk+QIDAQABo1MwUTAPBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBTA
ephojYn7qwVkDBF9qn1luMrMTjAfBgNVHSMEGDAWgBTAephojYn7qwVkDBF9qn1l
uMrMTjANBgkqhkiG9w0BAQUFAAOCAQEANeMpauUvXVSOKVCUn5kaFOSPeCpilKIn
Z57QzxpeR+nBsqTP3UEaBU6bS+5Kb1VSsyShNwrrZHYqLizz/Tt1kL/6cdjHPTfS
tQWVYrmm3ok9Nns4d0iXrKYgjy6myQzCsplFAMfOEVEiIuCl6rYVSAlk6l5PdPcF
PseKUgzbFbS9bZvlxrFUaKnjaZC2mqUPuLk/IH2uSrW4nOQdtqvmlKXBx4Ot2/Un
hw4EbNX/3aBd7YdStysVAq45pmp06drE57xNNB6pXE0zX5IJL4hmXXeXxx12E6nV
5fEWCRE11azbJHFwLJhWC9kXtNHjUStedejV0NxPNO3CBWaAocvmMw==
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIIDujCCAqKgAwIBAgILBAAAAAABD4Ym5g0wDQYJKoZIhvcNAQEFBQAwTDEgMB4G
A1UECxMXR2xvYmFsU2lnbiBSb290IENBIC0gUjIxEzARBgNVBAoTCkdsb2JhbFNp
Z24xEzARBgNVBAMTCkdsb2JhbFNpZ24wHhcNMDYxMjE1MDgwMDAwWhcNMjExMjE1
MDgwMDAwWjBMMSAwHgYDVQQLExdHbG9iYWxTaWduIFJvb3QgQ0EgLSBSMjETMBEG
A1UEChMKR2xvYmFsU2lnbjETMBEGA1UEAxMKR2xvYmFsU2lnbjCCASIwDQYJKoZI
hvcNAQEBBQADggEPADCCAQoCggEBAKbPJA6+Lm8omUVCxKs+IVSbC9N/hHD6ErPL
v4dfxn+G07IwXNb9rfF73OX4YJYJkhD10FPe+3t+c4isUoh7SqbKSaZeqKeMWhG8
eoLrvozps6yWJQeXSpkqBy+0Hne/ig+1AnwblrjFuTosvNYSuetZfeLQBoZfXklq
tTleiDTsvHgMCJiEbKjNS7SgfQx5TfC4LcshytVsW33hoCmEofnTlEnLJGKRILzd
C9XZzPnqJworc5HGnRusyMvo4KD0L5CLTfuwNhv2GXqF4G3yYROIXJ/gkwpRl4pa
zq+r1feqCapgvdzZX99yqWATXgAByUr6P6TqBwMhAo6CygPCm48CAwEAAaOBnDCB
mTAOBgNVHQ8BAf8EBAMCAQYwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUm+IH
V2ccHsBqBt5ZtJot39wZhi4wNgYDVR0fBC8wLTAroCmgJ4YlaHR0cDovL2NybC5n
bG9iYWxzaWduLm5ldC9yb290LXIyLmNybDAfBgNVHSMEGDAWgBSb4gdXZxwewGoG
3lm0mi3f3BmGLjANBgkqhkiG9w0BAQUFAAOCAQEAmYFThxxol4aR7OBKuEQLq4Gs
J0/WwbgcQ3izDJr86iw8bmEbTUsp9Z8FHSbBuOmDAGJFtqkIk7mpM0sYmsL4h4hO
291xNBrBVNpGP+DTKqttVCL1OmLNIG+6KYnX3ZHu01yiPqFbQfXf5WRDLenVOavS
ot+3i9DAgBkcRcAtjOj4LaR0VknFBbVPFd5uRHg5h6h+u/N5GJG79G+dwfCMNYxd
AfvDbbnvRG15RjF+Cv6pgsH/76tuIMRQyV+dTZsXjAzlAcmgQWpzU/qlULRuJQ/7
TBj0/VLZjmmx6BEP3ojY+x1J96relc8geMJgEtslQIxq/H5COEBkEveegeGTLg==
-----END CERTIFICATE-----
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

class TestTileClient(object):
    def test_tc_path(self):
        template = TileURLTemplate(TESTSERVER_URL + '/%(tc_path)s.png')
        client = TileClient(template)
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/09/000/000/005/000/000/013.png'},
                                              {'body': b'tile',
                                               'headers': {'content-type': 'image/png'}})]):
            resp = client.get_tile((5, 13, 9)).source.read()
            assert resp == b'tile'

    def test_quadkey(self):
        template = TileURLTemplate(TESTSERVER_URL + '/key=%(quadkey)s&format=%(format)s')
        client = TileClient(template)
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/key=000002303&format=png'},
                                              {'body': b'tile',
                                               'headers': {'content-type': 'image/png'}})]):
            resp = client.get_tile((5, 13, 9)).source.read()
            assert resp == b'tile'
    def test_xyz(self):
        template = TileURLTemplate(TESTSERVER_URL + '/x=%(x)s&y=%(y)s&z=%(z)s&format=%(format)s')
        client = TileClient(template)
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/x=5&y=13&z=9&format=png'},
                                              {'body': b'tile',
                                               'headers': {'content-type': 'image/png'}})]):
            resp = client.get_tile((5, 13, 9)).source.read()
            assert resp == b'tile'

    def test_arcgiscache_path(self):
        template = TileURLTemplate(TESTSERVER_URL + '/%(arcgiscache_path)s.png')
        client = TileClient(template)
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/L09/R0000000d/C00000005.png'},
                                              {'body': b'tile',
                                               'headers': {'content-type': 'image/png'}})]):
            resp = client.get_tile((5, 13, 9)).source.read()
            assert resp == b'tile'

    def test_bbox(self):
        grid = tile_grid(4326)
        template = TileURLTemplate(TESTSERVER_URL + '/service?BBOX=%(bbox)s')
        client = TileClient(template, grid=grid)
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/service?BBOX=-180.00000000,0.00000000,-90.00000000,90.00000000'},
                                              {'body': b'tile',
                                               'headers': {'content-type': 'image/png'}})]):
            resp = client.get_tile((0, 1, 2)).source.read()
            assert resp == b'tile'


class TestWMSClient(object):
    def test_no_image(self, caplog):
        try:
            with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/service?map=foo&layers=foo&transparent=true&bbox=-200000,-200000,200000,200000&width=512&height=512&srs=EPSG%3A900913&format=image%2Fpng&request=GetMap&version=1.1.1&service=WMS&styles='},
                                                  {'status': '200', 'body': b'x' * 1000,
                                                   'headers': {'content-type': 'application/foo'},
                                                  })]):
                req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
                                        param={'layers':'foo', 'transparent': 'true'})
                query = MapQuery((-200000, -200000, 200000, 200000), (512, 512), SRS(900913), 'png')
                wms = WMSClient(req).retrieve(query, 'png')
        except SourceError:
            assert len(caplog.record_tuples) == 1
            assert ("'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' [output truncated]"
                in caplog.record_tuples[0][2])
        else:
            assert False, 'expected no image returned error'


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
        assert combined.request_template.params.layers == ['foo', 'bar']
        assert combined.request_template.url == TESTSERVER_URL + '/service?map=foo'

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
        wms = WMSInfoClient(req, http_client=http, supported_srs=SupportedSRS([SRS(25832)]))
        fi_req = InfoQuery((8, 50, 9, 51), (512, 512),
                           SRS(4326), (128, 64), 'text/plain')

        wms.get_info(fi_req)

        assert wms_query_eq(http.requested[0],
            TESTSERVER_URL+'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                           '&REQUEST=GetFeatureInfo&SRS=EPSG%3A25832&info_format=text/plain'
                           '&query_layers=foo'
                           '&VERSION=1.1.1&WIDTH=512&HEIGHT=797&STYLES=&x=135&y=101'
                           '&BBOX=428333.552496,5538630.70275,500000.0,5650300.78652'), http.requested[0]

    def test_transform_fi_request(self):
        req = WMS111FeatureInfoRequest(url=TESTSERVER_URL + '/service?map=foo', param={'layers':'foo', 'srs': 'EPSG:25832'})
        http = MockHTTPClient()
        wms = WMSInfoClient(req, http_client=http)
        fi_req = InfoQuery((8, 50, 9, 51), (512, 512),
                           SRS(4326), (128, 64), 'text/plain')

        wms.get_info(fi_req)

        assert wms_query_eq(http.requested[0],
            TESTSERVER_URL+'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                           '&REQUEST=GetFeatureInfo&SRS=EPSG%3A25832&info_format=text/plain'
                           '&query_layers=foo'
                           '&VERSION=1.1.1&WIDTH=512&HEIGHT=797&STYLES=&x=135&y=101'
                           '&BBOX=428333.552496,5538630.70275,500000.0,5650300.78652'), http.requested[0]

class TestWMSMapRequest100(object):
    def setup(self):
        self.r = WMS100MapRequest(param=dict(layers='foo', version='1.1.1', request='GetMap'))
        self.r.params = self.r.adapt_params_to_version()
    def test_version(self):
        assert self.r.params['WMTVER'] == '1.0.0'
        assert 'VERSION' not in self.r.params
    def test_service(self):
        assert 'SERVICE' not in self.r.params
    def test_request(self):
        assert self.r.params['request'] == 'map'
    def test_str(self):
        assert_query_eq(str(self.r.params), 'layers=foo&styles=&request=map&wmtver=1.0.0')

class TestWMSMapRequest130(object):
    def setup(self):
        self.r = WMS130MapRequest(param=dict(layers='foo', WMTVER='1.0.0'))
        self.r.params = self.r.adapt_params_to_version()
    def test_version(self):
        assert self.r.params['version'] == '1.3.0'
        assert 'WMTVER' not in self.r.params
    def test_service(self):
        assert self.r.params['service'] == 'WMS'
    def test_request(self):
        assert self.r.params['request'] == 'GetMap'
    def test_str(self):
        query_eq(str(self.r.params), 'layers=foo&styles=&service=WMS&request=GetMap&version=1.3.0')

class TestWMSMapRequest111(object):
    def setup(self):
        self.r = WMS111MapRequest(param=dict(layers='foo', WMTVER='1.0.0'))
        self.r.params = self.r.adapt_params_to_version()
    def test_version(self):
        assert self.r.params['version'] == '1.1.1'
        assert 'WMTVER' not in self.r.params
