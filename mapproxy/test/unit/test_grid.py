# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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

from __future__ import division
from nose.tools import eq_, assert_almost_equal, raises
from mapproxy.grid import (
    MetaGrid,
    TileGrid,
    _create_tile_list,
    bbox_intersects,
    bbox_contains,
    NoTiles,
    tile_grid,
    resolutions,
    ResolutionRange,
    resolution_range,
    merge_resolution_range,
)
from mapproxy.srs import SRS, TransformationError

class TestResolution(object):
    def test_min_res(self):
        conf = dict(min_res=1000)
        res = resolutions(**conf)
        eq_(res[:5], [1000, 500.0, 250.0, 125.0, 62.5])
        eq_(len(res), 20)

    def test_min_res_max_res(self):
        conf = dict(min_res=1000, max_res=80)
        res = resolutions(**conf)
        eq_(res, [1000, 500.0, 250.0, 125.0])
    
    def test_min_res_levels(self):
        conf = dict(min_res=1600, num_levels=5)
        res = resolutions(**conf)
        eq_(res, [1600, 800.0, 400.0, 200.0, 100.0])
    
    def test_min_res_levels_res_factor(self):
        conf = dict(min_res=1600, num_levels=4, res_factor=4.0)
        res = resolutions(**conf)
        eq_(res, [1600, 400.0, 100.0, 25.0])

    def test_min_res_levels_sqrt2(self):
        conf = dict(min_res=1600, num_levels=5, res_factor='sqrt2')
        res = resolutions(**conf)
        eq_(map(round, res), [1600.0, 1131.0, 800.0, 566.0, 400.0])
    
    def test_min_res_max_res_levels(self):
        conf = dict(min_res=1600, max_res=10, num_levels=10)
        res = resolutions(**conf)
        eq_(len(res), 10)
        # will calculate log10 based factor of 1.75752...
        assert_almost_equal(res[0], 1600)
        assert_almost_equal(res[1], 1600/1.75752, 2)
        assert_almost_equal(res[8], 1600/1.75752**8, 2)
        assert_almost_equal(res[9], 10)
    
    def test_bbox_levels(self):
        conf = dict(bbox=[0,40,15,50], num_levels=10, tile_size=(256, 256))
        res = resolutions(**conf)
        eq_(len(res), 10)
        assert_almost_equal(res[0], 15/256)
        assert_almost_equal(res[1], 15/512)
        

class TestAlignedGrid(object):
    def test_epsg_4326_bbox(self):
        base = tile_grid(srs='epsg:4326')
        bbox = (10.0, -20.0, 40.0, 10.0)
        sub = tile_grid(align_with=base, bbox=bbox)
        
        eq_(sub.bbox, bbox)
        eq_(sub.resolution(0), 180/256/8)
        abbox, grid_size, tiles = sub.get_affected_level_tiles(bbox, 0)
        eq_(abbox, (10.0, -20.0, 55.0, 25.0))
        eq_(grid_size, (2, 2))
        eq_(list(tiles), [(0, 1, 0), (1, 1, 0), (0, 0, 0), (1, 0, 0)])
    
    def test_epsg_4326_bbox_from_sqrt2(self):
        base = tile_grid(srs='epsg:4326', res_factor='sqrt2')
        bbox = (10.0, -20.0, 40.0, 10.0)
        sub = tile_grid(align_with=base, bbox=bbox, res_factor=2.0)
        
        eq_(sub.bbox, bbox)
        eq_(sub.resolution(0), base.resolution(8))
        eq_(sub.resolution(1), base.resolution(10))
        eq_(sub.resolution(2), base.resolution(12))

    def test_epsg_4326_bbox_to_sqrt2(self):
        base = tile_grid(srs='epsg:4326', res_factor=2.0)
        bbox = (10.0, -20.0, 40.0, 10.0)
        sub = tile_grid(align_with=base, bbox=bbox, res_factor='sqrt2')
        
        eq_(sub.bbox, bbox)
        eq_(sub.resolution(0), base.resolution(4))
        eq_(sub.resolution(2), base.resolution(5))
        eq_(sub.resolution(4), base.resolution(6))

        assert sub.resolution(0) > sub.resolution(1) > sub.resolution(3)
        eq_(sub.resolution(3)/2, sub.resolution(5))
        

def test_metagrid_tiles():
    mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2))
    assert list(mgrid.meta_tile((0, 0, 0)).tile_patterns) == \
        [((0, 0, 0), (0, 0))]
    assert list(mgrid.meta_tile((0, 1, 1)).tile_patterns) == \
        [((0, 1, 1), (0, 0)), ((1, 1, 1), (256, 0)), 
         ((0, 0, 1), (0, 256)), ((1, 0, 1), (256, 256))]
         
    assert list(mgrid.meta_tile((1, 2, 2)).tile_patterns) == \
        [((0, 3, 2), (0, 0)), ((1, 3, 2), (256, 0)), 
         ((0, 2, 2), (0, 256)), ((1, 2, 2), (256, 256))]
    
def test_metagrid_tiles_w_meta_size():
    mgrid = MetaGrid(grid=TileGrid(), meta_size=(4, 2))
    assert list(mgrid.meta_tile((1, 2, 2)).tile_patterns) == \
        [((0, 3, 2), (0, 0)), ((1, 3, 2), (256, 0)),
         ((2, 3, 2), (512, 0)), ((3, 3, 2), (768, 0)),
         ((0, 2, 2), (0, 256)), ((1, 2, 2), (256, 256)),
         ((2, 2, 2), (512, 256)), ((3, 2, 2), (768, 256))]

