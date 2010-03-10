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

from __future__ import with_statement, division
import Image
from cStringIO import StringIO
from contextlib import nested

from mapproxy.core.grid import TileGrid
from mapproxy.core.cache import Cache
from mapproxy.core.layer import Layer
from mapproxy.tms.layer import TileServiceLayer
from mapproxy.tms import TileServer
from mapproxy.wms.server import WMSServer
from mapproxy.wms.request import WMS111MapRequest
from mapproxy.core.request import Request
from mapproxy.tms.request import tile_request
from mapproxy.core.exceptions import RequestError
from mapproxy.core.image import ImageSource, LayerMerger

from mapproxy.tests.helper import Mocker, assert_re, XPathValidator
from mapproxy.tests.image import tmp_image, is_jpeg
from nose.tools import eq_

class TestWMSServer(Mocker):
    def setup(self):
        Mocker.setup(self)
        self.layers = { 'dummy1': self.mock(Layer), 'dummy2': self.mock(Layer)}
        self.layer_merger_factory = self.mock()
        self.layer_merger = self.mock()
        self.wms = WMSServer(self.layers, {}, self.layer_merger_factory)
        
    def test_render(self):
        req = WMS111MapRequest(url='http://localhost/',
                         param=dict(format='image/png',
                                    layers='dummy2', width=200, height=200))
        self.expect_and_return(self.layer_merger_factory(), self.layer_merger)
        dummy2 = self.layers['dummy2']
        self.expect_and_return(dummy2.render(req), 'img')
        self.layer_merger.add('img')
        img_result = self.mock()
        self.expect_and_return(self.layer_merger.merge('png8', (200, 200), bgcolor='#ffffff',
                                                      transparent=False), img_result)
        img_result.as_buffer(format='png8')
        
        self.replay()
        self.wms.map(req)
        
    def test_render_w_two_layer(self):
        req = WMS111MapRequest(url='http://localhost/',
                         param=dict(format='image/png', layers='dummy2,dummy1',
                                    width=200, height=200))
        self.expect_and_return(self.layer_merger_factory(), self.layer_merger)
        dummy2 = self.layers['dummy2']
        self.expect_and_return(dummy2.render(req), 'img2')
        dummy1 = self.layers['dummy1']
        self.expect_and_return(dummy1.render(req), 'img1')
        self.layer_merger.add('img1')
        self.layer_merger.add('img2')
        img_result = self.mock()
        self.expect_and_return(self.layer_merger.merge('png8', (200, 200), bgcolor='#ffffff',
                                                      transparent=False), img_result)
        img_result.as_buffer(format='png8')
        
        self.replay()
        self.wms.map(req)

