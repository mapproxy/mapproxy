from mapproxy.grid import tile_grid
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.layer import MapLayer, DefaultMapExtent
from mapproxy.platform.image import Image
from mapproxy.service.base import Server
from mapproxy.service.tile import TileServer
from mapproxy.service.wms import WMSGroupLayer, WMSServer
from mapproxy.test.http import make_wsgi_env
from nose.tools import raises, eq_


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
        root_layer = WMSGroupLayer(None, 'root layer', None, [DummyLayer('layer1')])
        self.wms_server = WMSServer(md={}, root_layer=root_layer, srs=['EPSG:4326'],
            image_formats={'image/png': ImageOptions(format='image/png')})
        # Tile Server
        self.tile_server = TileServer([DummyTileLayer('layer1')], {})

    def test_original_imagesource_returned_when_no_callback(self):
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        env = make_wsgi_env('', extra_environ={})
        img_src2 = self.server.decorate_img(img_src1, env)
        eq_(img_src1, img_src2)

    def test_returns_imagesource(self):
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        env = make_wsgi_env('', extra_environ={})
        img_src2 = self.server.decorate_img(img_src1, env)
        assert isinstance(img_src2, ImageSource)

    def set_called_callback(self, img_src):
        self.called = True
        return img_src

    def test_calls_callback(self):
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        self.called = False
        env = make_wsgi_env('', extra_environ={'mapproxy.decorate_img': self.set_called_callback})
        img_src2 = self.server.decorate_img(img_src1, env)
        eq_(self.called, True)

    def return_new_imagesource_callback(self, img_src):
        new_img_src = ImageSource(Image.new('RGBA', (100, 100)))
        self.new_img_src = new_img_src
        return new_img_src

    def test_returns_callbacks_return_value(self):
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        env = make_wsgi_env('', extra_environ={'mapproxy.decorate_img': self.return_new_imagesource_callback})
        self.new_img_src = None
        img_src2 = self.server.decorate_img(img_src1, env)
        eq_(img_src2, self.new_img_src)

    def test_wms_server(self):
        ''' Test that the decorate_img method is available on a WMSServer instance '''
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        self.called = False
        env = make_wsgi_env('', extra_environ={'mapproxy.decorate_img': self.set_called_callback})
        img_src2 = self.wms_server.decorate_img(img_src1, env)
        eq_(self.called, True)

    def test_tile_server(self):
        ''' Test that the decorate_img method is available on a TileServer instance '''
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        self.called = False
        env = make_wsgi_env('', extra_environ={'mapproxy.decorate_img': self.set_called_callback})
        img_src2 = self.tile_server.decorate_img(img_src1, env)
        eq_(self.called, True)