class TestMetaGridGeodetic(object):
    def setup(self):
        self.mgrid = MetaGrid(grid=tile_grid('EPSG:4326'), meta_size=(2, 2), meta_buffer=10)
    
    def test_meta_bbox_level_0(self):
        eq_(self.mgrid._meta_bbox((0, 0, 0)), ((-180, -90, 180, 90), (0, 0, 0, -128)))
        eq_(self.mgrid._meta_bbox((0, 0, 0), limit_to_bbox=False),
            ((-194.0625, -104.0625, 194.0625, 284.0625), (10, 10, 10, 10)))
        
        eq_(self.mgrid.meta_tile((0, 0, 0)).size, (256, 128))
    
    def test_tiles_level_0(self):
        meta_tile = self.mgrid.meta_tile((0, 0, 0))
        eq_(meta_tile.size, (256, 128))
        eq_(meta_tile.grid_size, (1, 1))
        eq_(meta_tile.tile_patterns, [((0, 0, 0), (0, -128))])
    
    def test_meta_bbox_level_1(self):
        eq_(self.mgrid._meta_bbox((0, 0, 1)), ((-180, -90, 180, 90), (0, 0, 0, 0)))
        eq_(self.mgrid._meta_bbox((0, 0, 1), limit_to_bbox=False),
            ((-187.03125, -97.03125, 187.03125, 97.03125), (10, 10, 10, 10)))
        eq_(self.mgrid.meta_tile((0, 0, 1)).size, (512, 256))
        
    def test_tiles_level_1(self):
        eq_(list(self.mgrid.meta_tile((0, 0, 1)).tile_patterns),
            [
                ((0, 0, 1), (0, 0)),
                ((1, 0, 1), (256, 0))
            ])
    def test_tile_list_level_1(self):
        eq_(list(self.mgrid.tile_list((0, 0, 1))),
            [(0, 0, 1), (1, 0, 1)])
    
    def test_meta_bbox_level_2(self):
        eq_(self.mgrid._meta_bbox((0, 0, 2)), ((-180, -90, 3.515625, 90), (0, 0, 10, 0)))
        eq_(self.mgrid._meta_bbox((0, 0, 2), limit_to_bbox=False),
            ((-183.515625, -93.515625, 3.515625, 93.515625), (10, 10, 10, 10)))
        eq_(self.mgrid.meta_tile((0, 0, 2)).size, (522, 512))
        
        eq_(self.mgrid._meta_bbox((2, 0, 2)), ((-3.515625, -90, 180, 90), (10, 0, 0, 0)))
        meta_tile = self.mgrid.meta_tile((2, 0, 2))
        eq_(meta_tile.size, (522, 512))
        eq_(meta_tile.grid_size, (2, 2))

    def test_tiles_level_2(self):
        eq_(list(self.mgrid.meta_tile((0, 0, 2)).tile_patterns),
            [
                ((0, 1, 2), (0, 0)),
                ((1, 1, 2), (256, 0)),
                ((0, 0, 2), (0, 256)),
                ((1, 0, 2), (256, 256)),
            ])
        eq_(list(self.mgrid.meta_tile((2, 0, 2)).tile_patterns),
            [
                ((2, 1, 2), (10, 0)),
                ((3, 1, 2), (266, 0)),
                ((2, 0, 2), (10, 256)),
                ((3, 0, 2), (266, 256)),
            ])
    
    def test_tile_list_level_2(self):
        eq_(list(self.mgrid.tile_list((0, 0, 2))),
            [(0, 1, 2), (1, 1, 2), (0, 0, 2), (1, 0, 2)])
        eq_(list(self.mgrid.tile_list((1, 1, 2))),
            [(0, 1, 2), (1, 1, 2), (0, 0, 2), (1, 0, 2)])
    
    def test_tiles_level_3(self):
        eq_(list(self.mgrid.meta_tile((2, 0, 3)).tile_patterns),
            [
                ((2, 1, 3), (10, 10)),
                ((3, 1, 3), (266, 10)),
                ((2, 0, 3), (10, 266)),
                ((3, 0, 3), (266, 266)),
            ])
        eq_(list(self.mgrid.meta_tile((2, 2, 3)).tile_patterns),
            [
                ((2, 3, 3), (10, 0)),
                ((3, 3, 3), (266, 0)),
                ((2, 2, 3), (10, 256)),
                ((3, 2, 3), (266, 256)),
            ])

class TestMetaGridGeodeticUL(object):
    def setup(self):
        self.tile_grid = tile_grid('EPSG:4326', origin='ul')
        self.mgrid = MetaGrid(grid=self.tile_grid, meta_size=(2, 2), meta_buffer=10)
    
    def test_tiles_level_0(self):
        meta_tile = self.mgrid.meta_tile((0, 0, 0))
        eq_(meta_tile.bbox, (-180, -90, 180, 90))
        eq_(meta_tile.size, (256, 128))
        eq_(meta_tile.grid_size, (1, 1))
        eq_(meta_tile.tile_patterns, [((0, 0, 0), (0, 0))])
    
        
    def test_tiles_level_1(self):
        meta_tile = self.mgrid.meta_tile((0, 0, 1))
        eq_(meta_tile.bbox, (-180, -90, 180, 90))
        eq_(meta_tile.size, (512, 256))
        eq_(meta_tile.grid_size, (2, 1))
        eq_(list(meta_tile.tile_patterns),
            [
                ((0, 0, 1), (0, 0)),
                ((1, 0, 1), (256, 0))
            ])

    def test_tile_list_level_1(self):
        eq_(list(self.mgrid.tile_list((0, 0, 1))),
            [(0, 0, 1), (1, 0, 1)])
    
    def test_tiles_level_2(self):
        meta_tile = self.mgrid.meta_tile((0, 0, 2))
        eq_(meta_tile.bbox, (-180, -90, 3.515625, 90))
        eq_(meta_tile.size, (522, 512))
        eq_(meta_tile.grid_size, (2, 2))
        eq_(meta_tile.tile_patterns,
            [
                ((0, 0, 2), (0, 0)),
                ((1, 0, 2), (256, 0)),
                ((0, 1, 2), (0, 256)),
                ((1, 1, 2), (256, 256)),
            ])
        eq_(list(self.mgrid.meta_tile((2, 0, 2)).tile_patterns),
            [
                ((2, 0, 2), (10, 0)),
                ((3, 0, 2), (266, 0)),
                ((2, 1, 2), (10, 256)),
                ((3, 1, 2), (266, 256)),
            ])
    
    def test_tile_list_level_2(self):
        eq_(list(self.mgrid.tile_list((0, 0, 2))),
            [(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2)])
        eq_(list(self.mgrid.tile_list((1, 1, 2))),
            [(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2)])
    
    def test_tiles_level_3(self):
        meta_tile = self.mgrid.meta_tile((2, 0, 3))
        eq_(meta_tile.bbox, (-91.7578125, -1.7578125, 1.7578125, 90))
        eq_(meta_tile.size, (532, 522))
        eq_(meta_tile.grid_size, (2, 2))
        eq_(list(self.mgrid.meta_tile((2, 0, 3)).tile_patterns),
            [
                ((2, 0, 3), (10, 0)),
                ((3, 0, 3), (266, 0)),
                ((2, 1, 3), (10, 256)),
                ((3, 1, 3), (266, 256)),
            ])
        eq_(list(self.mgrid.meta_tile((2, 2, 3)).tile_patterns),
            [
                ((2, 2, 3), (10, 10)),
                ((3, 2, 3), (266, 10)),
                ((2, 3, 3), (10, 266)),
                ((3, 3, 3), (266, 266)),
            ])


