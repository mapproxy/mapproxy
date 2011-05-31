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

from mapproxy.srs import SRS
from mapproxy.request.base import url_decode, Request, NoCaseMultiDict, RequestParams
from mapproxy.request.tile import TMSRequest, tile_request, TileRequest
from mapproxy.request.wms import (wms_request, WMSMapRequest, WMSMapRequestParams,
                              WMS111MapRequest, WMS100MapRequest, WMS130MapRequest,
                              WMS111FeatureInfoRequest)
from mapproxy.exception import RequestError
from mapproxy.request.wms.exception import (WMS111ExceptionHandler, WMSImageExceptionHandler,
                                     WMSBlankExceptionHandler)
from mapproxy.test.http import make_wsgi_env, assert_url_eq, assert_query_eq

import pickle
from nose.tools import eq_

class TestNoCaseMultiDict(object):
    def test_from_iterable(self):
        data = (('layers', 'foo,bar'), ('laYERs', 'baz'), ('crs', 'EPSG:4326'))
        nc_dict = NoCaseMultiDict(data)
        print nc_dict
        
        for name in ('layers', 'LAYERS', 'lAYeRS'):
            assert name in nc_dict, name + ' not found'
        assert nc_dict.get_all('layers') == ['foo,bar', 'baz']
        assert nc_dict.get_all('crs') == ['EPSG:4326']
    
    def test_from_dict(self):
        data = [('layers', 'foo,bar'), ('laYERs', 'baz'), ('crs', 'EPSG:4326')]
        nc_dict = NoCaseMultiDict(data)
        print nc_dict
        
        for name in ('layers', 'LAYERS', 'lAYeRS'):
            assert name in nc_dict, name + ' not found'
        assert nc_dict.get_all('layers') == ['foo,bar', 'baz']
        assert nc_dict.get_all('crs') == ['EPSG:4326']
    
    def test_iteritems(self):
        data = dict([('LAYERS', 'foo,bar'), ('laYERs', 'baz'), ('crs', 'EPSG:4326')])
        nc_dict = NoCaseMultiDict(data)
        print nc_dict
    
        itr = nc_dict.iteritems()
        key, values = itr.next()
        assert key == 'LAYERS' and values == ['foo,bar', 'baz']
        key, values = itr.next()
        assert key == 'crs' and values == ['EPSG:4326']

    def test_multiple_sets(self):
        nc_dict = NoCaseMultiDict()
        nc_dict['foo'] = 'bar'
        assert nc_dict['FOO'] == 'bar'
        nc_dict['foo'] = 'baz'
        assert nc_dict['FOO'] == 'baz'

    def test_missing_key(self):
        nc_dict = NoCaseMultiDict([('foo', 'bar')])
        try:
            nc_dict['bar']
            assert False, 'Did not throw KeyError exception.'
        except KeyError:
            pass

    def test_get(self):
        nc_dict = NoCaseMultiDict([('foo', 'bar'), ('num', '42')])
        assert nc_dict.get('bar') == None
        assert nc_dict.get('bar', 'default_bar') == 'default_bar'
        assert nc_dict.get('num') == '42'
        assert nc_dict.get('num', type_func=int) == 42
        assert nc_dict.get('foo') == 'bar'
    
    def test_get_all(self):
        nc_dict = NoCaseMultiDict([('foo', 'bar'), ('num', '42'), ('foo', 'biz')])
        assert nc_dict.get_all('bar') == []
        assert nc_dict.get_all('foo') == ['bar', 'biz']
        assert nc_dict.get_all('num') == ['42']
    
    def test_set(self):
        nc_dict = NoCaseMultiDict()
        nc_dict.set('foo', 'bar')
        assert nc_dict.get_all('fOO') == ['bar']
        nc_dict.set('fOo', 'buzz', append=True)
        assert nc_dict.get_all('FOO') == ['bar', 'buzz']
        nc_dict.set('foO', 'bizz')
        assert nc_dict.get_all('FOO') == ['bizz']
        nc_dict.set('foO', ['ham', 'spam'], unpack=True)
        assert nc_dict.get_all('FOO') == ['ham', 'spam']
        nc_dict.set('FoO', ['egg', 'bacon'], append=True, unpack=True)
        assert nc_dict.get_all('FOo') == ['ham', 'spam', 'egg', 'bacon']
    
    def test_setitem(self):
        nc_dict = NoCaseMultiDict()
        nc_dict['foo'] = 'bar'
        assert nc_dict['foo'] == 'bar'
        nc_dict['foo'] = 'buz'
        assert nc_dict['foo'] == 'buz'
        nc_dict['bar'] = nc_dict['foo']
        assert nc_dict['bar'] == 'buz'

        nc_dict['bing'] = '1'
        nc_dict['bong'] = '2'
        nc_dict['bing'] = nc_dict['bong']
        assert nc_dict['bing'] == '2'
        assert nc_dict['bong'] == '2'
    
    def test_del(self):
        nc_dict = NoCaseMultiDict([('foo', 'bar'), ('num', '42')])
        assert nc_dict['fOO'] == 'bar'
        del nc_dict['FOO']
        assert nc_dict.get('foo') == None


