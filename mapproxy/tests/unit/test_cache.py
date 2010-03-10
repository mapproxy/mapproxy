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

from __future__ import with_statement
import os
import time
from contextlib import contextmanager
from tempfile import mkdtemp
from shutil import rmtree
from cStringIO import StringIO

from mapproxy.core.cache import (
    Cache,
    TileSource,
    FileCache,
    CacheManager,
    TileCollection,
    _ThreadedTileCreator,
    _SequentialTileCreator,
    _Tile,
    TileSourceError,
)
from mapproxy.wms.client import WMSClient
from mapproxy.wms.request import WMS111MapRequest
from mapproxy.wms.cache import WMSTileSource
from mapproxy.tms.cache import TMSTileSource
from mapproxy.core.srs import SRS
from mapproxy.core.image import ImageSource, TiledImage
from mapproxy.core.utils import LockTimeout
from mapproxy.core.grid import tile_grid_for_epsg, TileGrid
from mapproxy.tests.helper import Mocker, TempFiles
from mapproxy.tests.http import mock_httpd
from mapproxy.tests.image import tmp_image, is_png, assert_image_mode
from mocker import ANY
from nose.tools import eq_, raises


class TestCache(Mocker):
    def setup(self):
        Mocker.setup(self)
        self.mgr = self.mock(CacheManager)
        self.grid = tile_grid_for_epsg(4326)
        self.tc = Cache(self.mgr, self.grid)
    def test_get_tiles_empty(self):
        self.expect(self.mgr.load_tile_coords(ANY, with_metadata=True)).result([])
        self.replay()
        result = self.tc.tile(None)
        assert result is None
    def test_get_tiles(self):
        with TempFiles(2) as tmp_files:
            tiles = [_Tile((0, 0, 0)), _Tile((1, 0, 0))]
            image_sources = [ImageSource(tmp_files[0]), ImageSource(tmp_files[1])]
            def load_tiles(_):
                return image_sources
            self.expect(self.mgr.load_tile_coords(ANY)).call(load_tiles)
            self.replay()
            result = self.tc._tiles([(0, 0, 0), (1, 0, 0)])
            assert len(result) == 2
            assert result == image_sources
            assert hasattr(result[0].as_buffer(), 'read')
            assert hasattr(result[1].as_buffer(), 'read')
    
    def check_tiled_image(self, tiles, tile_grid, out_size, req_bbox, expected_bbox):
        with tmp_image((256, 256)) as img:
            self.expect(self.mgr.load_tile_coords(ANY)).result([ImageSource(img)])
            self.replay()
            result = self.tc._tiled_image(req_bbox=req_bbox, req_srs=SRS(4326),
                                             out_size=out_size)
            assert isinstance(result, TiledImage)
            eq_(result.tile_grid, tile_grid)
            eq_(result.tile_size, (256, 256))
            eq_(result.src_srs, SRS(4326))
            eq_(result.src_bbox, expected_bbox)
        
    def test_tiled_image(self):
        data = [([_Tile((0, 0, 0))], (1, 1), (100, 100),
                 (-180,-90,180,90), (-180, -90, 180, 270)),
                ([_Tile((0, 0, 1)), _Tile((1, 0, 1))], (2, 1),
                 (200, 200), (-180,-90,180,90), (-180, -90, 180, 90)),
                ([_Tile((0, 0, 1))], (1, 1),
                 (200, 200), (-180,-90,0,90), (-180, -90, 0, 90)),
                ([_Tile((0, 1, 2)), _Tile((1, 1, 2)), _Tile((0, 0, 2)), _Tile((1, 0, 2))],
                 (2, 2), (500, 500), (-180,-90,0,90), (-180, -90, 0, 90)),
        ]
        for tiles, tile_grid, out_size, req_bbox, expected_bbox in data:
            yield self.check_tiled_image, tiles, tile_grid, out_size, req_bbox, expected_bbox
    
    def test_get_image(self):
        with tmp_image((256, 256)) as img:
            tiles = [_Tile((0, 0, 1))]
            self.expect(self.mgr.load_tile_coords(ANY)).result([_Tile(ImageSource(img))])
            self.replay()
            result = self.tc.image(req_bbox=(-180,-90,0,90), req_srs=SRS(4326),
                                       out_size=(256, 256))
            assert isinstance(result, ImageSource)
            eq_(result.size, (256, 256))