class TestMetaTile(object):
    def setup(self):
        self.mgrid = MetaGrid(grid=tile_grid('EPSG:4326'), meta_size=(2, 2), meta_buffer=10)
    def test_meta_tile(self):
        meta_tile = self.mgrid.meta_tile((2, 0, 2))
        eq_(meta_tile.size, (522, 512))

    def test_metatile_bbox(self):
        mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2))
        meta_tile = mgrid.meta_tile((0, 0, 2))
        assert meta_tile.bbox == (-20037508.342789244, -20037508.342789244, 0.0, 0.0)
        meta_tile = mgrid.meta_tile((1, 1, 2))
        assert meta_tile.bbox == (-20037508.342789244, -20037508.342789244, 0.0, 0.0)
        meta_tile = mgrid.meta_tile((4, 5, 3))
        assert_almost_equal_bbox(meta_tile.bbox, (0.0, 0.0, 10018754.171394622, 10018754.171394622))

    def test_metatile_non_default_meta_size(self):
        mgrid = MetaGrid(grid=TileGrid(), meta_size=(4, 2))
        meta_tile = mgrid.meta_tile((4, 5, 3))
        assert_almost_equal_bbox(meta_tile.bbox, (0.0, 0.0, 20037508.342789244, 10018754.171394622))
        eq_(meta_tile.size, (1024, 512))
        eq_(meta_tile.grid_size, (4, 2))

class TestMetaTileSQRT2(object):
    def setup(self):
        self.grid = tile_grid('EPSG:4326', res_factor='sqrt2')
        self.mgrid = MetaGrid(grid=self.grid, meta_size=(4, 4), meta_buffer=10)
    def test_meta_tile(self):
        meta_tile = self.mgrid.meta_tile((0, 0, 8))
        eq_(meta_tile.size, (1034, 1034))

    def test_metatile_bbox(self):
        meta_tile = self.mgrid.meta_tile((0, 0, 2))
        eq_(meta_tile.bbox,  (-180, -90, 180, 90))
        eq_(meta_tile.size,  (512, 256))
        eq_(meta_tile.grid_size,  (2, 1))
        eq_(meta_tile.tile_patterns, [((0, 0, 2), (0, 0)), ((1, 0, 2), (256, 0))])
        
        meta_tile = self.mgrid.meta_tile((1, 0, 2))
        eq_(meta_tile.bbox, (-180.0, -90, 180.0, 90.0))
        eq_(meta_tile.size,  (512, 256))
        eq_(meta_tile.grid_size,  (2, 1))
        
        meta_tile = self.mgrid.meta_tile((0, 0, 3))
        eq_(meta_tile.bbox, (-180.0, -90, 180.0, 90.0))
        eq_(meta_tile.size,  (724, 362))
        eq_(meta_tile.tile_patterns, [((0, 1, 3), (0, -149)), ((1, 1, 3), (256, -149)),
            ((2, 1, 3), (512, -149)), ((0, 0, 3), (0, 107)), ((1, 0, 3), (256, 107)),
            ((2, 0, 3), (512, 107))])
        
    def test_metatile_non_default_meta_size(self):
        mgrid = MetaGrid(grid=self.grid, meta_size=(4, 2), meta_buffer=0)
        meta_tile = mgrid.meta_tile((4, 3, 6))
        eq_(meta_tile.bbox, (0.0, 0.0, 180.0, 90.0))
        eq_(meta_tile.size, (1024, 512))
        eq_(meta_tile.grid_size, (4, 2))
        eq_(meta_tile.tile_patterns, [((4, 3, 6), (0, 0)), ((5, 3, 6), (256, 0)),
            ((6, 3, 6), (512, 0)), ((7, 3, 6), (768, 0)), ((4, 2, 6), (0, 256)), 
            ((5, 2, 6), (256, 256)), ((6, 2, 6), (512, 256)), ((7, 2, 6), (768, 256))])
        



class TestMinimalMetaTile(object):
    def setup(self):
        self.mgrid = MetaGrid(grid=tile_grid('EPSG:4326'), meta_size=(2, 2), meta_buffer=10)
    
    def test_minimal_tiles(self):
        sgrid = self.mgrid.minimal_meta_tile([(0, 0, 2), (1, 0, 2)])
        eq_(sgrid.grid_size, (2, 1))
        eq_(list(sgrid.tile_patterns),
            [
                ((0, 0, 2), (0, 10)),
                ((1, 0, 2), (256, 10)),
            ]
        )
        eq_(sgrid.bbox, (-180.0, -90.0, 3.515625, 3.515625))
    
    def test_minimal_tiles_fragmented(self):
        sgrid = self.mgrid.minimal_meta_tile(
            [
                           (2, 3, 3),
                (1, 2, 3),
                           (2, 1, 3),
            ])
        
        eq_(sgrid.grid_size, (2, 3))
        eq_(list(sgrid.tile_patterns),
            [
                ((1, 3, 3), (10, 0)), ((2, 3, 3), (266, 0)),
                ((1, 2, 3), (10, 256)), ((2, 2, 3), (266, 256)),
                ((1, 1, 3), (10, 512)), ((2, 1, 3), (266, 512)),
            ]
        )
        eq_(sgrid.bbox, (-136.7578125, -46.7578125, -43.2421875, 90.0))

    def test_minimal_tiles_fragmented_ul(self):
        self.mgrid = MetaGrid(grid=tile_grid('EPSG:4326', origin='ul'),
            meta_size=(2, 2), meta_buffer=10)
        sgrid = self.mgrid.minimal_meta_tile(
            [
                           (2, 0, 3),
                (1, 1, 3),
                           (2, 2, 3),
            ])
        
        eq_(sgrid.grid_size, (2, 3))
        eq_(list(sgrid.tile_patterns),
            [
                ((1, 0, 3), (10, 0)), ((2, 0, 3), (266, 0)),
                ((1, 1, 3), (10, 256)), ((2, 1, 3), (266, 256)),
                ((1, 2, 3), (10, 512)), ((2, 2, 3), (266, 512)),
            ]
        )
        eq_(sgrid.bbox, (-136.7578125, -46.7578125, -43.2421875, 90.0))