class DummyRequest(object):
    def __init__(self, args, url=''):
        self.args = args
        self.base_url = url

class TestWMSMapRequest(object):
    def setup(self):
        self.base_req = url_decode('''SERVICE=WMS&format=image%2Fpng&layers=foo&styles=&
REQUEST=GetMap&height=300&srs=EPSG%3A4326&VERSION=1.1.1&
bbox=7,50,8,51&width=400'''.replace('\n',''))
    
class TestWMS100MapRequest(TestWMSMapRequest):
    def setup(self):
        TestWMSMapRequest.setup(self)
        del self.base_req['service']
        del self.base_req['version']
        self.base_req['wmtver'] = '1.0.0'
        self.base_req['request'] = 'Map'
    
    def test_basic_request(self):
        req = wms_request(DummyRequest(self.base_req), validate=False)
        assert isinstance(req, WMS100MapRequest)
        eq_(req.params.request, 'GetMap')

class TestWMS111MapRequest(TestWMSMapRequest):
    def test_basic_request(self):
        req = wms_request(DummyRequest(self.base_req), validate=False)
        assert isinstance(req, WMS111MapRequest)
        eq_(req.params.request, 'GetMap')

class TestWMS130MapRequest(TestWMSMapRequest):
    def setup(self):
        TestWMSMapRequest.setup(self)
        self.base_req['version'] = '1.3.0'
        self.base_req['crs'] = self.base_req['srs']
        del self.base_req['srs']
        
    def test_basic_request(self):
        req = wms_request(DummyRequest(self.base_req), validate=False)
        assert isinstance(req, WMS130MapRequest)
        eq_(req.params.request, 'GetMap')
        eq_(req.params.bbox, (50.0, 7.0, 51.0, 8.0))
    
    def test_copy_with_request_params(self):
        # check that we allways have our internal axis order
        req1 = WMS130MapRequest(param=dict(bbox="10,0,20,40", crs='EPSG:4326'))
        eq_(req1.params.bbox, (0.0, 10.0, 40.0, 20.0))
        req2 = WMS111MapRequest(param=dict(bbox="0,10,40,20", srs='EPSG:4326'))
        eq_(req2.params.bbox, (0.0, 10.0, 40.0, 20.0))
        
        # 130 <- 111
        req3 = req1.copy_with_request_params(req2)
        eq_(req3.params.bbox, (0.0, 10.0, 40.0, 20.0))
        assert isinstance(req3, WMS130MapRequest)
        
        # 130 <- 130
        req4 = req1.copy_with_request_params(req3)
        eq_(req4.params.bbox, (0.0, 10.0, 40.0, 20.0))
        assert isinstance(req4, WMS130MapRequest)
        
        # 111 <- 130
        req5 = req2.copy_with_request_params(req3)
        eq_(req5.params.bbox, (0.0, 10.0, 40.0, 20.0))
        assert isinstance(req5, WMS111MapRequest)
        
    
class TestWMS111FeatureInfoRequest(TestWMSMapRequest):
    def setup(self):
        TestWMSMapRequest.setup(self)
        self.base_req['request'] = 'GetFeatureInfo'
        self.base_req['x'] = '100'
        self.base_req['y'] = '150'
        self.base_req['query_layers'] = 'foo'
        
    def test_basic_request(self):
        req = wms_request(DummyRequest(self.base_req))#, validate=False)
        assert isinstance(req, WMS111FeatureInfoRequest)
    
    def test_pos(self):
        req = wms_request(DummyRequest(self.base_req))
        eq_(req.params.pos, (100, 150))
    
    def test_pos_coords(self):
        req = wms_request(DummyRequest(self.base_req))
        eq_(req.params.pos_coords, (7.25, 50.5))
        