class TestCacheManager(Mocker):
    def setup(self):
        Mocker.setup(self)
        self.cache = self.mock(FileCache)
        self.tile_source = self.mock(TileSource)
        self.tile_creator = self.mock()
        self.mgr = CacheManager(cache=self.cache, tile_source=self.tile_source,
                                tile_creator=self.tile_creator)
    
    def test_get_tiles_not_cached(self):
        tiles = TileCollection([(0, 0, 0)])
        def create_tiles(tiles, _tc, _source, _mgr):
            tiles[0].source = ImageSource(StringIO('tile1'))
            return tiles
        with TempFiles(no_create=True) as tmp_files:
            self.expect(self.cache.is_cached(tiles[0])).result(False)
            self.expect(self.tile_creator([tiles[0]], tiles, self.tile_source,
                                          self.mgr)).call(create_tiles)
            self.replay()
            
            self.mgr._load_tiles(tiles, with_metadata=True)
            assert tiles[0].source.as_buffer().read() == 'tile1'
    
    def test_get_tiles_cached(self):
        with TempFiles() as tmp_files:
            def load_tile(tile, with_metadata=False):
                tile.source = ImageSource(tmp_files[0])
                return tile
            self.expect(self.cache.is_cached(_Tile((0, 0, 0)))).result(True)
            self.expect(self.cache.load(_Tile((0, 0, 0)), with_metadata=False)).call(load_tile)
            self.replay()
            
            tiles = self.mgr.load_tile_coords([(0, 0, 0)])
            for tile in tiles:
                assert isinstance(tile, _Tile)
    
    def test_is_cached(self):
        self.expect(self.cache.is_cached(_Tile((0, 0, 0)))).result(True)
        self.replay()
        assert self.mgr.is_cached(_Tile((0, 0, 0)))

    def test_is_not_cached(self):
        self.expect(self.cache.is_cached(_Tile((0, 0, 0)))).result(False)
        self.replay()
        assert not self.mgr.is_cached(_Tile((0, 0, 0)))
    
    def test_is_cached_but_stale(self):
        time_now = time.time()
        time_before = time_now - 60
        self.mgr.expire_timestamp = lambda tile: time_now
        self.expect(self.cache.is_cached(_Tile((0, 0, 0)))).result(True)
        self.expect(self.cache.timestamp_created(_Tile((0, 0, 0)))).result(time_before)
        self.replay()
        assert not self.mgr.is_cached(_Tile((0, 0, 0)))
    
    def test_store_tiles(self):
        tiles = [_Tile((0, 0, 0)), _Tile((1, 0, 0))]
        self.expect(self.cache.store(tiles[0]))
        self.expect(self.cache.store(tiles[1]))
        self.replay()
        
        self.mgr.store_tiles(tiles)