class TestMetaGridLevelMetaTiles(object):
    def __init__(self):
        self.meta_grid = MetaGrid(TileGrid(), meta_size=(2, 2))
    
    def test_full_grid_0(self):
        bbox = (-20037508.34, -20037508.34, 20037508.34, 20037508.34)
        abbox, tile_grid, meta_tiles = \
            self.meta_grid.get_affected_level_tiles(bbox, 0)
        meta_tiles = list(meta_tiles)
        assert_almost_equal_bbox(bbox, abbox)
        
        eq_(len(meta_tiles), 1)
        eq_(meta_tiles[0], (0, 0, 0))
    
    def test_full_grid_2(self):
        bbox = (-20037508.34, -20037508.34, 20037508.34, 20037508.34)
        abbox, tile_grid, meta_tiles = \
            self.meta_grid.get_affected_level_tiles(bbox, 2)
        meta_tiles = list(meta_tiles)
        assert_almost_equal_bbox(bbox, abbox)
        
        eq_(tile_grid, (2, 2))
        eq_(len(meta_tiles), 4)
        eq_(meta_tiles[0], (0, 2, 2))
        eq_(meta_tiles[1], (2, 2, 2))
        eq_(meta_tiles[2], (0, 0, 2))
        eq_(meta_tiles[3], (2, 0, 2))
        
class TestMetaGridLevelMetaTilesGeodetic(object):
    def __init__(self):
        self.meta_grid = MetaGrid(TileGrid(is_geodetic=True), meta_size=(2, 2))
    
    def test_full_grid_2(self):
        bbox = (-180.0, -90.0, 180.0, 90)
        abbox, tile_grid, meta_tiles = \
            self.meta_grid.get_affected_level_tiles(bbox, 2)
        meta_tiles = list(meta_tiles)
        assert_almost_equal_bbox(bbox, abbox)
        
        eq_(tile_grid, (2, 1))
        eq_(len(meta_tiles), 2)
        eq_(meta_tiles[0], (0, 0, 2))
        eq_(meta_tiles[1], (2, 0, 2))

    def test_partial_grid_3(self):
        bbox = (0.0, 5.0, 45, 40)
        abbox, tile_grid, meta_tiles = \
            self.meta_grid.get_affected_level_tiles(bbox, 3)
        meta_tiles = list(meta_tiles)
        assert_almost_equal_bbox((0.0, 0.0, 90.0, 90.0), abbox)
        
        eq_(tile_grid, (1, 1))
        eq_(len(meta_tiles), 1)
        eq_(meta_tiles[0], (4, 2, 3))
        

def assert_grid_size(grid, level, grid_size):
    print grid.grid_sizes[level], "==", grid_size
    assert grid.grid_sizes[level] == grid_size
    res = grid.resolutions[level]
    x, y = grid_size
    assert res * x * 256 >= grid.bbox[2] - grid.bbox[0]
    assert res * y * 256 >= grid.bbox[3] - grid.bbox[1]


class TileGridTest(object):
    def check_grid(self, level, grid_size):
        assert_grid_size(self.grid, level, grid_size)

class TestTileGridResolutions(object):
    def test_explicit_grid(self):
        grid = TileGrid(res=[0.1, 0.05, 0.01])
        eq_(grid.resolution(0), 0.1)
        eq_(grid.resolution(1), 0.05)
        eq_(grid.resolution(2), 0.01)
        
        eq_(grid.closest_level(0.00001), 2)
    
    def test_factor_grid(self):
        grid = TileGrid(is_geodetic=True, res=1/0.75, tile_size=(360, 180))
        eq_(grid.resolution(0), 1.0)
        eq_(grid.resolution(1), 0.75)
        eq_(grid.resolution(2), 0.75*0.75)
    
    def test_sqrt_grid(self):
        grid = TileGrid(is_geodetic=True, res='sqrt2', tile_size=(360, 180))
        eq_(grid.resolution(0), 1.0)
        assert_almost_equal(grid.resolution(2), 0.5)
        assert_almost_equal(grid.resolution(4), 0.25)
    

class TestWGS84TileGrid(object):
    def setup(self):
        self.grid = TileGrid(is_geodetic=True)
    
    def test_resolution(self):
        assert_almost_equal(self.grid.resolution(0), 1.40625)
        assert_almost_equal(self.grid.resolution(1), 1.40625/2)
    
    def test_bbox(self):
        eq_(self.grid.bbox, (-180.0, -90.0, 180.0, 90.0))
    
    def test_grid_size(self):
        eq_(self.grid.grid_sizes[0], (1, 1))
        eq_(self.grid.grid_sizes[1], (2, 1))
        eq_(self.grid.grid_sizes[2], (4, 2))
    
    def test_affected_tiles(self):
        bbox, grid, tiles = self.grid.get_affected_tiles((-180,-90,180,90), (512,256))
        eq_(bbox, (-180.0, -90.0, 180.0, 90.0))
        eq_(grid, (2, 1))
        eq_(list(tiles), [(0, 0, 1), (1, 0, 1)])
    
    def test_affected_level_tiles(self):
        bbox, grid, tiles = self.grid.get_affected_level_tiles((-180,-90,180,90), 1)
        eq_(grid, (2, 1))
        eq_(bbox, (-180.0, -90.0, 180.0, 90.0))
        eq_(list(tiles), [(0, 0, 1), (1, 0, 1)])
        bbox, grid, tiles = self.grid.get_affected_level_tiles((0,0,180,90), 2)
        eq_(grid, (2, 1))
        eq_(bbox, (0.0, 0.0, 180.0, 90.0))
        eq_(list(tiles), [(2, 1, 2), (3, 1, 2)])

