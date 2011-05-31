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

from __future__ import with_statement, division

from mapproxy.test.system import module_setup, module_teardown, SystemTest
from nose.tools import eq_

test_config = {}

def setup_module():
    module_setup(test_config, 'auth.yaml')

def teardown_module():
    module_teardown(test_config)

TESTSERVER_ADDRESS = 'localhost', 42423
CAPABILITIES_REQ = "/service?request=GetCapabilities&service=WMS&Version=1.1.1"
MAP_REQ = ("/service?request=GetMap&service=WMS&Version=1.1.1&SRS=EPSG:4326"
    "&BBOX=-80,-40,0,0&WIDTH=200&HEIGHT=100&styles=&FORMAT=image/png&")


class TestWMSAuth(SystemTest):
    config = test_config

    # ###
    # see mapproxy.test.unit.test_auth for WMS GetMap request tests
    # ###
    
    def test_capabilities_authorize_all(self):
        def auth(service, layers, **kw):
            eq_(service, 'wms.capabilities')
            eq_(len(layers), 7)
            return {'authorized': 'full'}
        
        resp = self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(xml.xpath('//Layer/Name/text()'), ['layer1', 'layer1a', 'layer1b', 'layer2', 'layer2a', 'layer2b', 'layer2b1'])

    def test_capabilities_authorize_none(self):
        def auth(service, layers, **kw):
            eq_(service, 'wms.capabilities')
            eq_(len(layers), 7)
            return {'authorized': 'none'}
        self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth}, status=403)

    def test_capabilities_unauthenticated(self):
        def auth(service, layers, **kw):
            eq_(service, 'wms.capabilities')
            eq_(len(layers), 7)
            return {'authorized': 'unauthenticated'}
        self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth}, status=401)

    def test_capabilities_authorize_partial(self):
        def auth(service, layers, **kw):
            eq_(service, 'wms.capabilities')
            eq_(len(layers), 7)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1a': {'map': True},
                    'layer2': {'map': True},
                    'layer2b': {'map': True},
                    'layer2b1': {'map': True},
                }
            }
        resp = self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        # layer1a not included cause root layer (layer1) is not permitted
        eq_(xml.xpath('//Layer/Name/text()'), ['layer2', 'layer2b', 'layer2b1'])
    
    def test_capabilities_authorize_partial_with_fi(self):
        def auth(service, layers, **kw):
            eq_(service, 'wms.capabilities')
            eq_(len(layers), 7)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'map': True},
                    'layer1a': {'map': True},
                    'layer2': {'map': True, 'featureinfo': True},
                }
            }
        resp = self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(xml.xpath('//Layer/Name/text()'), ['layer1', 'layer1a', 'layer2'])
    
    def test_get_map_authorized(self):
        def auth(service, layers, query_extent, **kw):
            eq_(query_extent, ('EPSG:4326', (-80.0, -40.0, 0.0, 0.0)))
            eq_(service, 'wms.map')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'map': True},
                }
            }
        resp = self.app.get(MAP_REQ + 'layers=layer1', extra_environ={'mapproxy.authorize': auth})
        eq_(resp.content_type, 'image/png')

    def test_get_map_authorized_none(self):
        def auth(service, layers, query_extent, **kw):
            eq_(query_extent, ('EPSG:4326', (-80.0, -40.0, 0.0, 0.0)))
            eq_(service, 'wms.map')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'map': False},
                }
            }
        self.app.get(MAP_REQ + 'layers=layer1', extra_environ={'mapproxy.authorize': auth}, status=403)


TMS_CAPABILITIES_REQ = '/tms/1.0.0'

