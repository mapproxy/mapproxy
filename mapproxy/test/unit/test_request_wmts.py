from mapproxy.request.wmts import wmts_request, WMTSCapabilitiesRequest
from mapproxy.request.base import url_decode

from nose.tools import eq_

def dummy_req(url):
    return DummyRequest(url_decode(url.replace('\n', '')))

class DummyRequest(object):
    def __init__(self, args, url=''):
        self.args = args
        self.base_url = url

def test_tile_request():
    url = '''requeST=GetTile&service=wmts&tileMatrixset=EPSG900913&
tilematrix=2&tileROW=4&TILECOL=2&FORMAT=image/png&Style=&layer=Foo&version=1.0.0'''
    req = wmts_request(dummy_req(url))
    
    eq_(req.params.coord, (2, 4, '2'))
    eq_(req.params.layer, 'Foo')
    eq_(req.params.format, 'png')

def test_capabilities_request():
    url = '''requeST=GetCapabilities&service=wmts'''
    req = wmts_request(dummy_req(url))
    
    assert isinstance(req, WMTSCapabilitiesRequest)
    