class TestRequest(object):
    def setup(self):
        self.env = {
         'HTTP_HOST': 'localhost:5050',
         'PATH_INFO': '/service',
         'QUERY_STRING': 'LAYERS=osm_mapnik&FORMAT=image%2Fpng&SPHERICALMERCATOR=true&SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&STYLES=&EXCEPTIONS=application%2Fvnd.ogc.se_inimage&SRS=EPSG%3A900913&bbox=1013566.9382067363,7051939.297837454,1030918.1436243634,7069577.142111099&WIDTH=908&HEIGHT=923',
         'REMOTE_ADDR': '127.0.0.1',
         'REQUEST_METHOD': 'GET',
         'SCRIPT_NAME': '',
         'SERVER_NAME': '127.0.0.1',
         'SERVER_PORT': '5050',
         'SERVER_PROTOCOL': 'HTTP/1.1',
         'wsgi.url_scheme': 'http',
         }        
    def test_path(self):
        req = Request(self.env)
        assert req.path == '/service'
    
    def test_host_url(self):
        req = Request(self.env)
        assert req.host_url == 'http://localhost:5050/'
    
    def test_base_url(self):
        req = Request(self.env)
        assert req.base_url == 'http://localhost:5050/service'
        
        del self.env['HTTP_HOST']
        req = Request(self.env)
        assert req.base_url == 'http://127.0.0.1:5050/service'
        
        self.env['SERVER_PORT'] = '80'
        req = Request(self.env)
        assert req.base_url == 'http://127.0.0.1/service'
        
    def test_query_string(self):
        self.env['QUERY_STRING'] = 'Foo=boo&baz=baa&fOO=bizz'
        req = Request(self.env)
        print req.args['foo']
        assert req.args.get_all('foo') == ['boo', 'bizz']
    def test_query_string_encoding(self):
        env = {
            'QUERY_STRING': 'foo=some%20special%20chars%20%26%20%3D'
        }
        req = Request(env)
        print req.args['foo']
        assert req.args['foo'] == u'some special chars & ='
    
    def test_script_url(self):
        req = Request(self.env)
        eq_(req.script_url, 'http://localhost:5050')
        self.env['SCRIPT_NAME'] = '/'
        req = Request(self.env)
        eq_(req.script_url, 'http://localhost:5050')

        self.env['SCRIPT_NAME'] = '/proxy'
        req = Request(self.env)
        eq_(req.script_url, 'http://localhost:5050/proxy')

        self.env['SCRIPT_NAME'] = '/proxy/'
        req = Request(self.env)
        eq_(req.script_url, 'http://localhost:5050/proxy')
    
    def test_pop_path(self):
        self.env['PATH_INFO'] = '/foo/service'
        req = Request(self.env)
        part = req.pop_path()
        eq_(part, 'foo')
        eq_(self.env['PATH_INFO'], '/service')
        eq_(self.env['SCRIPT_NAME'], '/foo')
        
        part = req.pop_path()
        eq_(part, 'service')
        eq_(self.env['PATH_INFO'], '')
        eq_(self.env['SCRIPT_NAME'], '/foo/service')
    
        part = req.pop_path()
        eq_(part, '')
        eq_(self.env['PATH_INFO'], '')
        eq_(self.env['SCRIPT_NAME'], '/foo/service')
    

def test_maprequest_from_request():
    env = {
        'QUERY_STRING': 'layers=bar&bBOx=-90,-80,70.0,+80&format=image/png&'\
                        'WIdth=100&heIGHT=200&LAyerS=foo'
    }
    req = WMSMapRequest(param=Request(env).args)
    assert req.params.bbox == (-90.0, -80.0, 70.0, 80.0)
    assert req.params.layers == ['bar', 'foo']
    assert req.params.size == (100, 200)

