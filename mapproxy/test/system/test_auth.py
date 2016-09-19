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
from mapproxy.test.image import img_from_buf, create_tmp_image, is_transparent
from mapproxy.test.http import MockServ
from nose.tools import eq_
from mapproxy.util.geom import geom_support
from mapproxy.srs import bbox_equals


test_config = {}

def setup_module():
    module_setup(test_config, 'auth.yaml')

def teardown_module():
    module_teardown(test_config)

TESTSERVER_ADDRESS = 'localhost', 42423
CAPABILITIES_REQ = "/service?request=GetCapabilities&service=WMS&Version=1.1.1"
MAP_REQ = ("/service?request=GetMap&service=WMS&Version=1.1.1&SRS=EPSG:4326"
    "&BBOX=-80,-40,0,0&WIDTH=200&HEIGHT=100&styles=&FORMAT=image/png&")
FI_REQ = ("/service?request=GetFeatureInfo&service=WMS&Version=1.1.1&SRS=EPSG:4326"
    "&BBOX=-80,-40,0,0&WIDTH=200&HEIGHT=100&styles=&FORMAT=image/png&X=10&Y=10&")

if not geom_support:
    from nose.plugins.skip import SkipTest
    raise SkipTest('requires Shapely')

class TestWMSAuth(SystemTest):
    config = test_config

    # ###
    # see mapproxy.test.unit.test_auth for WMS GetMap request tests
    # ###
    def test_capabilities_authorize_all(self):
        def auth(service, layers, **kw):
            eq_(service, 'wms.capabilities')
            eq_(len(layers), 8)
            return {'authorized': 'full'}

        resp = self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(xml.xpath('//Layer/Name/text()'), ['layer1', 'layer1a', 'layer1b', 'layer2', 'layer2a', 'layer2b', 'layer2b1', 'layer3'])

    def test_capabilities_authorize_none(self):
        def auth(service, layers, **kw):
            eq_(service, 'wms.capabilities')
            eq_(len(layers), 8)
            return {'authorized': 'none'}
        self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth}, status=403)

    def test_capabilities_unauthenticated(self):
        def auth(service, layers, **kw):
            eq_(service, 'wms.capabilities')
            eq_(len(layers), 8)
            return {'authorized': 'unauthenticated'}
        self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth}, status=401)

    def test_capabilities_authorize_partial(self):
        def auth(service, layers, **kw):
            eq_(service, 'wms.capabilities')
            eq_(len(layers), 8)
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

    def test_capabilities_authorize_partial_limited_to(self):
        def auth(service, layers, **kw):
            eq_(service, 'wms.capabilities')
            eq_(len(layers), 8)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1a': {'map': True},
                    'layer2': {'map': True, 'limited_to': {'srs': 'EPSG:4326', 'geometry': [-40.0, -50.0, 0.0, 5.0]}},
                    'layer2b': {'map': True},
                    'layer2b1': {'map': True},
                }
            }
        resp = self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        # layer1a not included cause root layer (layer1) is not permitted
        eq_(xml.xpath('//Layer/Name/text()'), ['layer2', 'layer2b', 'layer2b1'])
        limited_bbox = xml.xpath('//Layer/LatLonBoundingBox')[1]
        eq_(float(limited_bbox.attrib['minx']), -40.0)
        eq_(float(limited_bbox.attrib['miny']), -50.0)
        eq_(float(limited_bbox.attrib['maxx']), 0.0)
        eq_(float(limited_bbox.attrib['maxy']), 5.0)

    def test_capabilities_authorize_partial_global_limited(self):
        def auth(service, layers, **kw):
            eq_(service, 'wms.capabilities')
            eq_(len(layers), 8)
            return {
                'authorized': 'partial',
                'limited_to': {'srs': 'EPSG:4326', 'geometry': [-40.0, -50.0, 0.0, 5.0]},
                'layers': {
                    'layer1': {'map': True},
                    'layer1a': {'map': True},
                    'layer2': {'map': True},
                    'layer2b': {'map': True},
                    'layer2b1': {'map': True},
                }
            }
        resp = self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        # print resp.body
        # layer2/2b/2b1 not included because coverage of 2b1 is outside of global limited_to
        eq_(xml.xpath('//Layer/Name/text()'), ['layer1', 'layer1a'])
        limited_bbox = xml.xpath('//Layer/LatLonBoundingBox')[1]
        eq_(float(limited_bbox.attrib['minx']), -40.0)
        eq_(float(limited_bbox.attrib['miny']), -50.0)
        eq_(float(limited_bbox.attrib['maxx']), 0.0)
        eq_(float(limited_bbox.attrib['maxy']), 5.0)

    def test_capabilities_authorize_partial_with_fi(self):
        def auth(service, layers, **kw):
            eq_(service, 'wms.capabilities')
            eq_(len(layers), 8)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'map': True},
                    'layer1a': {'map': True},
                    'layer2': {'map': True, 'featureinfo': True},
                    'layer2b': {'map': True, 'featureinfo': True},
                    'layer2b1': {'map': True, 'featureinfo': True},
                }
            }
        resp = self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(xml.xpath('//Layer/Name/text()'), ['layer1', 'layer1a', 'layer2', 'layer2b', 'layer2b1'])
        layers = xml.xpath('//Layer')
        assert layers[3][0].text == 'layer2'
        assert layers[3].attrib['queryable'] == '1'
        assert layers[4][0].text == 'layer2b'
        assert layers[4].attrib['queryable'] == '1'
        assert layers[5][0].text == 'layer2b1'
        assert layers[5].attrib['queryable'] == '1'

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

    def test_get_map_authorized_limited(self):
        def auth(service, layers, query_extent, **kw):
            eq_(query_extent, ('EPSG:4326', (-80.0, -40.0, 0.0, 0.0)))
            eq_(service, 'wms.map')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {
                        'map': True,
                        'limited_to': {'srs': 'EPSG:4326', 'geometry': [-40.0, -40.0, 0.0, 0.0]},
                    },
                }
            }
        resp = self.app.get(MAP_REQ + 'layers=layer1', extra_environ={'mapproxy.authorize': auth})
        eq_(resp.content_type, 'image/png')
        img = img_from_buf(resp.body)
        # left part not authorized, only bgcolor
        assert len(img.crop((0, 0, 100, 100)).getcolors()) == 1
        # right part authorized, bgcolor + text
        assert len(img.crop((100, 0, 200, 100)).getcolors()) >= 2

    def test_get_map_authorized_global_limited(self):
        def auth(service, layers, query_extent, **kw):
            eq_(query_extent, ('EPSG:4326', (-80.0, -40.0, 0.0, 0.0)))
            eq_(service, 'wms.map')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'limited_to': {'srs': 'EPSG:4326', 'geometry': [-20.0, -40.0, 0.0, 0.0]},
                'layers': {
                    'layer1': {
                        'map': True,
                        'limited_to': {'srs': 'EPSG:4326', 'geometry': [-40.0, -40.0, 0.0, 0.0]},
                    },
                }
            }
        resp = self.app.get(MAP_REQ + 'layers=layer1', extra_environ={'mapproxy.authorize': auth})
        eq_(resp.content_type, 'image/png')
        img = img_from_buf(resp.body)
        # left part not authorized, only bgcolor
        assert len(img.crop((0, 0, 100, 100)).getcolors()) == 1
        # right part authorized, bgcolor + text
        assert len(img.crop((100, 0, 200, 100)).getcolors()) >= 2

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

    def test_get_featureinfo_limited_to_inside(self):
        def auth(service, layers, query_extent, **kw):
            eq_(query_extent, ('EPSG:4326', (-80.0, -40.0, 0.0, 0.0)))
            eq_(service, 'wms.featureinfo')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1b': {'featureinfo': True, 'limited_to':  {'srs': 'EPSG:4326', 'geometry': [-80.0, -40.0, 0.0, 0.0]}},
                }
            }
        serv = MockServ(port=42423)
        serv.expects('/service?request=GetFeatureInfo&service=WMS&Version=1.1.1&SRS=EPSG:4326'
            '&BBOX=-80.0,-40.0,0.0,0.0&WIDTH=200&HEIGHT=100&styles=&FORMAT=image/png&X=10&Y=10'
            '&query_layers=fi&layers=fi')
        serv.returns(b'infoinfo')
        with serv:
            resp = self.app.get(FI_REQ + 'query_layers=layer1b&layers=layer1b', extra_environ={'mapproxy.authorize': auth})
            eq_(resp.body, b'infoinfo')

    def test_get_featureinfo_limited_to_outside(self):
        def auth(service, layers, query_extent, **kw):
            eq_(query_extent, ('EPSG:4326', (-80.0, -40.0, 0.0, 0.0)))
            eq_(service, 'wms.featureinfo')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1b': {'featureinfo': True, 'limited_to':  {'srs': 'EPSG:4326', 'geometry': [-80.0, -40.0, 0.0, -10.0]}},
                }
            }

        resp = self.app.get(FI_REQ + 'query_layers=layer1b&layers=layer1b', extra_environ={'mapproxy.authorize': auth})
        # empty response, FI request is outside of limited_to geometry
        eq_(resp.body, b'')

    def test_get_featureinfo_global_limited(self):
        def auth(service, layers, query_extent, **kw):
            eq_(query_extent, ('EPSG:4326', (-80.0, -40.0, 0.0, 0.0)))
            eq_(service, 'wms.featureinfo')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'limited_to':  {'srs': 'EPSG:4326', 'geometry': [-40.0, -40.0, 0.0, 0.0]},
                'layers': {
                    'layer1b': {'featureinfo': True},
                },
            }
        resp = self.app.get(FI_REQ + 'query_layers=layer1b&layers=layer1b', extra_environ={'mapproxy.authorize': auth})
        # empty response, FI request is outside of limited_to geometry
        eq_(resp.body, b'')


