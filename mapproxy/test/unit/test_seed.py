from mapproxy.seed import Seeder, SeedTask
from mapproxy.cache.tile import TileManager
from mapproxy.source.tile import TiledSource
from mapproxy.grid import TileGrid
from mapproxy.srs import SRS

from collections import defaultdict
from nose.tools import eq_
from nose.plugins.skip import SkipTest

try:
    from shapely.wkt import loads as load_wkt
except ImportError:
    load_wkt = None

class MockSeedPool(object):
    def __init__(self):
        self.seeded_tiles = defaultdict(set)
    def seed(self, tiles, progess):
        for x, y, level in tiles:
            self.seeded_tiles[level].add((x, y))
            
class MockCache(object):
    def is_cached(self, tile):
        return False

class TestSeeder(object):
    def setup(self):
        self.grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        self.source = TiledSource(self.grid, None)
        self.tile_mgr = TileManager(self.grid, MockCache(), [self.source], 'png')
        self.seed_pool = MockSeedPool()
        
    def test_seed_full_bbox(self):
        task = SeedTask([-180, -90, 180, 90], [0, 2], SRS(4326), SRS(4326))
        seeder = Seeder(self.tile_mgr, task, self.seed_pool)
        seeder.seed()
        
        eq_(len(self.seed_pool.seeded_tiles), 3)
        eq_(self.seed_pool.seeded_tiles[0], set([(0, 0)]))
        eq_(self.seed_pool.seeded_tiles[1], set([(0, 0), (1, 0)]))
        eq_(self.seed_pool.seeded_tiles[2], set([(0, 0), (1, 0), (2, 0), (3, 0),
                                                 (0, 1), (1, 1), (2, 1), (3, 1)]))
    
    def test_seed_small_bbox(self):
        task = SeedTask([-45, 0, 180, 90], [0, 2], SRS(4326), SRS(4326))
        seeder = Seeder(self.tile_mgr, task, self.seed_pool)
        seeder.seed()
        
        eq_(len(self.seed_pool.seeded_tiles), 3)
        eq_(self.seed_pool.seeded_tiles[0], set([(0, 0)]))
        eq_(self.seed_pool.seeded_tiles[1], set([(0, 0), (1, 0)]))
        eq_(self.seed_pool.seeded_tiles[2], set([(1, 1), (2, 1), (3, 1)]))
    
    def test_seed_small_bbox_transformed(self):
        bbox = SRS(4326).transform_bbox_to(SRS(900913), [-45, 0, 180, 90])
        task = SeedTask(bbox, [0, 2], SRS(900913), SRS(4326))
        seeder = Seeder(self.tile_mgr, task, self.seed_pool)
        seeder.seed()
        
        eq_(len(self.seed_pool.seeded_tiles), 3)
        eq_(self.seed_pool.seeded_tiles[0], set([(0, 0)]))
        eq_(self.seed_pool.seeded_tiles[1], set([(0, 0), (1, 0)]))
        eq_(self.seed_pool.seeded_tiles[2], set([(1, 1), (2, 1), (3, 1)]))
    
    def test_seed_with_geom(self):
        if not load_wkt: raise SkipTest('no shapely installed')
        geom = load_wkt("POLYGON((10 10, 10 50, -10 60, 10 70, 80 80, 80 10, 10 10))")
        task = SeedTask(geom.bounds, [0, 4], SRS(4326), SRS(4326), geom=geom)
        seeder = Seeder(self.tile_mgr, task, self.seed_pool)
        seeder.seed()
        
        eq_(len(self.seed_pool.seeded_tiles), 5)
        eq_(self.seed_pool.seeded_tiles[0], set([(0, 0)]))
        eq_(self.seed_pool.seeded_tiles[1], set([(0, 0), (1, 0)]))
        eq_(self.seed_pool.seeded_tiles[2], set([(1, 1), (2, 1)]))
        eq_(self.seed_pool.seeded_tiles[3], set([(4, 2), (5, 2), (4, 3), (5, 3), (3, 3)]))
        eq_(len(self.seed_pool.seeded_tiles[4]), 18)
        