class TestWGS83TileGridUL(object):
    def setup(self):
        self.grid = TileGrid(4326, bbox=(-180, -90, 180, 90), origin='ul')
    
    def test_resolution(self):
        assert_almost_equal(self.grid.resolution(0), 1.40625)
        assert_almost_equal(self.grid.resolution(1), 1.40625/2)
    
    def test_bbox(self):
        eq_(self.grid.bbox, (-180.0, -90.0, 180.0, 90.0))
    
    def test_tile_bbox(self):
        eq_(self.grid.tile_bbox((0, 0, 0)), (-180.0, -270.0, 180.0, 90.0))
        eq_(self.grid.tile_bbox((0, 0, 0), limit=True), (-180.0, -90.0, 180.0, 90.0))
        eq_(self.grid.tile_bbox((0, 0, 1)), (-180.0, -90.0, 0.0, 90.0))
    
    def test_tile(self):
        eq_(self.grid.tile(-170, -80, 0), (0, 0, 0))
        eq_(self.grid.tile(-170, -80, 1), (0, 0, 1))
        eq_(self.grid.tile(-170, -80, 2), (0, 1, 2))
        
    def test_grid_size(self):
        eq_(self.grid.grid_sizes[0], (1, 1))
        eq_(self.grid.grid_sizes[1], (2, 1))
        eq_(self.grid.grid_sizes[2], (4, 2))
    
    def test_affected_tiles(self):
        bbox, grid, tiles = self.grid.get_affected_tiles((-180,-90,180,90), (512,256))
        eq_(bbox, (-180.0, -90.0, 180.0, 90.0))
        eq_(grid, (2, 1))
        eq_(list(tiles), [(0, 0, 1), (1, 0, 1)])
    
        bbox, grid, tiles = self.grid.get_affected_tiles((-180,-90,0,90), (512, 512))
        eq_(bbox, (-180.0, -90.0, 0.0, 90.0))
        eq_(grid, (2, 2))
        eq_(list(tiles), [(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2)])
    
    def test_affected_level_tiles(self):
        bbox, grid, tiles = self.grid.get_affected_level_tiles((-180,-90,180,90), 1)
        eq_(grid, (2, 1))
        eq_(bbox, (-180.0, -90.0, 180.0, 90.0))
        eq_(list(tiles), [(0, 0, 1), (1, 0, 1)])
        bbox, grid, tiles = self.grid.get_affected_level_tiles((0,0,180,90), 2)
        eq_(grid, (2, 1))
        eq_(list(tiles), [(2, 0, 2), (3, 0, 2)])
        eq_(bbox, (0.0, 0.0, 180.0, 90.0))
        bbox, grid, tiles = self.grid.get_affected_level_tiles((0,-90,180,90), 2)
        eq_(grid, (2, 2))
        eq_(list(tiles), [(2, 0, 2), (3, 0, 2), (2, 1, 2), (3, 1, 2)])
        eq_(bbox, (0.0, -90.0, 180.0, 90.0))

class TestGKTileGrid(TileGridTest):
    def setup(self):
        self.grid = TileGrid(SRS(31467), bbox=(3250000, 5230000, 3930000, 6110000))
    
    def test_bbox(self):
        assert self.grid.bbox == (3250000, 5230000, 3930000, 6110000)
    
    def test_resolution(self):
        res = self.grid.resolution(0)
        width = self.grid.bbox[2] - self.grid.bbox[0]
        height = self.grid.bbox[3] - self.grid.bbox[1]
        assert height == 880000.0 and width == 680000.0
        assert res == 880000.0/256
    
    def test_tile_bbox(self):
        tile_bbox = self.grid.tile_bbox((0, 0, 0))
        assert tile_bbox == (3250000.0, 5230000.0, 4130000.0, 6110000.0)
    
    def test_tile(self):
        x, y = 3450000, 5890000
        assert [self.grid.tile(x, y, level) for level in range(5)] == \
            [(0, 0, 0), (0, 1, 1), (0, 3, 2), (1, 6, 3), (3, 12, 4)]
    
    def test_grids(self):
        for level, grid_size in [(0, (1, 1)), (1, (2, 2)), (2, (4, 4)), (3, (7, 8))]:
            yield self.check_grid, level, grid_size
    
    def test_closest_level(self):
        assert self.grid.closest_level(880000.0/256) == 0
        assert self.grid.closest_level(600000.0/256) == 1
        assert self.grid.closest_level(440000.0/256) == 1
        assert self.grid.closest_level(420000.0/256) == 1
    
    def test_adjacent_tile_bbox(self):
        t1 = self.grid.tile_bbox((0, 0, 1))
        t2 = self.grid.tile_bbox((1, 0, 1))
        t3 = self.grid.tile_bbox((0, 1, 1))
        assert t1[1] == t2[1]
        assert t1[3] == t2[3]
        assert t1[2] == t2[0]
        assert t1[0] == t3[0]
        assert t1[3] == t3[1]
    

class TestGKTileGridUL(TileGridTest):
    """
    Custom grid with ul origin.
    """
    def setup(self):
        self.grid = TileGrid(SRS(31467),
            bbox=(3300000, 5300000, 3900000, 6000000), origin='ul',
            res=[1500, 1000, 500, 300, 150, 100])

    def test_bbox(self):
        assert self.grid.bbox == (3300000, 5300000, 3900000, 6000000)
    
    def test_tile_bbox(self):
        eq_(self.grid.tile_bbox((0, 0, 0)), 
            (3300000.0, 5616000.0, 3684000.0, 6000000.0))
        eq_(self.grid.tile_bbox((1, 0, 0)), 
            (3684000.0, 5616000.0, 4068000.0, 6000000.0))
        eq_(self.grid.tile_bbox((1, 1, 0)), 
            (3684000.0, 5232000.0, 4068000.0, 5616000.0))
    
    def test_tile(self):
        x, y = 3310000, 5990000
        eq_(self.grid.tile(x, y, 0), (0, 0, 0))
        eq_(self.grid.tile(x, y, 1), (0, 0, 1))
        eq_(self.grid.tile(x, y, 2), (0, 0, 2))

        x, y = 3890000, 5310000
        eq_(self.grid.tile(x, y, 0), (1, 1, 0))
        eq_(self.grid.tile(x, y, 1), (2, 2, 1))
        eq_(self.grid.tile(x, y, 2), (4, 5, 2))
    
    def test_grids(self):
        assert_grid_size(self.grid, 0, (2, 2))
        assert_grid_size(self.grid, 1, (3, 3))
        assert_grid_size(self.grid, 2, (5, 6))
        
    def test_closest_level(self):
        assert self.grid.closest_level(1500) == 0
        assert self.grid.closest_level(1000) == 1
        assert self.grid.closest_level(900) == 1
        assert self.grid.closest_level(600) == 2
    
    def test_adjacent_tile_bbox(self):
        t1 = self.grid.tile_bbox((0, 0, 1))
        t2 = self.grid.tile_bbox((1, 0, 1))
        t3 = self.grid.tile_bbox((0, 1, 1))
        assert t1[1] == t2[1]
        assert t1[3] == t2[3]
        assert t1[2] == t2[0]
        assert t1[0] == t3[0]
        assert t1[1] == t3[3]


