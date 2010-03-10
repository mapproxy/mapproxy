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
from mapproxy.core.client import HTTPClient, HTTPClientError
from mapproxy.core.client import TMSClient
from mapproxy.wms.client import WMSClient
from mapproxy.wms.request import wms_request, WMS111MapRequest, WMS100MapRequest,\
                                 WMS130MapRequest
from mapproxy.core.srs import bbox_equals
from mapproxy.core.request import Request, url_decode
from mapproxy.tests.http import mock_httpd, query_eq, make_wsgi_env
from mapproxy.tests.helper import assert_re

from nose.tools import eq_

TESTSERVER_ADDRESS = ('127.0.0.1', 56413)
TESTSERVER_URL = 'http://%s:%s' % TESTSERVER_ADDRESS

class TestHTTPClient(object):
    def setup(self):
        self.client = HTTPClient()
    def test_internal_error_response(self):
        try:
            with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/'},
                                                  {'status': '500', 'body': ''})]):
                self.client.open(TESTSERVER_URL + '/')
        except HTTPClientError, e:
            assert_re(e.message, r'HTTP Error \(.*\): 500')
        else:
            assert False, 'expected HTTPClientError'
    def test_invalid_url_type(self):
        try:
            self.client.open('htp://example.org')
        except HTTPClientError, e:
            assert_re(e.message, r'No response .* \(htp://example.*\): unknown url type')
        else:
            assert False, 'expected HTTPClientError'
    def test_invalid_url(self):
        try:
            self.client.open('this is not a url')
        except HTTPClientError, e:
            assert_re(e.message, r'URL not correct \(this is not.*\): unknown url type')
        else:
            assert False, 'expected HTTPClientError'
    def test_unknown_host(self):
        try:
            self.client.open('http://thishostshouldnotexist000136really42.org')
        except HTTPClientError, e:
            assert_re(e.message, r'No response .* \(http://thishost.*\): .*')
        else:
            assert False, 'expected HTTPClientError'
    def test_no_connect(self):
        try:
            self.client.open('http://localhost:53871')
        except HTTPClientError, e:
            assert_re(e.message, r'No response .* \(http://localhost.*\): Connection refused')
        else:
            assert False, 'expected HTTPClientError'
    def test_internal_error(self):
        try:
            self.client.open('http://localhost:53871', invalid_key='argument')
        except HTTPClientError, e:
            assert_re(e.message, r'Internal HTTP error \(http://localhost.*\): TypeError')
        else:
            assert False, 'expected HTTPClientError'
    

class TestWMSClient(object):
    def setup(self):
        self.req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo')
        self.wms = WMSClient(self.req)
    def test_request(self):
        expected_req = ({'path': r'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326'
                                  '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,90.0&WIDTH=512&STYLES='},
                        {'body': 'no image', 'headers': {'content-type': 'image/png'}})
        with mock_httpd(TESTSERVER_ADDRESS, [expected_req]):
            req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
                                   param={'layers': 'foo', 'bbox': '-180.0,-90.0,180.0,90.0'})
            req.params.size = (512, 256)
            req.params['format'] = 'image/png'
            req.params['srs'] = 'EPSG:4326'
            resp = self.wms.get_map(req)
    def test_get_tile_non_image_content_type(self):
        expected_req = ({'path': r'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&STYLES='
                                  '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,90.0&WIDTH=512'},
                        {'body': 'error', 'headers': {'content-type': 'text/plain'}})
        with mock_httpd(TESTSERVER_ADDRESS, [expected_req]):
            try:
                req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
                                       param={'layers': 'foo', 'bbox': '-180.0,-90.0,180.0,90.0'})
                req.params.size = (512, 256)
                req.params['format'] = 'image/png'
                req.params['srs'] = 'EPSG:4326'
                resp = self.wms.get_map(req)
            except HTTPClientError, e:
                assert_re(e.message, r'response is not an image')
            else:
                assert False, 'expected HTTPClientError'
    
    def test__transform_fi_request(self):
        default_req = WMS111MapRequest(url_decode('srs=EPSG%3A4326'))
        fi_req = Request(make_wsgi_env('''LAYERS=mapserver_cache&
         QUERY_LAYERS=mapnik_mapserver&X=601&Y=528&FORMAT=image%2Fpng&SERVICE=WMS&
         VERSION=1.1.1&REQUEST=GetFeatureInfo&STYLES=&
         EXCEPTIONS=application%2Fvnd.ogc.se_inimage&SRS=EPSG%3A900913&
         BBOX=730930.9303206909,6866851.379301955,1031481.3254841676,7170153.507483206&
         WIDTH=983&HEIGHT=992'''.replace('\n', '').replace(' ', '')))
        wms_client = WMSClient(default_req)
        orig_req = wms_request(fi_req)
        req = wms_request(fi_req)
        wms_client._transform_fi_request(req)
        
        eq_(req.params.srs, 'EPSG:4326')
        eq_(req.params.pos, (601, 523))

        default_req = WMS111MapRequest(url_decode('srs=EPSG%3A900913'))
        wms_client = WMSClient(default_req)
        wms_client._transform_fi_request(req)
        
        eq_(req.params.srs, 'EPSG:900913')
        eq_(req.params.pos, (601, 528))
        assert bbox_equals(orig_req.params.bbox, req.params.bbox, 0.1)
        
class TestTMSClient(object):
    def setup(self):
        self.client = TMSClient(TESTSERVER_URL)
    def test_get_tile(self):
        with mock_httpd(TESTSERVER_ADDRESS, [({'path': '/9/5/13.png'},
                                                {'body': 'tile', 'headers': {'content-type': 'image/png'}})]):
            resp = self.client.get_tile((5, 13, 9)).read()
            eq_(resp, 'tile')

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
        eq_(str(self.r.params), 'layers=foo&styles=&request=map&wmtver=1.0.0')

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