class TestFileCache(object):
    def setup(self):
        self.cache_dir = mkdtemp()
        self.cache = FileCache(cache_dir=self.cache_dir, file_ext='png')
    def teardown(self):
        rmtree(self.cache_dir)
    
    def test_is_cached_miss(self):
        assert not self.cache.is_cached(_Tile((0, 0, 0)))
    
    def test_is_cached_hit(self):
        tile = _Tile((0, 0, 0))
        self._create_cached_tile(tile)
        assert self.cache.is_cached(_Tile((0, 0, 0)))
    
    def test_is_cached_none(self):
        assert self.cache.is_cached(_Tile(None))
    
    def test_load_tile_not_cached(self):
        tile = _Tile((0, 0, 0))
        assert self.cache.load(tile) == False
        assert tile.is_missing()
    
    def test_load_tile_cached(self):
        tile = _Tile((0, 0, 0))
        self._create_cached_tile(tile)
        assert self.cache.load(tile) == True
        assert not tile.is_missing()
    
    def test_store(self):
        tile = _Tile((0, 0, 0), ImageSource(StringIO('foo')))
        self.cache.store(tile)
        assert self.cache.is_cached(tile)
        loc = self.cache.tile_location(tile)
        with open(loc) as f:
            assert f.read() == 'foo'
        assert tile.stored
    
    def test_store_tile_already_stored(self):
        tile = _Tile((0, 0, 0), StringIO('foo'))
        tile.stored = True
        self.cache.store(tile)
        loc = self.cache.tile_location(tile)
        assert not os.path.exists(loc)
    
    def _create_cached_tile(self, tile):
        loc = self.cache.tile_location(tile, create_dir=True)
        with open(loc, 'w') as f:
            f.write('foo')
    
class Test_SequentialTileCreator(Mocker):
    def setup(self):
        Mocker.setup(self)
        self.tile_source = self.mock(TileSource)
        self.cache = self.mock(CacheManager)
        self.creator = _SequentialTileCreator(tile_source=self.tile_source,
                                             cache=self.cache)
        self.locked = False
    def test_create_tiles(self):
        tiles = TileCollection([(x, y, 3) for x in range(3) for y in range(3)])
        for tile in tiles:
            self.expect(self.tile_source.tile_lock(tile)).result(self._mock_lock())
            if tile.coord[1] == 2:
                self.expect(self.cache.is_cached(tile)).result(True)
            else:
                self.expect(self.cache.is_cached(tile)).result(False)
                self.expect(self.tile_source.create_tile(tile, ANY)).result([tile])
                self.expect(self.cache.store_tiles([tile]))
        
        self.replay()
        new_tiles = self.creator.create_tiles(tiles, tiles)
        assert new_tiles == [tile for tile in tiles if tile.coord[1] != 2]
    
    @contextmanager
    def _mock_lock(self):
        """
        assert that only one lock at a time is created
        (eg. check the sequential creation of tiles)
        """
        assert not self.locked
        self.locked = True
        yield
        assert self.locked
        self.locked = False

class Test_ThreadedTileCreator(Mocker):
    def setup(self):
        Mocker.setup(self)
        self.tile_source = self.mock(TileSource)
        self.cache = self.mock(CacheManager)
        self.creator = _ThreadedTileCreator(tile_source=self.tile_source,
                                           cache=self.cache)
        self.locked = False
    def test_create_tiles_unique(self):
        tiles = TileCollection([(x, y, 3) for x in range(3) for y in range(3)])
        for tile in tiles:
            self.expect(self.tile_source.lock_filename(tile)).result(str(tile))
            self.expect(self.tile_source.tile_lock(tile)).result(self._null_lock())
            if tile.coord[1] == 2:
                self.expect(self.cache.is_cached(tile)).result(True)
            else:
                self.expect(self.cache.is_cached(tile)).result(False)
                self.expect(self.tile_source.create_tile(tile, ANY)).result([tile])
                self.expect(self.cache.store_tiles([tile]))
        
        self.replay()
        
        new_tiles = self.creator.create_tiles(tiles, tiles)
        expected_tiles =  [tile for tile in tiles if tile.coord[1] != 2]
        eq_(set(new_tiles), set(expected_tiles))
    
    @contextmanager
    def _null_lock(self):
        yield
    
    def test_sort_tiles(self):
        tiles = TileCollection([(x, y, 3) for x in range(2) for y in range(2)])
        self.expect(self.tile_source.lock_filename(tiles[0])).result('lock1')
        self.expect(self.tile_source.lock_filename(tiles[1])).result('lock1')
        self.expect(self.tile_source.lock_filename(tiles[2])).result('lock2')
        self.expect(self.tile_source.lock_filename(tiles[3])).result('lock2')
        
        self.replay()
        unique_tiles, other_tiles = self.creator._sort_tiles(tiles)
        eq_(set(unique_tiles), set([tiles[0], tiles[2]]))
        eq_(other_tiles, [tiles[1], tiles[3]])

    def test_create_tiles_meta(self):
        tiles = TileCollection([(x, y, 3) for x in range(2) for y in range(2)])
        self.expect(self.tile_source.lock_filename(tiles[0])).result('lock1')
        self.expect(self.tile_source.lock_filename(tiles[1])).result('lock1')
        self.expect(self.tile_source.lock_filename(tiles[2])).result('lock2')
        self.expect(self.tile_source.lock_filename(tiles[3])).result('lock2')
        
        self.expect(self.tile_source.tile_lock(tiles[0])).result(self._null_lock())
        self.expect(self.tile_source.tile_lock(tiles[2])).result(self._null_lock())
        self.expect(self.cache.is_cached(tiles[0])).result(True)
        self.expect(self.cache.is_cached(tiles[2])).result(False)
        self.expect(self.tile_source.create_tile(tiles[2], ANY)).result([tiles[2], tiles[3]])
        self.expect(self.cache.store_tiles([tiles[2], tiles[3]]))
        
        self.replay()
        
        new_tiles = self.creator.create_tiles(tiles, tiles)
        eq_(set(new_tiles), set([tiles[2], tiles[3]]))