class TestOrigins(object):
    def test_basic(self):
        grid = tile_grid(4326, bbox=(-180, -90, 180, 90), origin='ll')
        assert grid.supports_access_with_origin('ll')
        assert not grid.supports_access_with_origin('ul')

        grid = tile_grid(4326, bbox=(-180, -90, 180, 90), origin='ul')
        assert not grid.supports_access_with_origin('ll')
        assert grid.supports_access_with_origin('ul')

    def test_basic_no_level_zero(self):
        grid = tile_grid(4326, bbox=(-180, -90, 180, 90), origin='ll',
            min_res=360/256/2)
        assert grid.supports_access_with_origin('ll')
        assert grid.supports_access_with_origin('ul')

        grid = tile_grid(4326, bbox=(-180, -90, 180, 90), origin='ul',
            min_res=360/256/2)
        assert grid.supports_access_with_origin('ll')
        assert grid.supports_access_with_origin('ul')

    def test_custom_with_match(self):
        # height is divisible by res*tile_size
        grid = tile_grid(4326, bbox=(0, 0, 1024, 1024), origin='ll',
            min_res=1)
        assert grid.supports_access_with_origin('ll')
        assert grid.supports_access_with_origin('ul')

        grid = tile_grid(4326, bbox=(0, 0, 1024, 1024), origin='ul',
            min_res=1)
        assert grid.supports_access_with_origin('ll')
        assert grid.supports_access_with_origin('ul')

    def test_custom_without_match(self):
        # height is not divisible by res*tile_size
        grid = tile_grid(4326, bbox=(0, 0, 1024, 1000), origin='ll',
            min_res=1)
        assert grid.supports_access_with_origin('ll')
        assert not grid.supports_access_with_origin('ul')

        grid = tile_grid(4326, bbox=(0, 0, 1024, 1000), origin='ul',
            min_res=1)
        assert not grid.supports_access_with_origin('ll')
        assert grid.supports_access_with_origin('ul')
    
    def test_custom_res_with_match(self):
        grid = tile_grid(4326, bbox=(0, 0, 1024, 1024), origin='ll',
            res=[1, 0.5, 0.25])
        assert grid.supports_access_with_origin('ll')
        assert grid.supports_access_with_origin('ul')

        grid = tile_grid(4326, bbox=(0, 0, 1024, 1024), origin='ul',
            res=[1, 0.5, 0.25])
        assert grid.supports_access_with_origin('ll')
        assert grid.supports_access_with_origin('ul')
    
    def test_custom_res_without_match(self):
        grid = tile_grid(4326, bbox=(0, 0, 1024, 1023), origin='ll',
            res=[1, 0.5, 0.25])
        assert grid.supports_access_with_origin('ll')
        assert not grid.supports_access_with_origin('ul')

        grid = tile_grid(4326, bbox=(0, 0, 1024, 1023), origin='ul',
            res=[1, 0.5, 0.25])
        assert not grid.supports_access_with_origin('ll')
        assert grid.supports_access_with_origin('ul')
    
class TestFixedResolutionsTileGrid(TileGridTest):
    def setup(self):
        self.res = [1000.0, 500.0, 200.0, 100.0, 50.0, 20.0, 5.0]
        bbox = (3250000, 5230000, 3930000, 6110000)
        self.grid = TileGrid(SRS(31467), bbox=bbox, res=self.res)
    
    def test_resolution(self):
        for level, res in enumerate(self.res):
            assert res == self.grid.resolution(level)

    def test_closest_level(self):
        assert self.grid.closest_level(2000) == 0
        assert self.grid.closest_level(1000) == 0
        assert self.grid.closest_level(950) == 0
        assert self.grid.closest_level(210) == 2
    
    def test_affected_tiles(self):
        req_bbox = (3250000, 5230000, 3930000, 6110000)
        self.grid.max_shrink_factor = 10
        bbox, grid_size, tiles = \
            self.grid.get_affected_tiles(req_bbox, (256, 256))
        assert bbox == (req_bbox[0], req_bbox[1],
                        req_bbox[0]+1000*256*3, req_bbox[1]+1000*256*4)
        assert grid_size == (3, 4)
        tiles = list(tiles)
        assert tiles == [(0, 3, 0), (1, 3, 0), (2, 3, 0),
                         (0, 2, 0), (1, 2, 0), (2, 2, 0),
                         (0, 1, 0), (1, 1, 0), (2, 1, 0),
                         (0, 0, 0), (1, 0, 0), (2, 0, 0),
                         ]
    
    def test_affected_tiles_2(self):
        req_bbox = (3250000, 5230000, 3930000, 6110000)
        self.grid.max_shrink_factor = 2.0
        try:
            bbox, grid_size, tiles = \
                self.grid.get_affected_tiles(req_bbox, (256, 256))
        except NoTiles:
            pass
        else:
            assert False, 'got no exception'
    def test_grid(self):
        for level, grid_size in [(0, (3, 4)), (1, (6, 7)), (2, (14, 18))]:
            yield self.check_grid, level, grid_size
    
    def test_tile_bbox(self):
        tile_bbox = self.grid.tile_bbox((0, 0, 0)) # w: 1000x256
        assert tile_bbox == (3250000.0, 5230000.0, 3506000.0, 5486000.0)
        tile_bbox = self.grid.tile_bbox((0, 0, 1)) # w: 500x256
        assert tile_bbox == (3250000.0, 5230000.0, 3378000.0, 5358000.0)
        tile_bbox = self.grid.tile_bbox((0, 0, 2)) # w: 200x256
        assert tile_bbox == (3250000.0, 5230000.0, 3301200.0, 5281200.0)
    
class TestGeodeticTileGrid(TileGridTest):
    def setup(self):
        self.grid = TileGrid(is_geodetic=True, )
    def test_auto_resolution(self):
        grid = TileGrid(is_geodetic=True, bbox=(-10, 30, 10, 40), tile_size=(20, 20))
        tile_bbox = grid.tile_bbox((0, 0, 0))
        assert tile_bbox == (-10, 30, 10, 50)
        assert grid.resolution(0) == 1.0
    
    def test_grid(self):
        for level, grid_size in [(0, (1, 1)), (1, (2, 1)), (2, (4, 2))]:
            yield self.check_grid, level, grid_size
    
    def test_adjacent_tile_bbox(self):
        grid = TileGrid(is_geodetic=True, bbox=(-10, 30, 10, 40), tile_size=(20, 20))
        t1 = grid.tile_bbox((0, 0, 2))
        t2 = grid.tile_bbox((1, 0, 2))
        t3 = grid.tile_bbox((0, 1, 2))
        assert t1[1] == t2[1]
        assert t1[3] == t2[3]
        assert t1[2] == t2[0]
        assert t1[0] == t3[0]
        assert t1[2] == t3[2]
        assert t1[3] == t3[1]
    
    def test_w_resolution(self):
        res = [1, 0.5, 0.2]
        grid = TileGrid(is_geodetic=True, bbox=(-10, 30, 10, 40), tile_size=(20, 20), res=res)
        assert grid.grid_sizes[0] == (1, 1)
        assert grid.grid_sizes[1] == (2, 1)
        assert grid.grid_sizes[2] == (5, 3)
    
    def test_tile(self):
        assert self.grid.tile(-180, -90, 0) == (0, 0, 0)
        assert self.grid.tile(-180, -90, 1) == (0, 0, 1)
        assert self.grid.tile(-180, -90, 2) == (0, 0, 2)
        assert self.grid.tile(180-0.001, 90-0.001, 0) == (0, 0, 0)
        assert self.grid.tile(10, 50, 1) == (1, 0, 1)

    def test_affected_tiles(self):
        bbox, grid_size, tiles = \
            self.grid.get_affected_tiles((-45,-45,45,45), (512,512))
        assert self.grid.grid_sizes[3] == (8, 4)
        assert bbox == (-45.0, -45.0, 45.0, 45.0)
        assert grid_size == (2, 2)
        tiles = list(tiles)
        assert tiles == [(3, 2, 3), (4, 2, 3), (3, 1, 3), (4, 1, 3)]

