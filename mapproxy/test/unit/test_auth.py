from mapproxy.layer import MapLayer, DefaultMapExtent
from mapproxy.request.base import Request
from mapproxy.exception import RequestError
from mapproxy.request.wms import wms_request
from mapproxy.service.wms import WMSLayer, WMSGroupLayer, WMSServer
from mapproxy.test.http import make_wsgi_env

from nose.tools import raises, eq_

class DummyLayer(MapLayer):
    transparent = True
    extent = DefaultMapExtent()
    has_legend = False
    queryable = False
    def __init__(self, name):
        self.name = name
        self.requested = False
        self.queried = False
    def get_map(self, query):
        self.requested = True
    def get_info(self, query):
        self.queried = True
    def map_layers_for_query(self, query):
        return [(self.name, self)]
    def info_layers_for_query(self, query):
        return [(self.name, self)]

MAP_REQ = "FORMAT=image%2Fpng&SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&STYLES=&SRS=EPSG%3A4326&BBOX=5,46,8,48&WIDTH=60&HEIGHT=40"
FI_REQ = "FORMAT=image%2Fpng&SERVICE=WMS&VERSION=1.1.1&REQUEST=GetFeatureInfo&STYLES=&SRS=EPSG%3A4326&BBOX=5,46,8,48&WIDTH=60&HEIGHT=40&X=30&Y=20"

class TestWMSAuth(object):
    def setup(self):
        layers = {}
        wms_layers = {}

        # create test layer tree
        # - unnamed root
        #     - layer1
        #       - layer1a
        #       - layer1b
        #     - layer2
        #       - layer2a
        #       - layer2b
        #         - layer2b1

        layers['layer1a'] = DummyLayer('layer1a')
        wms_layers['layer1a'] = WMSLayer('layer1a', None, [layers['layer1a']],
                                         info_layers=[layers['layer1a']])
        layers['layer1b'] = DummyLayer('layer1b')
        wms_layers['layer1b'] = WMSLayer('layer1b', None, [layers['layer1b']],
                                         info_layers=[layers['layer1b']])
        wms_layers['layer1'] = WMSGroupLayer('layer1', None, None,
                                             [wms_layers['layer1a'], wms_layers['layer1b']])


        layers['layer2a'] = DummyLayer('layer2a')
        wms_layers['layer2a'] = WMSLayer('layer2a', None, [layers['layer2a']],
                                         info_layers=[layers['layer2a']])
        layers['layer2b1'] = DummyLayer('layer2b1')
        wms_layers['layer2b1'] = WMSLayer('layer2b1', None, [layers['layer2b1']],
                                          info_layers=[layers['layer2b1']])
        layers['layer2b'] = DummyLayer('layer2b')
        wms_layers['layer2b'] = WMSGroupLayer('layer2b', None, layers['layer2b'],
                                              [wms_layers['layer2b1']])
        wms_layers['layer2'] = WMSGroupLayer('layer2', None, None,
                                             [wms_layers['layer2a'], wms_layers['layer2b']])
        
        root_layer = WMSGroupLayer(None, 'root layer', None, [wms_layers['layer1'],
                                                  wms_layers['layer2']])
        self.wms_layers = wms_layers
        self.layers = layers
        self.server = WMSServer(md={}, root_layer=root_layer)
    

# ###
# see mapproxy.test.system.test_auth for WMS GetCapabilities request tests
# ###