class TestWMSMapRequestParams(object):
    def setup(self):
        self.m = WMSMapRequestParams(url_decode('layers=bar&bBOx=-90,-80,70.0, 80&format=image/png'
                                    '&WIdth=100&heIGHT=200&LAyerS=foo&srs=EPSG%3A0815'))
    def test_empty(self):
        m = WMSMapRequestParams()
        assert m.query_string == ''
    def test_size(self):
        assert self.m.size == (100, 200)
        self.m.size = (250, 350)
        assert self.m.size == (250, 350)
        assert self.m['width'] == '250'
        assert self.m['height'] == '350'
        del self.m['width']
        assert self.m.size == None
    def test_format(self):
        assert self.m.format == 'png'
        assert self.m.format_mime_type == 'image/png'
        self.m['transparent'] = 'True'
        assert self.m.format == 'png'
    def test_bbox(self):
        assert self.m.bbox == (-90.0, -80.0, 70.0, 80.0)
        del self.m['bbox']
        assert self.m.bbox is None
        self.m.bbox = (-90.0, -80.0, 70.0, 80.0)
        assert self.m.bbox == (-90.0, -80.0, 70.0, 80.0)
        self.m.bbox = '0.0, -40.0, 70.0, 80.0'
        assert self.m.bbox == (0.0, -40.0, 70.0, 80.0)
        self.m.bbox = None
        assert self.m.bbox is None
    def test_transparent(self):
        assert self.m.transparent == False
        self.m['transparent'] = 'trUe'
        assert self.m.transparent == True
    def test_transparent_bool(self):
        self.m['transparent'] = True
        assert self.m['transparent'] == 'True'
    def test_bgcolor(self):
        assert self.m.bgcolor == '#ffffff'
        self.m['bgcolor'] = '0x42cafe'
        assert self.m.bgcolor == '#42cafe'
    def test_srs(self):
        print self.m.srs
        assert self.m.srs == 'EPSG:0815'
        del self.m['srs']
        assert self.m.srs is None
        self.m.srs = SRS('EPSG:4326')
        assert self.m.srs == 'EPSG:4326'
    def test_layers(self):
        assert list(self.m.layers) == ['bar', 'foo']
    def test_query_string(self):
        print self.m.query_string
        assert_query_eq(self.m.query_string, 
            'layers=bar,foo&WIdth=100&bBOx=-90,-80,70.0,+80'
            '&format=image%2Fpng&srs=EPSG%3A0815&heIGHT=200')
    def test_get(self):
        assert self.m.get('LAYERS') == 'bar'
        assert self.m.get('width', type_func=int) == 100
    def test_set(self):
        self.m.set('Layers', 'baz', append=True)
        assert self.m.get('LAYERS') == 'bar'
        self.m.set('Layers', 'baz')
        assert self.m.get('LAYERS') == 'baz'
    def test_attr_access(self):
        assert self.m['width'] == '100'
        assert self.m['height'] == '200'
        try:
            self.m.invalid
        except AttributeError:
            pass
        else:
            assert False
    def test_with_defaults(self):
        orig_req = WMSMapRequestParams(param=dict(layers='baz'))
        new_req = self.m.with_defaults(orig_req)
        assert new_req is not self.m
        assert self.m.get('LayErs') == 'bar'
        assert new_req.get('LAyers') == 'baz'
        assert new_req.size == (100, 200)

class TestURLDecode(object):
    def test_key_decode(self):
        d = url_decode('white+space=in+key&foo=bar', decode_keys=True)
        assert d['white space'] == 'in key'
        assert d['foo'] == 'bar'
    def test_include_empty(self):
        d = url_decode('bar&foo=baz&bing', include_empty=True)
        assert d['bar'] == ''
        assert d['foo'] == 'baz'
        assert d['bing'] == ''


def test_non_mime_format():
    m = WMSMapRequest(param={'format': 'jpeg'})
    assert m.params.format == 'jpeg'

def test_request_w_url():
    url = WMSMapRequest(url='http://localhost:8000/service?', param={'layers': 'foo,bar'}).complete_url
    assert_url_eq(url, 'http://localhost:8000/service?layers=foo,bar&styles=&request=GetMap&service=WMS')
    url = WMSMapRequest(url='http://localhost:8000/service',  param={'layers': 'foo,bar'}).complete_url
    assert_url_eq(url, 'http://localhost:8000/service?layers=foo,bar&styles=&request=GetMap&service=WMS')
    url = WMSMapRequest(url='http://localhost:8000/service?map=foo',  param={'layers': 'foo,bar'}).complete_url
    assert_url_eq(url, 'http://localhost:8000/service?map=foo&layers=foo,bar&styles=&request=GetMap&service=WMS')

class TestWMSRequest(object):
    env = make_wsgi_env("""LAYERS=foo&FORMAT=image%2Fjpeg&SERVICE=WMS&VERSION=1.1.1&
REQUEST=GetMap&STYLES=&EXCEPTIONS=application%2Fvnd.ogc.se_xml&SRS=EPSG%3A900913&
BBOX=8,4,9,5&WIDTH=984&HEIGHT=708""".replace('\n', ''))
    def setup(self):
        self.req = Request(self.env)
    def test_valid_request(self):
        map_req = wms_request(self.req)
        # constructor validates
        assert map_req.params.size == (984, 708)
    def test_invalid_request(self):
        del self.req.args['request']
        try:
            wms_request(self.req)
        except RequestError, e:
            assert 'request' in e.msg
        else:
            assert False, 'RequestError expected'
    def test_exception_handler(self):
        map_req = wms_request(self.req)
        assert isinstance(map_req.exception_handler, WMS111ExceptionHandler)
    def test_image_exception_handler(self):
        self.req.args['exceptions'] = 'application/vnd.ogc.se_inimage'
        map_req = wms_request(self.req)
        assert isinstance(map_req.exception_handler, WMSImageExceptionHandler)
    def test_blank_exception_handler(self):
        self.req.args['exceptions'] = 'blank'
        map_req = wms_request(self.req)
        assert isinstance(map_req.exception_handler, WMSBlankExceptionHandler)