TMS_CAPABILITIES_REQ = '/tms/1.0.0'

class TestTMSAuth(SystemTest):
    config = test_config

    def test_capabilities_authorize_all(self):
        def auth(service, layers, environ, **kw):
            eq_(environ['PATH_INFO'], '/tms/1.0.0')
            eq_(service, 'tms')
            eq_(len(layers), 6)
            return {'authorized': 'full'}

        resp = self.app.get(TMS_CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(xml.xpath('//TileMap/@title'), ['layer 1a', 'layer 1b', 'layer 1', 'layer 2a', 'layer 2b1', 'layer 3'])

    def test_capabilities_authorize_none(self):
        def auth(service, layers, **kw):
            eq_(service, 'tms')
            eq_(len(layers), 6)
            return {'authorized': 'none'}
        self.app.get(TMS_CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth}, status=403)

    def test_capabilities_unauthenticated(self):
        def auth(service, layers, **kw):
            eq_(service, 'tms')
            eq_(len(layers), 6)
            return {'authorized': 'unauthenticated'}
        self.app.get(TMS_CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth}, status=401)

    def test_capabilities_authorize_partial(self):
        def auth(service, layers, **kw):
            eq_(service, 'tms')
            eq_(len(layers), 6)
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
        def auth(service, layers, environ, query_extent, **kw):
            eq_(environ['PATH_INFO'], '/tms/1.0.0/layer1_EPSG900913/0/0/0.png')
            eq_(service, 'tms')
            eq_(query_extent[0], 'EPSG:900913')
            assert bbox_equals(query_extent[1], (-20037508.342789244, -20037508.342789244, 0, 0))
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'tile': True},
                }
            }
        resp = self.app.get(TMS_CAPABILITIES_REQ + '/layer1_EPSG900913/0/0/0.png', extra_environ={'mapproxy.authorize': auth})
        eq_(resp.content_type, 'image/png')
        assert resp.content_length > 1000

    def test_get_tile_global_limited_to(self):
        # check with limited_to for all layers
        auth_dict = {
                'authorized': 'partial',
                'limited_to': {
                    'geometry': [-180, -89, -90, 89],
                    'srs': 'EPSG:4326',
                },
                'layers': {
                    'layer3': {'tile': True},
                }
            }
        self.check_get_tile_limited_to(auth_dict)

    def test_get_tile_layer_limited_to(self):
        # check with limited_to for one layer
        auth_dict = {
            'authorized': 'partial',
            'layers': {
                'layer3': {
                    'tile': True,
                    'limited_to': {
                        'geometry': [-180, -89, -90, 89],
                        'srs': 'EPSG:4326',
                    }
                },
            }
        }

        self.check_get_tile_limited_to(auth_dict)

    def check_get_tile_limited_to(self, auth_dict):
        def auth(service, layers, environ, query_extent, **kw):
            eq_(environ['PATH_INFO'], '/tms/1.0.0/layer3/0/0/0.jpeg')
            eq_(service, 'tms')
            eq_(len(layers), 1)
            eq_(query_extent[0], 'EPSG:900913')
            assert bbox_equals(query_extent[1], (-20037508.342789244, -20037508.342789244, 0, 0))

            return auth_dict

        serv = MockServ(port=42423)
        serv.expects('/1/0/0.png')
        serv.returns(create_tmp_image((256, 256), color=(255, 0, 0)), headers={'content-type': 'image/png'})
        with serv:
            resp = self.app.get(TMS_CAPABILITIES_REQ + '/layer3/0/0/0.jpeg', extra_environ={'mapproxy.authorize': auth})

        eq_(resp.content_type, 'image/png')

        img = img_from_buf(resp.body)
        img = img.convert('RGBA')
        # left part authorized, red
        eq_(img.crop((0, 0, 127, 255)).getcolors()[0], (127*255, (255, 0, 0, 255)))
        # right part not authorized, transparent
        eq_(img.crop((129, 0, 255, 255)).getcolors()[0][1][3], 0)

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
        def auth(service, layers, query_extent, **kw):
            eq_(service, 'kml')
            eq_(len(layers), 1)
            eq_(query_extent[0], 'EPSG:900913')
            assert bbox_equals(query_extent[1], (-20037508.342789244, -20037508.342789244, 20037508.342789244, 20037508.342789244))

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

    def test_get_tile_global_limited_to(self):
        # check with limited_to for all layers
        auth_dict = {
                'authorized': 'partial',
                'limited_to': {
                    'geometry': [-180, -89, -90, 89],
                    'srs': 'EPSG:4326',
                },
                'layers': {
                    'layer3': {'tile': True},
                }
            }
        self.check_get_tile_limited_to(auth_dict)

    def test_get_tile_layer_limited_to(self):
        # check with limited_to for one layer
        auth_dict = {
            'authorized': 'partial',
            'layers': {
                'layer3': {
                    'tile': True,
                    'limited_to': {
                        'geometry': [-180, -89, -90, 89],
                        'srs': 'EPSG:4326',
                    }
                },
            }
        }

        self.check_get_tile_limited_to(auth_dict)

    def check_get_tile_limited_to(self, auth_dict):
        def auth(service, layers, environ, query_extent, **kw):
            eq_(environ['PATH_INFO'], '/kml/layer3_EPSG900913/1/0/0.jpeg')
            eq_(service, 'kml')
            eq_(len(layers), 1)
            eq_(query_extent[0], 'EPSG:900913')
            assert bbox_equals(query_extent[1], (-20037508.342789244, -20037508.342789244, 0, 0))
            return auth_dict

        serv = MockServ(port=42423)
        serv.expects('/1/0/0.png')
        serv.returns(create_tmp_image((256, 256), color=(255, 0, 0)), headers={'content-type': 'image/png'})
        with serv:
            resp = self.app.get('/kml/layer3_EPSG900913/1/0/0.jpeg', extra_environ={'mapproxy.authorize': auth})

        eq_(resp.content_type, 'image/png')

        img = img_from_buf(resp.body)
        img = img.convert('RGBA')
        # left part authorized, red
        eq_(img.crop((0, 0, 127, 255)).getcolors()[0], (127*255, (255, 0, 0, 255)))
        # right part not authorized, transparent
        eq_(img.crop((129, 0, 255, 255)).getcolors()[0][1][3], 0)


