# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

from mapproxy.request.wmts import wmts_request, WMTS100CapabilitiesRequest
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
    eq_(req.params.tilematrixset, 'EPSG900913')

def test_capabilities_request():
    url = '''requeST=GetCapabilities&service=wmts'''
    req = wmts_request(dummy_req(url))
    
    assert isinstance(req, WMTS100CapabilitiesRequest)
    