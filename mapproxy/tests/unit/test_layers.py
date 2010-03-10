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

from __future__ import division
from cStringIO import StringIO
import mapproxy.wms.layer
from mapproxy.wms.client import WMSClient
from mapproxy.core.grid import TileGrid
from mapproxy.core.cache import Cache, TileCacheError
from mapproxy.wms.layer import DirectLayer, Layer, VLayer, WMSCacheLayer, MultiLayer
from mapproxy.tms.layer import TileServiceLayer
from mapproxy.core.request import Request
from mapproxy.tms.request import tile_request
from mapproxy.core.exceptions import RequestError
from mapproxy.wms.request import WMS111MapRequest
from mapproxy.core.srs import SRS

from nose.tools import eq_, assert_almost_equal, raises
from mapproxy.tests.helper import Mocker, mocker
from mocker import ANY


class TestVLayer(Mocker):
    def setup(self):
        Mocker.setup(self)
        self.sources = [self.mock(Layer), self.mock(Layer)]
        self.vlayer = VLayer({}, self.sources)
    def test_render(self):
        req = {}
        self.expect(self.sources[0].render(req)).result('dummy0')
        self.expect(self.sources[1].render(req)).result('dummy1')
        self.replay()
        result = list(self.vlayer.render(req))
        eq_(len(result), 2)

class TestMultiLayer(Mocker):
    def setup(self):
        Mocker.setup(self)
        self.layers = [self.mock(Layer), self.mock(Layer)]
        self.layer = MultiLayer(self.layers, {})
        self.srs = [SRS(900913), SRS(4326)]
    def test_srs_dispatch(self):
        req = WMS111MapRequest(param={'srs': 'EPSG:4326'})
        self.expect(self.layers[0].srs).result(self.srs[0])
        self.expect(self.layers[1].srs).result(self.srs[1])
        self.expect(self.layers[1].render(req)).result('dummy')
        self.replay()
        assert self.layer.render(req) == 'dummy'
    def test_srs_dispatch2(self):
        req = WMS111MapRequest(param={'srs': 'EPSG:31466'})
        self.expect(self.layers[0].srs).result(self.srs[0])
        self.expect(self.layers[0].render(req)).result('dummy')
        self.replay()
        assert self.layer.render(req) == 'dummy'


class TestDirectLayer(Mocker):
    def setup(self):
        Mocker.setup(self)
        self.wms = self.mock(WMSClient)
        self.dl = DirectLayer(self.wms)
    def test_render(self):
        dummy_request = 'dummy request'
        dummy_result = 'dummy result'
        self.expect(self.wms.get_map(dummy_request)).result(dummy_result)
        self.replay()
        result = self.dl.render(dummy_request)
        assert result == dummy_result

class TestWMSCacheLayer(Mocker):
    def setup(self):
        Mocker.setup(self)
        self.tc = self.mock(Cache)
        self.tcl = WMSCacheLayer(self.tc)
    def test_render(self):
        req = WMS111MapRequest(param={'width': '100', 'height': '200',
                                    'bbox': '10,-5,15,5', 'srs': 'EPSG:4326'})
        self.expect(self.tc.image((10, -5, 15, 5), SRS(4326), (100, 200))).result('dummy')
        self.replay()
        result = self.tcl.render(req)
        assert result == 'dummy'
    def test_render_w_exception(self):
        req = WMS111MapRequest(param={'width': '100', 'height': '200',
                                    'bbox': '10,-5,15,5', 'srs': 'EPSG:4326'})
        old_log = mapproxy.wms.layer.log
        mapproxy.core.layer.log = self.mock()
        self.expect(mapproxy.wms.layer.log.error(mocker.ANY))
        exc = TileCacheError('foo happened')
        self.expect(self.tc.image((10, -5, 15, 5), SRS(4326), (100, 200))).throw(exc)
        self.replay()
        try:
            self.tcl.render(req)
        except RequestError, e:
            eq_(e.request, req)
        else:
            assert False, 'expected RequestError'
        mapproxy.core.layer.log = old_log

class TestTileServiceLayer(Mocker):
    def layer_for_grid(self, epsg, **kw):
        grid = TileGrid(epsg=epsg, **kw)
        cache = Cache(self.mock(), grid)
        return TileServiceLayer({}, cache)
        
    def test_global_mercator(self):
        tms = self.layer_for_grid(epsg=900913)
        eq_(tms.grid.profile, 'global-mercator')
        eq_(tms.grid.srs_name, 'OSGEO:41001')
        tile_sets = tms.grid.tile_sets
        eq_(len(tile_sets), 19)
        eq_(tile_sets[0], (0, 78271.516964020484))
        eq_(tms.grid.internal_tile_coord((2, 4, 5), use_profiles=True), (2, 4, 6))
    def test_global_geodetic(self):
        tms = self.layer_for_grid(epsg=4326, is_geodetic=True)
        eq_(tms.grid.profile, 'global-geodetic')
        eq_(tms.grid.srs_name, 'EPSG:4326')
        tile_sets = tms.grid.tile_sets
        eq_(len(tile_sets), 19)
        eq_(tile_sets[0], (0, 360/256/2))
        eq_(tms.grid.internal_tile_coord((2, 4, 5), use_profiles=True), (2, 4, 6))
    def test_global_geodetic_sqrt2(self):
        tms = self.layer_for_grid(epsg=4326, is_geodetic=True, res='sqrt2', levels=40)
        eq_(tms.grid.profile, 'global-geodetic')
        eq_(tms.grid.srs_name, 'EPSG:4326')
        tile_sets = tms.grid.tile_sets
        eq_(len(tile_sets), 19) # skip every second level for sqrt2
        assert_almost_equal(tile_sets[0][1], 360/256/2)
        eq_(tile_sets[1][0], 1)
        assert_almost_equal(tile_sets[1][1], 360/256/2/2)
        eq_(tms.grid.internal_tile_coord((2, 4, 7), use_profiles=True), (2, 4, 16))
    @raises(RequestError)
    def test_render_out_of_bounds(self):
        tms = self.layer_for_grid(epsg=4326, is_geodetic=True)
        tms_req = tile_request(Request({'PATH': '/tms/1.0.0/foo/1/0/-1.png'}))
        tms.render(tile_request)
    def test_render(self):
        tms_req = tile_request(Request({'PATH_INFO': '/tms/1.0.0/foo/2/0/1.png'}))
        tms = self.layer_for_grid(epsg=4326, is_geodetic=True)
        tile = self.mock()
        self.expect(tile.source_buffer()).result(StringIO('dummy'))
        tms.cache.cache_mgr = self.mock()
        tms.cache.cache_mgr.load_tile_coords(ANY, with_metadata=True)
        self.mocker.result([tile])
        self.replay()
        eq_(tms.render(tms_req, use_profiles=True).as_buffer().read(), 'dummy')
        