WMTS_CAPABILITIES_REQ = '/wmts/1.0.0/WMTSCapabilities.xml'

class TestWMTSAuth(SystemTest):
    config = test_config

    def test_capabilities_authorize_all(self):
        def auth(service, layers, environ, **kw):
            eq_(environ['PATH_INFO'], '/wmts/1.0.0/WMTSCapabilities.xml')
            eq_(service, 'wmts')
            eq_(len(layers), 6)
            return {'authorized': 'full'}

        resp = self.app.get(WMTS_CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(set(xml.xpath('//wmts:Layer/ows:Title/text()',
            namespaces={'wmts': 'http://www.opengis.net/wmts/1.0', 'ows': 'http://www.opengis.net/ows/1.1'})),
            set(['layer 1b', 'layer 1a', 'layer 2a', 'layer 2b1', 'layer 1', 'layer 3']))

    def test_capabilities_authorize_none(self):
        def auth(service, layers, **kw):
            eq_(service, 'wmts')
            eq_(len(layers), 6)
            return {'authorized': 'none'}
        self.app.get(WMTS_CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth}, status=403)

    def test_capabilities_unauthenticated(self):
        def auth(service, layers, **kw):
            eq_(service, 'wmts')
            eq_(len(layers), 6)
            return {'authorized': 'unauthenticated'}
        self.app.get(WMTS_CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth}, status=401)

    def test_capabilities_authorize_partial(self):
        def auth(service, layers, **kw):
            eq_(service, 'wmts')
            eq_(len(layers), 6)
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
        resp = self.app.get(WMTS_CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(set(xml.xpath('//wmts:Layer/ows:Title/text()',
            namespaces={'wmts': 'http://www.opengis.net/wmts/1.0', 'ows': 'http://www.opengis.net/ows/1.1'})),
            set(['layer 1a', 'layer 2b1']))

    def test_get_tile(self):
        def auth(service, layers, environ, query_extent, **kw):
            eq_(environ['PATH_INFO'], '/wmts/layer1/GLOBAL_MERCATOR/0/0/0.png')
            eq_(service, 'wmts')
            eq_(len(layers), 1)
            eq_(query_extent[0], 'EPSG:900913')
            assert bbox_equals(query_extent[1], (-20037508.342789244, -20037508.342789244, 20037508.342789244, 20037508.342789244))
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'tile': True},
                }
            }
        resp = self.app.get('/wmts/layer1/GLOBAL_MERCATOR/0/0/0.png', extra_environ={'mapproxy.authorize': auth})
        eq_(resp.content_type, 'image/png')
        assert resp.content_length > 1000

    def test_get_tile_global_limited_to(self):
        # check with limited_to for all layers
        auth_dict = {
                'authorized': 'partial',
                'limited_to': {
                    'geometry': [-180, -89, -90, 89],
                    'srs': 'EPSG:4326',
                },
                'layers': {
                    'layer3': {'tile': True},
                }
            }
        self.check_get_tile_limited_to(auth_dict)

    def test_get_tile_layer_limited_to(self):
        # check with limited_to for one layer
        auth_dict = {
            'authorized': 'partial',
            'layers': {
                'layer3': {
                    'tile': True,
                    'limited_to': {
                        'geometry': [-180, -89, -90, 89],
                        'srs': 'EPSG:4326',
                    }
                },
            }
        }

        self.check_get_tile_limited_to(auth_dict)

    def check_get_tile_limited_to(self, auth_dict):
        def auth(service, layers, environ, query_extent, **kw):
            eq_(environ['PATH_INFO'], '/wmts/layer3/GLOBAL_MERCATOR/1/0/0.jpeg')
            eq_(service, 'wmts')
            eq_(len(layers), 1)
            eq_(query_extent[0], 'EPSG:900913')
            assert bbox_equals(query_extent[1], (-20037508.342789244, 0, 0, 20037508.342789244))
            return auth_dict

        serv = MockServ(port=42423)
        serv.expects('/1/0/1.png')
        serv.returns(create_tmp_image((256, 256), color=(255, 0, 0)), headers={'content-type': 'image/png'})
        with serv:
            resp = self.app.get('/wmts/layer3/GLOBAL_MERCATOR/1/0/0.jpeg', extra_environ={'mapproxy.authorize': auth})

        eq_(resp.content_type, 'image/png')

        img = img_from_buf(resp.body)
        img = img.convert('RGBA')
        # left part authorized, red
        eq_(img.crop((0, 0, 127, 255)).getcolors()[0], (127*255, (255, 0, 0, 255)))
        # right part not authorized, transparent
        eq_(img.crop((129, 0, 255, 255)).getcolors()[0][1][3], 0)

    def test_get_tile_limited_to_outside(self):
        def auth(service, layers, environ, **kw):
            eq_(environ['PATH_INFO'], '/wmts/layer3/GLOBAL_MERCATOR/2/0/0.jpeg')
            eq_(service, 'wmts')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'limited_to': {
                    'geometry': [0, -89, 90, 89],
                    'srs': 'EPSG:4326',
                },
                'layers': {
                    'layer3': {'tile': True},
                }
            }

        resp = self.app.get('/wmts/layer3/GLOBAL_MERCATOR/2/0/0.jpeg', extra_environ={'mapproxy.authorize': auth})

        eq_(resp.content_type, 'image/png')
        is_transparent(resp.body)

    def test_get_tile_limited_to_inside(self):
        def auth(service, layers, environ, **kw):
            eq_(environ['PATH_INFO'], '/wmts/layer3/GLOBAL_MERCATOR/1/0/0.jpeg')
            eq_(service, 'wmts')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'limited_to': {
                    'geometry': [-180, -89, 180, 89],
                    'srs': 'EPSG:4326',
                },
                'layers': {
                    'layer3': {'tile': True},
                }
            }

        serv = MockServ(port=42423)
        serv.expects('/1/0/1.png')
        serv.returns(create_tmp_image((256, 256), color=(255, 0, 0)), headers={'content-type': 'image/png'})
        with serv:
            resp = self.app.get('/wmts/layer3/GLOBAL_MERCATOR/1/0/0.jpeg', extra_environ={'mapproxy.authorize': auth})

        eq_(resp.content_type, 'image/jpeg')

        img = img_from_buf(resp.body)
        eq_(img.getcolors()[0], (256*256, (255, 0, 0)))

    def test_get_tile_kvp(self):
        def auth(service, layers, environ, **kw):
            eq_(environ['PATH_INFO'], '/service')
            eq_(service, 'wmts')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'tile': True},
                }
            }
        resp = self.app.get('/service?service=WMTS&version=1.0.0&layer=layer1&request=GetTile&'
            'style=&tilematrixset=GLOBAL_MERCATOR&tilematrix=00&tilerow=0&tilecol=0&format=image/png', extra_environ={'mapproxy.authorize': auth})
        eq_(resp.content_type, 'image/png')

    def test_get_tile_authorize_none(self):
        def auth(service, layers, **kw):
            eq_(service, 'wmts')
            eq_(len(layers), 1)
            return {
                'authorized': 'none',
            }
        self.app.get('/wmts/layer1/GLOBAL_MERCATOR/0/0/0.png', extra_environ={'mapproxy.authorize': auth}, status=403)

    def test_get_tile_authorize_none_kvp(self):
        def auth(service, layers, environ, **kw):
            eq_(environ['PATH_INFO'], '/service')
            eq_(service, 'wmts')
            eq_(len(layers), 1)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'tile': False},
                }
            }
        self.app.get('/service?service=WMTS&version=1.0.0&layer=layer1&request=GetTile&'
            'style=&tilematrixset=GLOBAL_MERCATOR&tilematrix=00&tilerow=0&tilecol=0&format=image/png',
            extra_environ={'mapproxy.authorize': auth}, status=403)

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