class TestWMSGetMapAuth(TestWMSAuth):
    def map_request(self, layers, auth):
        env = make_wsgi_env(MAP_REQ+'&layers=' + layers, extra_environ={'mapproxy.authorize': auth})
        req = Request(env)
        return wms_request(req)

    def test_root_with_partial_sublayers(self):
        # filter out sublayer layer1b
        def auth(service, layers):
            eq_(layers, 'layer1a layer1b'.split())
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'map': True},
                    'layer1a': {'map': True},
                    'layer1b': {'map': False},
                }
            }
        self.server.map(self.map_request('layer1', auth))
        assert self.layers['layer1a'].requested
        assert not self.layers['layer1b'].requested

    def test_accept_sublayer(self):
        def auth(service, layers):
            eq_(layers, 'layer1a'.split())
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'map': True},
                    'layer1a': {'map': True},
                    'layer1b': {'map': False},
                }
            }
        self.server.map(self.map_request('layer1a', auth))
        assert self.layers['layer1a'].requested
        assert not self.layers['layer1b'].requested
    
    def test_accept_sublayer_w_root_denied(self):
        def auth(service, layers):
            eq_(layers, 'layer1a'.split())
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'map': False},
                    'layer1a': {'map': True},
                    'layer1b': {'map': False},
                }
            }
        self.server.map(self.map_request('layer1a', auth))
        assert self.layers['layer1a'].requested
        assert not self.layers['layer1b'].requested
    
    @raises(RequestError)
    def test_deny_sublayer(self):
        def auth(service, layers):
            eq_(layers, 'layer1b'.split())
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'map': True},
                    'layer1a': {'map': True},
                    'layer1b': {'map': False},
                }
            }
        self.server.map(self.map_request('layer1b', auth))

    @raises(RequestError)
    def test_deny_group_layer_w_source(self):
        def auth(service, layers):
            eq_(layers, 'layer2b'.split())
            return {
                'authorized': 'partial',
                'layers': {
                    'layer2b': {'map': False},
                }
            }
        self.server.map(self.map_request('layer2b', auth))

    def test_nested_layers_with_partial_sublayers(self):
        def auth(service, layers):
            eq_(layers, 'layer1a layer1b layer2a layer2b'.split())
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1a': {'map': False},
                    # deny is the default
                    #'layer1b': {'map': False},
                    'layer2a': {'map': True},
                    'layer2b': {'map': False},
                }
            }
        self.server.map(self.map_request('layer1,layer2', auth))
        assert self.layers['layer2a'].requested
        assert not self.layers['layer2b'].requested
        assert not self.layers['layer1a'].requested
        assert not self.layers['layer1b'].requested

class TestWMSGetFeatureInfoAuth(TestWMSAuth):
    def fi_request(self, layers, auth):
        env = make_wsgi_env(FI_REQ+'&layers=%s&query_layers=%s' % (layers, layers),
                            extra_environ={'mapproxy.authorize': auth})
        req = Request(env)
        return wms_request(req)

    def test_root_with_partial_sublayers(self):
        # filter out sublayer layer1b
        def auth(service, layers):
            eq_(layers, 'layer1a layer1b'.split())
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'featureinfo': True},
                    'layer1a': {'featureinfo': True},
                    'layer1b': {'featureinfo': False},
                }
            }
        self.server.featureinfo(self.fi_request('layer1', auth))
        assert self.layers['layer1a'].queried
        assert not self.layers['layer1b'].queried

    def test_accept_sublayer(self):
        def auth(service, layers):
            eq_(layers, 'layer1a'.split())
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'featureinfo': True},
                    'layer1a': {'featureinfo': True},
                    'layer1b': {'featureinfo': False},
                }
            }
        self.server.featureinfo(self.fi_request('layer1a', auth))
        assert self.layers['layer1a'].queried
        assert not self.layers['layer1b'].queried
    
    def test_accept_sublayer_w_root_denied(self):
        def auth(service, layers):
            eq_(layers, 'layer1a'.split())
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'featureinfo': False},
                    'layer1a': {'featureinfo': True},
                    'layer1b': {'featureinfo': False},
                }
            }
        self.server.featureinfo(self.fi_request('layer1a', auth))
        assert self.layers['layer1a'].queried
        assert not self.layers['layer1b'].queried
    
    @raises(RequestError)
    def test_deny_sublayer(self):
        def auth(service, layers):
            eq_(layers, 'layer1b'.split())
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'featureinfo': True},
                    'layer1a': {'featureinfo': True},
                    'layer1b': {'featureinfo': False},
                }
            }
        self.server.featureinfo(self.fi_request('layer1b', auth))

    @raises(RequestError)
    def test_deny_group_layer_w_source(self):
        def auth(service, layers):
            eq_(layers, 'layer2b'.split())
            return {
                'authorized': 'partial',
                'layers': {
                    'layer2b': {'featureinfo': False},
                }
            }
        self.server.featureinfo(self.fi_request('layer2b', auth))

    def test_nested_layers_with_partial_sublayers(self):
        def auth(service, layers):
            eq_(layers, 'layer1a layer1b layer2a layer2b'.split())
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1a': {'featureinfo': False},
                    # deny is the default
                    #'layer1b': {'featureinfo': False},
                    'layer2a': {'featureinfo': True},
                    'layer2b': {'featureinfo': False},
                }
            }
        self.server.featureinfo(self.fi_request('layer1,layer2', auth))
        assert self.layers['layer2a'].queried
        assert not self.layers['layer2b'].queried
        assert not self.layers['layer1a'].queried
        assert not self.layers['layer1b'].queried