class TestTileGrid(object):
    def test_tile_out_of_grid_bounds(self):
        grid = TileGrid(is_geodetic=True)
        eq_(grid.tile(-180.01, 50, 1), (-1, 0, 1))
        
    def test_affected_tiles_out_of_grid_bounds(self):
        grid = TileGrid()
        #bbox from open layers
        req_bbox = (-30056262.509599999, -10018754.170400001, -20037508.339999996, -0.00080000050365924835)
        bbox, grid_size, tiles = \
            grid.get_affected_tiles(req_bbox, (256, 256))
        assert_almost_equal_bbox(bbox, req_bbox)
        eq_(grid_size, (1, 1))
        tiles = list(tiles)
        eq_(tiles, [None])
    def test_broken_bbox(self):
        grid = TileGrid()
        # broken request from "ArcGIS Client Using WinInet"
        req_bbox = (-10000855.0573254,2847125.18913603,-9329367.42767611,4239924.78564583)
        try:
            grid.get_affected_tiles(req_bbox, (256, 256), req_srs=SRS(31467))
        except TransformationError:
            pass
        else:
            assert False, 'Expected TransformationError'

class TestTileGridThreshold(object):
    def test_lower_bound(self):
        # thresholds near the next lower res value
        grid = TileGrid(res=[1000, 500, 250, 100, 50], threshold_res=[300, 110])
        grid.stretch_factor = 1.1
        eq_(grid.closest_level(1100), 0)
        # regular transition (w/stretchfactor)
        eq_(grid.closest_level(950), 0)
        eq_(grid.closest_level(800), 1)
        eq_(grid.closest_level(500), 1)
        # transition at threshold
        eq_(grid.closest_level(301), 1)
        eq_(grid.closest_level(300), 2)
        eq_(grid.closest_level(250), 2)
        # transition at threshold
        eq_(grid.closest_level(111), 2)
        eq_(grid.closest_level(110), 3)
        eq_(grid.closest_level(100), 3)
        # regular transition (w/stretchfactor)
        eq_(grid.closest_level(92), 3)
        eq_(grid.closest_level(90), 4)
    def test_upper_bound(self):
        # thresholds near the next upper res value (within threshold)
        grid = TileGrid(res=[1000, 500, 250, 100, 50], threshold_res=[495, 240])
        grid.stretch_factor = 1.1
        eq_(grid.closest_level(1100), 0)
        # regular transition (w/stretchfactor)
        eq_(grid.closest_level(950), 0)
        eq_(grid.closest_level(800), 1)
        eq_(grid.closest_level(500), 1)
        # transition at threshold
        eq_(grid.closest_level(496), 1)
        eq_(grid.closest_level(495), 2)
        eq_(grid.closest_level(250), 2)
        # transition at threshold (within strechfactor)
        eq_(grid.closest_level(241), 2)
        eq_(grid.closest_level(240), 3)
        eq_(grid.closest_level(100), 3)
        # regular transition (w/stretchfactor)
        eq_(grid.closest_level(92), 3)
        eq_(grid.closest_level(90), 4)

        
class TestCreateTileList(object):
    def test(self):
        xs = range(-1, 2)
        ys = range(-2, 3)
        grid_size = (1, 2)
        tiles = list(_create_tile_list(xs, ys, 3, grid_size))
        
        expected = [None, None, None,
                    None, None, None, 
                    None, (0, 0, 3), None,
                    None, (0, 1, 3), None,
                    None, None, None]
        eq_(expected, tiles)
        
    def _create_tile_list(self, xs, ys, level, grid_size):
        x_limit = grid_size[0]
        y_limit = grid_size[1]
        for y in ys:
            for x in xs:
                if x < 0 or y < 0 or x >= x_limit or y >= y_limit:
                    yield None
                else:
                    yield x, y, level


class TestBBOXIntersects(object):
    def test_no_intersect(self):
        b1 = (0, 0, 10, 10)
        b2 = (20, 20, 30, 30)
        assert not bbox_intersects(b1, b2)
        assert not bbox_intersects(b2, b1)

    def test_no_intersect_only_vertical(self):
        b1 = (0, 0, 10, 10)
        b2 = (20, 0, 30, 10)
        assert not bbox_intersects(b1, b2)
        assert not bbox_intersects(b2, b1)

    def test_no_intersect_touch_point(self):
        b1 = (0, 0, 10, 10)
        b2 = (10, 10, 20, 20)
        assert not bbox_intersects(b1, b2)
        assert not bbox_intersects(b2, b1)

    def test_no_intersect_touch_side(self):
        b1 = (0, 0, 10, 10)
        b2 = (0, 10, 10, 20)
        assert not bbox_intersects(b1, b2)
        assert not bbox_intersects(b2, b1)

    def test_full_contains(self):
        b1 = (0, 0, 10, 10)
        b2 = (2, 2, 8, 8)
        assert bbox_intersects(b1, b2)
        assert bbox_intersects(b2, b1)

    def test_overlap(self):
        b1 = (0, 0, 10, 10)
        b2 = (-5, -5, 5, 5)
        assert bbox_intersects(b1, b2)
        assert bbox_intersects(b2, b1)


class TestBBOXContains(object):
    def test_no_intersect(self):
        b1 = (0, 0, 10, 10)
        b2 = (20, 20, 30, 30)
        assert not bbox_contains(b1, b2)
        assert not bbox_contains(b2, b1)

    def test_no_intersect_only_vertical(self):
        b1 = (0, 0, 10, 10)
        b2 = (20, 0, 30, 10)
        assert not bbox_contains(b1, b2)
        assert not bbox_contains(b2, b1)

    def test_no_intersect_touch_point(self):
        b1 = (0, 0, 10, 10)
        b2 = (10, 10, 20, 20)
        assert not bbox_contains(b1, b2)
        assert not bbox_contains(b2, b1)

    def test_no_intersect_touch_side(self):
        b1 = (0, 0, 10, 10)
        b2 = (0, 10, 10, 20)
        assert not bbox_contains(b1, b2)
        assert not bbox_contains(b2, b1)

    def test_full_contains(self):
        b1 = (0, 0, 10, 10)
        b2 = (2, 2, 8, 8)
        assert bbox_contains(b1, b2)
        assert not bbox_contains(b2, b1)

    def test_overlap(self):
        b1 = (0, 0, 10, 10)
        b2 = (-5, -5, 5, 5)
        assert not bbox_contains(b1, b2)
        assert not bbox_contains(b2, b1)

