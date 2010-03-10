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

from nose.tools import eq_, assert_almost_equals
from mapproxy.core.grid import MetaGrid, TileGrid, _create_tile_list
from mapproxy.core.srs import SRS, TransformationError

def test_metagrid_bbox():
    mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2))
    bbox = mgrid.meta_bbox((0, 0, 2))
    assert bbox == (-20037508.342789244, -20037508.342789244, 0.0, 0.0)
    bbox = mgrid.meta_bbox((1, 1, 2))
    assert bbox == (-20037508.342789244, -20037508.342789244, 0.0, 0.0)
    bbox = mgrid.meta_bbox((4, 5, 3))
    assert bbox == (0.0, 0.0, 10018754.171394622, 10018754.171394622)

def test_metagrid_bbox_w_meta_size():
    mgrid = MetaGrid(grid=TileGrid(), meta_size=(4, 2))
    bbox = mgrid.meta_bbox((4, 5, 3))
    assert bbox == (0.0, 0.0, 20037508.342789244, 10018754.171394622)

def test_metagrid_bbox_w_meta_buffer():    
    mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2), meta_buffer=10)
    assert mgrid.grid.resolution(2) == 39135.758482010242
    bbox = mgrid.meta_bbox((0, 0, 2))
    assert bbox == (-20428865.927609347, -20428865.927609347,
                    391357.58482010243, 391357.58482010243)

def test_metagrid_tiles():
    mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2))
    assert list(mgrid.tiles((0, 0, 0))) == \
        [((0, 0, 0), (0, 0))]
    assert list(mgrid.tiles((0, 1, 1))) == \
        [((0, 1, 1), (0, 0)), ((1, 1, 1), (256, 0)), 
         ((0, 0, 1), (0, 256)), ((1, 0, 1), (256, 256))]
         
    assert list(mgrid.tiles((1, 2, 2))) == \
        [((0, 3, 2), (0, 0)), ((1, 3, 2), (256, 0)), 
         ((0, 2, 2), (0, 256)), ((1, 2, 2), (256, 256))]
    
def test_metagrid_tiles_w_meta_size():
    mgrid = MetaGrid(grid=TileGrid(), meta_size=(4, 2))
    assert list(mgrid.tiles((1, 2, 2))) == \
        [((0, 3, 2), (0, 0)), ((1, 3, 2), (256, 0)),
         ((2, 3, 2), (512, 0)), ((3, 3, 2), (768, 0)),
         ((0, 2, 2), (0, 256)), ((1, 2, 2), (256, 256)),
         ((2, 2, 2), (512, 256)), ((3, 2, 2), (768, 256))]
    
def test_metagrid_tiles_w_meta_buffer():
    mgrid = MetaGrid(grid=TileGrid(), meta_size=(4, 2), meta_buffer=10)
    assert list(mgrid.tiles((0, 0, 0))) == \
        [((0, 0, 0), (0, 0))]
    assert list(mgrid.tiles((1, 2, 2))) == \
        [((0, 3, 2), (10, 10)), ((1, 3, 2), (266, 10)),
         ((2, 3, 2), (522, 10)), ((3, 3, 2), (778, 10)),
         ((0, 2, 2), (10, 266)), ((1, 2, 2), (266, 266)),
         ((2, 2, 2), (522, 266)), ((3, 2, 2), (778, 266))]

def test_metagrid_tiles_geodetic():
    mgrid = MetaGrid(grid=TileGrid(is_geodetic=True, ), meta_size=(2, 2), meta_buffer=10)
    assert list(mgrid.tiles((0, 0, 0))) == \
        [((0, 0, 0), (0, 0))]
    assert list(mgrid.tiles((0, 0, 1))) == \
        [((0, 0, 1), (10, 10)), ((1, 0, 1), (266, 10))]
    assert mgrid.tile_size(1) == (532, 276)
    assert mgrid.meta_bbox((0, 0, 1)) == (-187.03125, -97.03125, 187.03125, 97.03125)

class TileGridTest(object):
    def check_grid(self, level, grid_size):
        print self.grid.grid_sizes[level], "==", grid_size
        assert self.grid.grid_sizes[level] == grid_size
        res = self.grid.resolutions[level]
        x, y = grid_size
        assert res * x * 256 >= self.grid.bbox[2] - self.grid.bbox[0]
        assert res * y * 256 >= self.grid.bbox[3] - self.grid.bbox[1]


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
        assert_almost_equals(grid.resolution(2), 0.5)
        assert_almost_equals(grid.resolution(4), 0.25)
    

class TestWGS84TileGrid(object):
    def setup(self):
        self.grid = TileGrid(is_geodetic=True)
    
    def test_resolution(self):
        assert_almost_equals(self.grid.resolution(0), 1.40625)
        assert_almost_equals(self.grid.resolution(1), 1.40625/2)
    
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
    

class TestGKTileGrid(TileGridTest):
    def setup(self):
        self.grid = TileGrid(epsg=31467, bbox=(3250000, 5230000, 3930000, 6110000))
    
    def test_bbox(self):
        assert self.grid.bbox == (3250000, 5230000, 3930000, 6110000)
    
    def test__get_south_west_point(self):
        assert self.grid._get_south_west_point((0, 0, 0)) == (3250000, 5230000)
    
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
        assert t1[1] == t2[1]
        assert t1[3] == t2[3]
        assert t1[2] == t2[0]
    

class TestFixedResolutionsTileGrid(TileGridTest):
    def setup(self):
        self.res = [1000.0, 500.0, 200.0, 100.0, 50.0, 20.0, 5.0]
        bbox = (3250000, 5230000, 3930000, 6110000)
        self.grid = TileGrid(epsg=31467, bbox=bbox, res=self.res)
    
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
    
    def test_affected_tiles_inverse(self):
        bbox, grid_size, tiles = \
            self.grid.get_affected_tiles((-45,-45,45,45), (512,512), inverse=True)
        assert self.grid.grid_sizes[3] == (8, 4)
        assert bbox == (-45.0, -45.0, 45.0, 45.0)
        assert grid_size == (2, 2)
        tiles = list(tiles)
        assert tiles == [(3, 1, 3), (4, 1, 3), (3, 2, 3), (4, 2, 3)]

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

def assert_almost_equal_bbox(bbox1, bbox2, places=2):
    for coord1, coord2 in zip(bbox1, bbox2):
        assert_almost_equals(coord1, coord2, places)