class TestTileSource(object):
    def setup(self):
        self.lock_dir = mkdtemp()
        self.tile_source = TileSource(lock_dir=self.lock_dir)
    def teardown(self):
        rmtree(self.lock_dir)
    def test_tile_lock(self):
        self.tile_source._id = 'dummy'
        with self.tile_source.tile_lock(_Tile((0, 0, 0))):
            second_lock = self.tile_source.tile_lock(_Tile((0, 0, 0)))
            second_lock.timeout = 0.1
            was_locked = False
            try:
                second_lock.lock()
            except LockTimeout:
                was_locked = True
            assert was_locked
    
    @raises(NotImplementedError)
    def test_create_tile(self):
        self.tile_source.create_tile(_Tile((0, 0, 0)), lambda x: x)

TEST_SERVER_ADDRESS = ('127.0.0.1', 56413)

class TestTMSTileSource(object):
    def setup(self):
        self.tms = TMSTileSource(TileGrid(), 'http://%s:%s/tms' % TEST_SERVER_ADDRESS)
    
    def test_id(self):
        eq_(self.tms.id(), 'http://%s:%s/tms' % TEST_SERVER_ADDRESS)
    
    def test_get_tiles(self):
        with tmp_image((256, 256)) as img:
            expected_req = ({'path': r'/tms/3/1/2.png'},
                            {'body': img.read(), 'headers': {'content-type': 'image/png'}})
            tile = _Tile((1, 2, 3))
            with mock_httpd(TEST_SERVER_ADDRESS, [expected_req]):
                new_tiles = self.tms.create_tile(tile, lambda x: _Tile(x))
                img.seek(0)
                eq_(new_tiles[0].source.as_buffer().read(), img.read())
    def test_get_tiles_inverse(self):
        with tmp_image((256, 256)) as img:
            expected_req = ({'path': r'/tms/3/0/5.png'},
                            {'body': img.read(), 'headers': {'content-type': 'image/png'}})
            self.tms.inverse = True
            tile = _Tile((0, 2, 3))
            with mock_httpd(TEST_SERVER_ADDRESS, [expected_req]):
                new_tiles = self.tms.create_tile(tile, lambda x: _Tile(x))
                img.seek(0)
                eq_(new_tiles[0].source.as_buffer().read(), img.read())
    def test_get_tile_non_image_result(self):
            expected_req = ({'path': r'/tms/1/1/0.png'},
                            {'body': 'error', 'headers': {'content-type': 'text/plain'}})
            with mock_httpd(TEST_SERVER_ADDRESS, [expected_req]):
                try:
                    self.tms.create_tile(_Tile((1, 0, 1)), lambda x: _Tile(x))
                except TileSourceError, e:
                    assert 'image' in e.message
                else:
                    assert False, 'expected TileSourceError'

