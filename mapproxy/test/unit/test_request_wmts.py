# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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
    