class TestSRSAxisOrder(object):
    def setup(self):
        params111 =  url_decode("""LAYERS=foo&FORMAT=image%2Fjpeg&SERVICE=WMS&
VERSION=1.1.1&REQUEST=GetMap&STYLES=&EXCEPTIONS=application%2Fvnd.ogc.se_xml&
SRS=EPSG%3A4326&BBOX=8,4,9,5&WIDTH=984&HEIGHT=708""".replace('\n', ''))
        self.req111 = WMS111MapRequest(params111)
        self.params130 = params111.copy()
        self.params130['version'] = '1.3.0'
        self.params130['crs'] = self.params130['srs']
        del self.params130['srs']
    def test_111_order(self):
        eq_(self.req111.params.bbox, (8, 4, 9, 5))
    def test_130_order_geog(self):
        req130 = WMS130MapRequest(self.params130)
        eq_(req130.params.bbox, (4, 8, 5, 9))
        self.params130['crs'] = 'EPSG:4258'
        req130 = WMS130MapRequest(self.params130)
        eq_(req130.params.bbox, (4, 8, 5, 9))
    def test_130_order_geog_old(self):
        self.params130['crs'] = 'CRS:84'
        req130 = WMS130MapRequest(self.params130)
        eq_(req130.params.bbox, (8, 4, 9, 5))
    def test_130_order_proj_north_east(self):
        self.params130['crs'] = 'EPSG:31466'
        req130 = WMS130MapRequest(self.params130)
        eq_(req130.params.bbox, (4, 8, 5, 9))
    def test_130_order_proj(self):
        self.params130['crs'] = 'EPSG:31463'
        req130 = WMS130MapRequest(self.params130)
        eq_(req130.params.bbox, (8, 4, 9, 5))
        
class TestTileRequest(object):
    def test_tms_request(self):
        env = {
            'PATH_INFO': '/tms/1.0.0/osm/5/2/3.png',
            'QUERY_STRING': '',
        }
        req = Request(env)
        tms = tile_request(req)
        assert isinstance(tms, TMSRequest)
        eq_(tms.tile, (2, 3, 5))
        eq_(tms.format, 'png')
        eq_(tms.layer, 'osm')

    def test_tile_request(self):
        env = {
            'PATH_INFO': '/tiles/1.0.0/osm/5/2/3.png',
            'QUERY_STRING': '',
        }
        req = Request(env)
        tile_req = tile_request(req)
        assert isinstance(tile_req, TileRequest)
        eq_(tile_req.tile, (2, 3, 5))
        eq_(tile_req.origin, 'sw')
        eq_(tile_req.format, 'png')
        eq_(tile_req.layer, 'osm')

    def test_tile_request_flipped_y(self):
        env = {
            'PATH_INFO': '/tiles/1.0.0/osm/5/2/3.png',
            'QUERY_STRING': 'origin=nw',
        }
        req = Request(env)
        tile_req = tile_request(req)
        assert isinstance(tile_req, TileRequest)
        eq_(tile_req.tile, (2, 3, 5)) # not jet flipped
        eq_(tile_req.origin, 'nw')
        eq_(tile_req.format, 'png')
        eq_(tile_req.layer, 'osm')
        
    def test_tile_request_w_epsg(self):
        env = {
            'PATH_INFO': '/tiles/1.0.0/osm/EPSG4326/5/2/3.png',
            'QUERY_STRING': '',
        }
        req = Request(env)
        tile_req = tile_request(req)
        assert isinstance(tile_req, TileRequest)
        eq_(tile_req.tile, (2, 3, 5))
        eq_(tile_req.format, 'png')
        eq_(tile_req.layer, 'osm_EPSG4326')

def test_request_params_pickle():
    params = RequestParams(dict(foo='bar', zing='zong'))
    params2 = pickle.loads(pickle.dumps(params, 2))
    assert params.params == params2.params
    