class TestWMSTileSource(object):
    def setup(self):
        self.grid = tile_grid_for_epsg(epsg=4326)
        self.req = WMS111MapRequest(url='http://%s:%d/service?' % TEST_SERVER_ADDRESS,
                              param=dict(srs='EPSG:4326', layer='foo', format='image/png'))
        self.wms = WMSTileSource(self.grid, [WMSClient(self.req)])
    def test_get_tile_level_zero(self):
        with tmp_image((256, 256)) as img:
            expected_req = ({'path': r'/service?LAYER=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&styles='
                                      '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,270.0&WIDTH=256'},
                            {'body': img.read(), 'headers': {'content-type': 'image/png'}})
            with mock_httpd(TEST_SERVER_ADDRESS, [expected_req]):
                tile = self.wms.create_tile(_Tile((0, 0, 0)), lambda x: _Tile(x))
                assert len(tile) == 1
                assert tile[0].coord == (0, 0, 0)
                # internal conversion to png8, so they are not equal anymore
                # eq_(tile[0].data.read(), img.read())
                assert isinstance(tile[0].source, ImageSource)
                assert is_png(tile[0].source.as_buffer())
                assert_image_mode(tile[0].source.as_buffer(), 'P')
    def test_get_tile_level_zero_w_transparent(self):
        with tmp_image((256, 256)) as img:
            self.req.params['transparent'] = 'True'
            self.wms = WMSTileSource(self.grid, [WMSClient(self.req)])
            expected_req = ({'path': r'/service?LAYER=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&styles='
                                      '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,270.0&WIDTH=256'
                                      '&transparent=True'},
                            {'body': img.read(), 'headers': {'content-type': 'image/png'}})
            with mock_httpd(TEST_SERVER_ADDRESS, [expected_req]):
                tile = self.wms.create_tile(_Tile((0, 0, 0)), lambda x: _Tile(x))
                assert len(tile) == 1
                assert tile[0].coord == (0, 0, 0)
                img.seek(0)
                eq_(tile[0].source.as_buffer().read(), img.read())
                assert is_png(tile[0].source.as_buffer())
    def test_get_tile_level_one(self):
        with tmp_image((512, 512)) as img:
            expected_req = ({'path': r'/service?LAYER=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&styles='
                                      '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,90.0&WIDTH=512'},
                            {'body': img.read(), 'headers': {'content-type': 'image/png'}})
            with mock_httpd(TEST_SERVER_ADDRESS, [expected_req]):
                tiles = self.wms.create_tile(_Tile((1, 0, 1)), lambda x: _Tile(x))
                assert len(tiles) == 2
                for expected, actual in zip([tile.coord for tile in tiles],
                                            [(0, 0, 1), (1, 0, 1)]):
                    assert expected == actual
                for tile in tiles:
                    assert isinstance(tile.source, ImageSource)
    def test_get_tile_non_image_content_type(self):
        expected_req = ({'path': r'/service?LAYER=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,90.0&WIDTH=512'},
                        {'body': 'error', 'headers': {'content-type': 'text/plain'}})
        with mock_httpd(TEST_SERVER_ADDRESS, [expected_req]):
            try:
                self.wms.create_tile(_Tile((1, 0, 1)), lambda x: _Tile(x))
            except TileSourceError, e:
                assert 'image' in e.message
            else:
                assert False, 'expected TileSourceError'
    def test_get_tile_non_image_result(self):
        expected_req = ({'path': r'/service?LAYER=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&styles='
                                  '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,90.0&WIDTH=512'},
                        {'body': 'no image', 'headers': {'content-type': 'image/png'}})
        with mock_httpd(TEST_SERVER_ADDRESS, [expected_req]):
            try:
                self.wms.create_tile(_Tile((1, 0, 1)), lambda x: _Tile(x))
            except TileSourceError, e:
                print e.message
                assert 'cannot identify' in e.message
            else:
                assert False, 'expected TileSourceError'
    
    def test_lock_filename_same(self):
        l1 = self.wms.lock_filename(_Tile((0, 0, 1)))
        l2 = self.wms.lock_filename(_Tile((1, 0, 1)))
        assert l1 == l2

    def test_lock_filename_differ(self):
        l1 = self.wms.lock_filename(_Tile((1, 0, 2)))
        l2 = self.wms.lock_filename(_Tile((2, 0, 2)))
        assert l1 != l2

