from mapproxy.grid import tile_grid
from mapproxy.image import BlankImageSource
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.layer import MapLayer, DefaultMapExtent
from mapproxy.compat.image import Image
from mapproxy.service.base import Server
from mapproxy.service.tile import TileServer
from mapproxy.service.wms import WMSGroupLayer, WMSServer
from mapproxy.service.wmts import WMTSServer
from mapproxy.test.http import make_wsgi_env
from mapproxy.util.ext.odict import odict
from nose.tools import eq_


class DummyLayer(MapLayer):
    transparent = True
    extent = DefaultMapExtent()
    has_legend = False
    queryable = False

    def __init__(self, name):
        MapLayer.__init__(self)
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


class DummyTileLayer(object):
    def __init__(self, name):
        self.requested = False
        self.name = name
        self.grid = tile_grid(900913)

    def tile_bbox(self, request, use_profiles=False):
        # this dummy code does not handle profiles and different tile origins!
        return self.grid.tile_bbox(request.tile)

    def render(self, tile_request, use_profiles=None, coverage=None, decorate_img=None):
        self.requested = True
        resp = BlankImageSource((256, 256), image_opts=ImageOptions(format='image/png'))
        resp.timestamp = 0
        return resp


class TestDecorateImg(object):

    def setup(self):
        # Base server
        self.server = Server()
        # WMS Server
        root_layer = WMSGroupLayer(None, 'root layer', None, [DummyLayer('wms_cache')])
        self.wms_server = WMSServer(
            md={}, root_layer=root_layer, srs=['EPSG:4326'],
            image_formats={'image/png': ImageOptions(format='image/png')}
        )
        # Tile Servers
        layers = odict()
        layers["wms_cache_EPSG900913"] = DummyTileLayer('wms_cache')
        self.tile_server = TileServer(layers, {})
        self.wmts_server = WMTSServer(layers, {})
        # Common arguments
        self.query_extent = ('EPSG:27700', (0, 0, 700000, 1300000))

    def test_original_imagesource_returned_when_no_callback(self):
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        env = make_wsgi_env('', extra_environ={})
        img_src2 = self.server.decorate_img(
            img_src1, 'wms.map', ['layer1'],
            env, self.query_extent
        )
        eq_(img_src1, img_src2)

    def test_returns_imagesource(self):
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        env = make_wsgi_env('', extra_environ={})
        img_src2 = self.server.decorate_img(
            img_src1, 'wms.map', ['layer1'],
            env, self.query_extent
        )
        assert isinstance(img_src2, ImageSource)

    def set_called_callback(self, img_src, service, layers, **kw):
        self.called = True
        return img_src

    def test_calls_callback(self):
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        self.called = False
        env = make_wsgi_env('', extra_environ={'mapproxy.decorate_img': self.set_called_callback})
        img_src2 = self.server.decorate_img(
            img_src1, 'wms.map', ['layer1'],
            env, self.query_extent
        )
        eq_(self.called, True)

    def return_new_imagesource_callback(self, img_src, service, layers, **kw):
        new_img_src = ImageSource(Image.new('RGBA', (100, 100)))
        self.new_img_src = new_img_src
        return new_img_src

    def test_returns_callbacks_return_value(self):
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        env = make_wsgi_env('', extra_environ={'mapproxy.decorate_img': self.return_new_imagesource_callback})
        self.new_img_src = None
        img_src2 = self.server.decorate_img(
            img_src1, 'wms.map', ['layer1'],
            env, self.query_extent
        )
        eq_(img_src2, self.new_img_src)

    def test_wms_server(self):
        ''' Test that the decorate_img method is available on a WMSServer instance '''
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        self.called = False
        env = make_wsgi_env('', extra_environ={'mapproxy.decorate_img': self.set_called_callback})
        img_src2 = self.wms_server.decorate_img(
            img_src1, 'wms.map', ['layer1'],
            env, self.query_extent
        )
        eq_(self.called, True)

    def test_tile_server(self):
        ''' Test that the decorate_img method is available on a TileServer instance '''
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        self.called = False
        env = make_wsgi_env('', extra_environ={'mapproxy.decorate_img': self.set_called_callback})
        img_src2 = self.tile_server.decorate_img(
            img_src1, 'tms', ['layer1'],
            env, self.query_extent
        )
        eq_(self.called, True)

    def test_wmts_server(self):
        ''' Test that the decorate_img method is available on a WMTSServer instance '''
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        self.called = False
        env = make_wsgi_env('', extra_environ={'mapproxy.decorate_img': self.set_called_callback})
        img_src2 = self.wmts_server.decorate_img(
            img_src1, 'wmts', ['layer1'],
            env, self.query_extent
        )
        eq_(self.called, True)

    def test_args(self):
        def callback(img_src, service, layers, environ, query_extent, **kw):
            assert isinstance(img_src, ImageSource)
            eq_('wms.map', service)
            assert isinstance(layers, list)
            assert isinstance(environ, dict)
            assert len(query_extent) == 2
            assert len(query_extent[1]) == 4
            return img_src
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        env = make_wsgi_env('', extra_environ={'mapproxy.decorate_img': callback})
        img_src2 = self.tile_server.decorate_img(
            img_src1, 'wms.map', ['layer1'],
            env, self.query_extent
        )