def assert_almost_equal_bbox(bbox1, bbox2, places=2):
    for coord1, coord2 in zip(bbox1, bbox2):
        assert_almost_equal(coord1, coord2, places)


class TestResolutionRange(object):
    def test_meter(self):
        res_range = ResolutionRange(1000, 10)
        assert not res_range.contains([0, 0, 100000, 100000], (10, 10), SRS(900913))
        assert not res_range.contains([0, 0, 100000, 100000], (99, 99), SRS(900913))
        # min is exclusive but there is a delta
        assert     res_range.contains([0, 0, 100000, 100000], (100, 100), SRS(900913))
        assert     res_range.contains([0, 0, 100000, 100000], (1000, 1000), SRS(900913))
        # max is inclusive
        assert     res_range.contains([0, 0, 100000, 100000], (10000, 10000), SRS(900913))
        assert not res_range.contains([0, 0, 100000, 100000], (10001, 10001), SRS(900913))
    def test_deg(self):
        res_range = ResolutionRange(100000, 1000)
        assert not res_range.contains([0, 0, 10, 10], (10, 10), SRS(4326))
        assert not res_range.contains([0, 0, 10, 10], (11, 11), SRS(4326))
        assert     res_range.contains([0, 0, 10, 10], (12, 12), SRS(4326))
        assert     res_range.contains([0, 0, 10, 10], (100, 100), SRS(4326))
        assert     res_range.contains([0, 0, 10, 10], (1000, 1000), SRS(4326))
        assert     res_range.contains([0, 0, 10, 10], (1100, 1100), SRS(4326))
        assert not res_range.contains([0, 0, 10, 10], (1200, 1200), SRS(4326))
    
    def test_no_min(self):
        res_range = ResolutionRange(None, 10)
        assert     res_range.contains([0, 0, 100000, 100000], (1, 1), SRS(900913))
        assert     res_range.contains([0, 0, 100000, 100000], (10, 10), SRS(900913))
        assert     res_range.contains([0, 0, 100000, 100000], (99, 99), SRS(900913))
        assert     res_range.contains([0, 0, 100000, 100000], (100, 100), SRS(900913))
        assert     res_range.contains([0, 0, 100000, 100000], (1000, 1000), SRS(900913))
        # max is inclusive
        assert     res_range.contains([0, 0, 100000, 100000], (10000, 10000), SRS(900913))
        assert not res_range.contains([0, 0, 100000, 100000], (10001, 10001), SRS(900913))

    def test_no_max(self):
        res_range = ResolutionRange(1000, None)
        assert not res_range.contains([0, 0, 100000, 100000], (10, 10), SRS(900913))
        assert not res_range.contains([0, 0, 100000, 100000], (99, 99), SRS(900913))
        # min is exclusive but there is a delta
        assert     res_range.contains([0, 0, 100000, 100000], (100, 100), SRS(900913))
        assert     res_range.contains([0, 0, 100000, 100000], (1000, 1000), SRS(900913))
        assert     res_range.contains([0, 0, 100000, 100000], (10000, 10000), SRS(900913))
        assert     res_range.contains([0, 0, 100000, 100000], (10001, 10001), SRS(900913))
        assert     res_range.contains([0, 0, 100000, 100000], (1000000, 100000), SRS(900913))

    def test_none(self):
        res_range = resolution_range(None, None)
        assert res_range.contains([0, 0, 100000, 100000], (1, 1), SRS(900913))
        assert res_range.contains([0, 0, 100000, 100000], (1000000, 100000), SRS(900913))        

    def test_from_scale(self):
        res_range = resolution_range(max_scale=1e6, min_scale=1e3)
        assert_almost_equal(res_range.min_res, 280)
        assert_almost_equal(res_range.max_res, 0.28)
    
    @raises(ValueError)
    def check_invalid_combination(self, min_res, max_res, max_scale, min_scale):
        resolution_range(min_res, max_res, max_scale, min_scale)
    
    def test_invalid_combinations(self):
        yield self.check_invalid_combination, 10, None, 10, None
        yield self.check_invalid_combination, 10, 20, 10, None
        yield self.check_invalid_combination, 10, None, 10, 20
        yield self.check_invalid_combination, 10, 20, 10, 20
    
    @raises(AssertionError)
    def test_wrong_order_res(self):
         resolution_range(min_res=10, max_res=100)

    @raises(AssertionError)
    def test_wrong_order_scale(self):
         resolution_range(min_scale=100, max_scale=10)
        
    
    def test_merge_resolutions(self):
        res_range = merge_resolution_range(
            ResolutionRange(None, 10), ResolutionRange(1000, None))
        eq_(res_range.min_res, None)
        eq_(res_range.max_res, None)

        res_range = merge_resolution_range(
            ResolutionRange(10000, 10), ResolutionRange(1000, None))
        eq_(res_range.min_res, 10000)
        eq_(res_range.max_res, None)

        res_range = merge_resolution_range(
            ResolutionRange(10000, 10), ResolutionRange(1000, 1))
        eq_(res_range.min_res, 10000)
        eq_(res_range.max_res, 1)
        
        res_range = merge_resolution_range(
            ResolutionRange(10000, 10), ResolutionRange(None, None))
        eq_(res_range.min_res, None)
        eq_(res_range.max_res, None)
        
        res_range = merge_resolution_range(
            None, ResolutionRange(None, None))
        eq_(res_range, None)
        
        res_range = merge_resolution_range(
            ResolutionRange(10000, 10), None)
        eq_(res_range, None)
    
    def test_eq(self):
        assert resolution_range(None, None) == resolution_range(None, None)
        assert resolution_range(None, 100) == resolution_range(None, 100.0)
        assert resolution_range(None, 100) != resolution_range(None, 100.1)
        assert resolution_range(1000, 100) == resolution_range(1000, 100)
        assert resolution_range(1000, 100) == resolution_range(1000.0, 100)
        assert resolution_range(1000, 100) != resolution_range(1000.1, 100)
        
        