class TestTMSAuth(SystemTest):
    config = test_config

    def test_capabilities_authorize_all(self):
        def auth(service, layers, environ, **kw):
            eq_(environ['PATH_INFO'], '/tms/1.0.0')
            eq_(service, 'tms')
            eq_(len(layers), 5)
            return {'authorized': 'full'}
        
        resp = self.app.get(TMS_CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(xml.xpath('//TileMap/@title'), ['layer 1a', 'layer 1b', 'layer 1', 'layer 2a', 'layer 2b1'])

    def test_capabilities_authorize_none(self):
        def auth(service, layers, **kw):
            eq_(service, 'tms')
            eq_(len(layers), 5)
            return {'authorized': 'none'}
    
    def test_capabilities_unauthenticated(self):
        def auth(service, layers, **kw):
            eq_(service, 'tms')
            eq_(len(layers), 5)
            return {'authorized': 'unauthenticated'}
        self.app.get(TMS_CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth}, status=401)

    def test_capabilities_authorize_partial(self):
        def auth(service, layers, **kw):
            eq_(service, 'tms')
            eq_(len(layers), 5)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1a': {'tile': True},
                    'layer1b': {'tile': False},
                    'layer2': {'tile': True},
                    'layer2b': {'tile': True},
                    'layer2b1': {'tile': True},
                }
            }
        resp = self.app.get(TMS_CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(xml.xpath('//TileMap/@title'), ['layer 1a', 'layer 2b1'])

    def test_layer_capabilities_authorize_none(self):
        def auth(service, layers, **kw):
            eq_(service, 'tms')
            eq_(len(layers), 1)
            return {
                'authorized': 'none',
            }
        self.app.get(TMS_CAPABILITIES_REQ + '/layer1', extra_environ={'mapproxy.authorize': auth}, status=403)

    def test_layer_capabilities_authorize_all(self):
        def auth(service, layers, **kw):
            eq_(service, 'tms')
            eq_(len(layers), 1)
            return {
                'authorized': 'full',
            }
        resp = self.app.get(TMS_CAPABILITIES_REQ + '/layer1', extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(xml.xpath('//TileMap/Title/text()'), ['layer 1'])
    
    def test_layer_capabilities_authorize_partial(self):
        def auth(service, layers, **kw):
            eq_(service, 'tms')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'tile': True},
                }
            }
        resp = self.app.get(TMS_CAPABILITIES_REQ + '/layer1', extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(xml.xpath('//TileMap/Title/text()'), ['layer 1'])
    
    def test_layer_capabilities_deny_partial(self):
        def auth(service, layers, **kw):
            eq_(service, 'tms')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'tile': False},
                }
            }
        self.app.get(TMS_CAPABILITIES_REQ + '/layer1', extra_environ={'mapproxy.authorize': auth}, status=403)
    
    def test_get_tile(self):
        def auth(service, layers, environ, **kw):
            eq_(environ['PATH_INFO'], '/tms/1.0.0/layer1/0/0/0.png')
            eq_(service, 'tms')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'tile': True},
                }
            }
        resp = self.app.get(TMS_CAPABILITIES_REQ + '/layer1/0/0/0.png', extra_environ={'mapproxy.authorize': auth})
        eq_(resp.content_type, 'image/png')
        assert resp.content_length > 1000

    def test_get_tile_authorize_none(self):
        def auth(service, layers, **kw):
            eq_(service, 'tms')
            eq_(len(layers), 1)
            return {
                'authorized': 'none',
            }
        self.app.get(TMS_CAPABILITIES_REQ + '/layer1/0/0/0.png', extra_environ={'mapproxy.authorize': auth}, status=403)
    

class TestKMLAuth(SystemTest):
    config = test_config

    def test_superoverlay_authorize_all(self):
        def auth(service, layers, environ, **kw):
            eq_(environ['PATH_INFO'], '/kml/layer1/0/0/0.kml')
            eq_(service, 'kml')
            eq_(len(layers), 1)
            return {'authorized': 'full'}
        
        resp = self.app.get('/kml/layer1/0/0/0.kml', extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(xml.xpath('kml:Document/kml:name/text()', namespaces={'kml': 'http://www.opengis.net/kml/2.2'}), ['layer1'])

    def test_superoverlay_authorize_none(self):
        def auth(service, layers, **kw):
            eq_(service, 'kml')
            eq_(len(layers), 1)
            return {'authorized': 'none'}
        
        self.app.get('/kml/layer1/0/0/0.kml', extra_environ={'mapproxy.authorize': auth}, status=403)

    def test_superoverlay_unauthenticated(self):
        def auth(service, layers, **kw):
            eq_(service, 'kml')
            eq_(len(layers), 1)
            return {'authorized': 'unauthenticated'}
        
        self.app.get('/kml/layer1/0/0/0.kml', extra_environ={'mapproxy.authorize': auth}, status=401)

    def test_superoverlay_authorize_partial(self):
        def auth(service, layers, **kw):
            eq_(service, 'kml')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'tile': True},
                }
            }        
        resp = self.app.get('/kml/layer1/0/0/0.kml', extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(xml.xpath('kml:Document/kml:name/text()', namespaces={'kml': 'http://www.opengis.net/kml/2.2'}), ['layer1'])

    def test_superoverlay_deny_partial(self):
        def auth(service, layers, **kw):
            eq_(service, 'kml')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'tile': False},
                }
            }        
        self.app.get('/kml/layer1/0/0/0.kml', extra_environ={'mapproxy.authorize': auth}, status=403)

class TestDemoAuth(SystemTest):
    config = test_config

    def test_authorize_all(self):
        def auth(service, layers, environ, **kw):
            return {'authorized': 'full'}
        self.app.get('/demo', extra_environ={'mapproxy.authorize': auth})

    def test_authorize_none(self):
        def auth(service, layers, environ, **kw):
            return {'authorized': 'none'}
        self.app.get('/demo', extra_environ={'mapproxy.authorize': auth}, status=403)

    def test_unauthenticated(self):
        def auth(service, layers, environ, **kw):
            return {'authorized': 'unauthenticated'}
        self.app.get('/demo', extra_environ={'mapproxy.authorize': auth}, status=401)

    def test_superoverlay_authorize_none(self):
        def auth(service, layers, **kw):
            eq_(service, 'kml')
            eq_(len(layers), 1)
            return {'authorized': 'none'}
        
        self.app.get('/kml/layer1/0/0/0.kml', extra_environ={'mapproxy.authorize': auth}, status=403)

    def test_superoverlay_unauthenticated(self):
        def auth(service, layers, **kw):
            eq_(service, 'kml')
            eq_(len(layers), 1)
            return {'authorized': 'unauthenticated'}
        
        self.app.get('/kml/layer1/0/0/0.kml', extra_environ={'mapproxy.authorize': auth}, status=401)