class TestMergedWMSTileSource(object):
    def setup(self):
        self.grid = tile_grid_for_epsg(epsg=4326)
        self.req1 = WMS111MapRequest(url='http://%s:%d/service1?' % TEST_SERVER_ADDRESS,
                              param=dict(srs='EPSG:4326', layer='foo', format='image/png'))
        self.req2 = WMS111MapRequest(url='http://%s:%d/service2?' % TEST_SERVER_ADDRESS,
                            param=dict(srs='EPSG:4326', layer='bar', format='image/png'))
        self.wms = WMSTileSource(self.grid, [WMSClient(self.req1), WMSClient(self.req2)])
    def test_get_tile_level_zero(self):
        with tmp_image((256, 256)) as img:
            img_data = img.read()
            expected_req1 = ({'path': r'/service1?LAYER=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&styles='
                                      '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,270.0&WIDTH=256'},
                             {'body': img_data, 'headers': {'content-type': 'image/png'}})
            
            expected_req2 = ({'path': r'/service2?LAYER=bar&SERVICE=WMS&FORMAT=image%2Fpng'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&styles='
                                      '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,270.0&WIDTH=256'},
                             {'body': img_data, 'headers': {'content-type': 'image/png'}})
            with mock_httpd(TEST_SERVER_ADDRESS, [expected_req1, expected_req2]):
                tile = self.wms.create_tile(_Tile((0, 0, 0)), lambda x: _Tile(x))
                assert len(tile) == 1
                assert tile[0].coord == (0, 0, 0)
                assert isinstance(tile[0].source, ImageSource)
                assert is_png(tile[0].source.as_buffer())
                assert_image_mode(tile[0].source.as_buffer(), 'P')
    def test_get_tile_level_zero_w_transparent(self):
        with tmp_image((256, 256)) as img:
            img_data = img.read()
            self.req1.params['transparent'] = 'True'
            self.wms = WMSTileSource(self.grid, [WMSClient(self.req1), WMSClient(self.req2)])
            expected_req1 = ({'path': r'/service1?LAYER=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&styles='
                                      '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,270.0&WIDTH=256'
                                      '&transparent=True'},
                             {'body': img_data, 'headers': {'content-type': 'image/png'}})
            
            expected_req2 = ({'path': r'/service2?LAYER=bar&SERVICE=WMS&FORMAT=image%2Fpng'
                                      '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326&styles='
                                      '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,270.0&WIDTH=256'},
                             {'body': img_data, 'headers': {'content-type': 'image/png'}})
            with mock_httpd(TEST_SERVER_ADDRESS, [expected_req1, expected_req2]):
                tile = self.wms.create_tile(_Tile((0, 0, 0)), lambda x: _Tile(x))
                assert len(tile) == 1
                assert tile[0].coord == (0, 0, 0)
                assert is_png(tile[0].source.as_buffer())
                assert_image_mode(tile[0].source.as_buffer(), 'RGBA')

class TestTile(object):
    def test_eq(self):
        assert _Tile((1, 2, 3)) == _Tile((1, 2, 3))
        assert _Tile((1, 1, 1)) != _Tile((1, 2, 3))
    def test_data_not_set(self):
        assert _Tile((1, 2, 3)).source is None
    def test_is_missing(self):
        assert _Tile((1, 2, 3)).is_missing()
        assert not _Tile((1, 2, 3), ImageSource('foo')).is_missing()
    def test_data_obj(self):
        data = StringIO('foo')
        assert _Tile((1, 2, 3), data).source is data