class TestTileServer(Mocker):
    def setup(self):
        Mocker.setup(self)
        self.layers = { 'dummy1': self.mock(TileServiceLayer), 'dummy2': self.mock(TileServiceLayer)}
        self.tms = TileServer(self.layers, md={})
        
    def test_render(self):
        from mapproxy.core.app import ctx
        ctx.env = {}
        req = tile_request(Request({'PATH_INFO': '/tms/1.0.0/dummy1/2/1/3.png'}))
        tile = self.mock()
        self.expect(tile.as_buffer()).result(StringIO('dummy'))
        self.expect(self.layers['dummy1'].render(req, use_profiles=True)).result(tile)
        self.expect(tile.timestamp).result(1234567890.0).count(1, None)
        self.expect(tile.size).result(12345).count(1, None)
        self.replay()
        resp = self.tms.map(req)
        eq_(resp.data, 'dummy')
        eq_(resp.content_type, 'image/png')
    
    def test_render_out_of_bounds(self):
        req = tile_request(Request({'PATH_INFO': '/tms/1.0.0/dummy1/2/1/-3.png'}))
        error = RequestError('out of bounds', request=req)
        self.expect(self.layers['dummy1'].render(req, use_profiles=True)).throw(error)
        self.replay()
        try:
            resp = self.tms.map(req)
        except RequestError, e:
            resp = e.render()
            assert_re(resp.data, r'<TileMapServerError>\s+<Message>out of bounds</Message>')
            eq_(resp.content_type, 'text/xml; charset=utf-8')
            eq_(resp.status, '404 Not Found')
        else:
            assert False, 'expected RequestError'
    
    def test_render_service_capabilities(self):
        grid = TileGrid(epsg=4326, is_geodetic=True)
        cache = Cache(None, grid)
        layer = TileServiceLayer({'title': 'Dummy Map', 'name': 'dummy',
                                  'name_path': ('dummy', 'spec')}, cache)
        self.tms.layers = {'dummy': layer}
        req = tile_request(Request({'PATH_INFO': '/tms/1.0.0/', 'wsgi.url_scheme': 'http',
                                   'SERVER_NAME': 'localhost', 'SERVER_PORT': '8080'}))
        self.replay()
        resp = self.tms.tms_capabilities(req)
        validator = XPathValidator(resp.data)
        validator.assert_xpath('//TileMaps/TileMap/@title', 'Dummy Map')
        validator.assert_xpath('//TileMaps/TileMap/@href',
                               'http://localhost:8080/tms/1.0.0/dummy/spec')
        
        validator.assert_xpath('/TileMapService/@version', '1.0.0')
        validator.assert_xpath('/TileMapService/Title')
        validator.assert_xpath('/TileMapService/Abstract')
        
    def test_render_layer_capabilities(self):
        grid = TileGrid(epsg=4326, is_geodetic=True, tile_size=(360, 180))
        cache = Cache(None, grid)
        layer = TileServiceLayer({'title': 'Dummy Map', 'name': 'dummy',
                          'format': 'image/jpeg'}, cache)
        self.tms.layers = {'dummy': layer}
        req = tile_request(Request({'PATH_INFO': '/tms/1.0.0/dummy', 'wsgi.url_scheme': 'http',
                                   'SERVER_NAME': 'localhost', 'SERVER_PORT': '8080'}))
        self.replay()
        resp = self.tms.tms_capabilities(req)
        validator = XPathValidator(resp.data)
        validator.assert_xpath('/TileMap/@version', '1.0.0')
        validator.assert_xpath('/TileMap/Title/text()', 'Dummy Map')
        validator.assert_xpath('/TileMap/Abstract')
        validator.assert_xpath('/TileMap/SRS/text()', 'EPSG:4326')
        validator.assert_xpath('/TileMap/TileFormat/@width', '360')
        validator.assert_xpath('/TileMap/TileFormat/@height', '180')
        
        validator.assert_xpath('/TileMap/Origin/@x', '-180.0')
        validator.assert_xpath('/TileMap/Origin/@y', '-90.0')
        
        validator.assert_xpath('/TileMap/TileFormat/@extension', 'jpeg')
        validator.assert_xpath('/TileMap/TileFormat/@mime-type', 'image/jpeg')

        validator.assert_xpath('//TileSets/@profile', 'local')
        validator.assert_xpath('//TileSets/TileSet[1]/@href',
                               'http://localhost:8080/tms/1.0.0/dummy/0')
        validator.assert_xpath('//TileSets/TileSet[1]/@units-per-pixel', '1.0')
        validator.assert_xpath('//TileSets/TileSet[5]/@href',
                               'http://localhost:8080/tms/1.0.0/dummy/4')
        validator.assert_xpath('//TileSets/TileSet[5]/@order', '4')
        
    def test_render_layer_capabilities2(self):
        resolutions = [0.02197265625, 0.0054931640625, 0.00274658203125,
               0.000686645507812, 0.000343322753906, 0.000171661376953]
        grid = TileGrid(epsg=4326, is_geodetic=True,
                        bbox=(5.40731, 46.8447, 15.5072, 55.4314), res=resolutions)
        cache = Cache(None, grid)
        layer = TileServiceLayer({'title': 'Dummy Map', 'name': 'dummy'}, cache)
        self.tms.layers = {'dummy': layer}
        req = tile_request(Request({'PATH_INFO': '/tms/1.0.0/dummy', 'wsgi.url_scheme': 'http',
                                   'SERVER_NAME': 'localhost', 'SERVER_PORT': '8080'}))
        self.replay()
        resp = self.tms.tms_capabilities(req)
        validator = XPathValidator(resp.data)
        validator.assert_xpath('/TileMap/@version', '1.0.0')
        validator.assert_xpath('/TileMap/Title/text()', 'Dummy Map')
        validator.assert_xpath('/TileMap/Abstract')
        validator.assert_xpath('/TileMap/SRS/text()', 'EPSG:4326')
        validator.assert_xpath('/TileMap/TileFormat/@width', '256')
        validator.assert_xpath('/TileMap/TileFormat/@height', '256')

        maxx = float(validator.xpath('/TileMap/BoundingBox/@maxx')[0])
        assert maxx >= (5.40731+0.02197265625*256)
        
        validator.assert_xpath('/TileMap/Origin/@x', '5.40731')
        validator.assert_xpath('/TileMap/Origin/@y', '46.8447')
        
        validator.assert_xpath('/TileMap/TileFormat/@extension', 'png')
        validator.assert_xpath('/TileMap/TileFormat/@mime-type', 'image/png')

        validator.assert_xpath('//TileSets/@profile', 'local')
        for i, res in enumerate(resolutions):
            validator.assert_xpath('//TileSets/TileSet[%d]/@units-per-pixel' % (i+1,),
                               str(res))


class TestLayerMerger(Mocker):
    def setup(self):
        Mocker.setup(self)
        self.merger = LayerMerger()
    def test_add(self):
        self.merger.add(1)
        self.merger.add(2)
        self.merger.add(3)
        eq_(len(self.merger.layers), 3)
    def test_merge_one(self):
        l_base = self.mock()
        self.expect(iter(l_base))
        self.expect(l_base.transparent).result(False)
        self.replay()
        self.merger.add(l_base)
        assert self.merger.merge('png', (200, 200)) == l_base
    def test_merge_two_non_transparent(self):
        with nested(tmp_image((200, 200)), tmp_image((200, 200))) as (tmp1, tmp2):
            l_base = ImageSource(tmp1)
            l_top = ImageSource(tmp2)
            self.replay()
            self.merger.add(l_base)
            self.merger.add(l_top)
            merge = self.merger.merge('jpeg', (200, 200))
            assert is_jpeg(merge.as_buffer())
    def test_merge_two(self):
        l_base = self.mock()
        l_top = self.mock()
        self.expect(iter(l_base))
        self.expect(iter(l_top))
        self.expect_and_return(l_base.as_image(), Image.new('RGB', (200, 200)))
        self.expect_and_return(l_top.as_image(), Image.new('RGBA', (200, 200)))
        self.replay()
        self.merger.add(l_base)
        self.merger.add(l_top)
        assert isinstance(self.merger.merge('png', (200, 200)), ImageSource)
        