import Image

from mapproxy.core.cache import (
    FileCache,
    TileManager,
    Source,
    TiledSource,
    WMSSource,
    InvalidTileRequest,
    Tile,
)
from mapproxy.core.grid import TileGrid
from mapproxy.core.srs import SRS
from mapproxy.core.image import ImageSource

from nose.tools import eq_, raises

class MockTileClient(object):
    def __init__(self):
        self.requested_tiles = []
    
    def get_tile(self, tile_coord):
        self.requested_tiles.append(tile_coord)

class TestTiledSourceGlobalGeodetic(object):
    def setup(self):
        self.grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        self.client = MockTileClient()
        self.source = TiledSource(self.grid, self.client)
    def test_match(self):
        self.source.get([-180, -90, 0, 90], (256, 256), SRS(4326))
        self.source.get([0, -90, 180, 90], (256, 256), SRS(4326))
        eq_(self.client.requested_tiles, [(0, 0, 1), (1, 0, 1)])
    @raises(InvalidTileRequest)
    def test_wrong_size(self):
        self.source.get([-180, -90, 0, 90], (512, 256), SRS(4326))
    @raises(InvalidTileRequest)
    def test_wrong_srs(self):
        self.source.get([-180, -90, 0, 90], (512, 256), SRS(4326))


class MockFileCache(FileCache):
    def __init__(self, *args):
        FileCache.__init__(self, *args)
        self.stored_tiles = set()
    
    def store(self, tile):
        self.stored_tiles.add(tile.coord)
    
    def is_cached(self, tile):
        return tile.coord in self.stored_tiles
    
class TestTileManagerTiledSource(object):
    def setup(self):
        self.file_cache = MockFileCache('/dev/null', 'png')
        self.grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        self.client = MockTileClient()
        self.source = TiledSource(self.grid, self.client)
        self.tile_mgr = TileManager(self.grid, self.file_cache, [self.source])
    
    def test_create_tiles(self):
        self.tile_mgr._create_tiles([Tile((0, 0, 1)), Tile((1, 0, 1))])
        eq_(self.file_cache.stored_tiles, set([(0, 0, 1), (1, 0, 1)]))
        eq_(self.client.requested_tiles, [(0, 0, 1), (1, 0, 1)])

class TestTileManagerDifferentSourceGrid(object):
    def setup(self):
        self.file_cache = MockFileCache('/dev/null', 'png')
        self.grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        self.source_grid = TileGrid(SRS(4326), bbox=[0, -90, 180, 90])
        self.client = MockTileClient()
        self.source = TiledSource(self.source_grid, self.client)
        self.tile_mgr = TileManager(self.grid, self.file_cache, [self.source])
    
    def test_create_tiles(self):
        self.tile_mgr._create_tiles([Tile((1, 0, 1))])
        eq_(self.file_cache.stored_tiles, set([(1, 0, 1)]))
        eq_(self.client.requested_tiles, [(0, 0, 0)])
    
    @raises(InvalidTileRequest)
    def test_create_tiles_out_of_bounds(self):
        self.tile_mgr._create_tiles([Tile((0, 0, 0))])

class MockWMSSource(Source):
    def __init__(self, *args):
        Source.__init__(self, *args)
        self.requested = []
    
    def get(self, bbox, size, srs):
        self.requested.append((bbox, size, srs))

class TestTileManagerWMSSource(object):
    def setup(self):
        self.file_cache = MockFileCache('/dev/null', 'png')
        self.grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        self.source = MockWMSSource()
        self.tile_mgr = TileManager(self.grid, self.file_cache, [self.source])
    
    def test_create_tile(self):
        self.tile_mgr._create_tiles([Tile((0, 0, 1)), Tile((1, 0, 1))])
        eq_(self.file_cache.stored_tiles, set([(0, 0, 1), (1, 0, 1)]))
        eq_(self.source.requested,
            [((-180.0, -90.0, 0.0, 90.0), (256, 256), SRS(4326)),
             ((0.0, -90.0, 180.0, 90.0), (256, 256), SRS(4326))])

class MockWMSClient(object):
    def __init__(self):
        self.requested = []
    
    def get_map(self, bbox, size, srs):
        self.requested.append((bbox, size, srs))
        return ImageSource(Image.new('RGBA', size))

class TestTileManagerWMSSource(object):
    def setup(self):
        self.file_cache = MockFileCache('/dev/null', 'png')
        self.grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        self.client = MockWMSClient()
        self.source = WMSSource(self.client)
        self.tile_mgr = TileManager(self.grid, self.file_cache, [self.source],
            meta_size=[2, 2], meta_buffer=0)
    
    def test_create_tile_first_level(self):
        self.tile_mgr._create_tiles([Tile((0, 0, 1)), Tile((1, 0, 1))])
        eq_(self.file_cache.stored_tiles, set([(0, 0, 1), (1, 0, 1)]))
        eq_(self.client.requested,
            [((-180.0, -90.0, 180.0, 90.0), (512, 256), SRS(4326))])
    def test_create_tile(self):
        self.tile_mgr._create_tiles([Tile((0, 0, 2))])
        eq_(self.file_cache.stored_tiles,
            set([(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2)]))
        eq_(self.client.requested,
            [((-180.0, -90.0, 0.0, 90.0), (512, 512), SRS(4326))])
    def test_create_tiles(self):
        self.tile_mgr._create_tiles([Tile((0, 0, 2)), Tile((2, 0, 2))])
        eq_(self.file_cache.stored_tiles,
            set([(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2),
                 (2, 0, 2), (3, 0, 2), (2, 1, 2), (3, 1, 2)]))
        eq_(self.client.requested,
            [((-180.0, -90.0, 0.0, 90.0), (512, 512), SRS(4326)),
            ((0.0, -90.0, 180.0, 90.0), (512, 512), SRS(4326))])

    def test_load_tile_coords(self):
        tiles = self.tile_mgr.load_tile_coords(((0, 0, 2), (2, 0, 2)))
        eq_(tiles[0].coord, (0, 0, 2))
        assert isinstance(tiles[0].source, ImageSource)
        eq_(tiles[1].coord, (2, 0, 2))
        assert isinstance(tiles[1].source, ImageSource)
        
        eq_(self.file_cache.stored_tiles,
            set([(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2),
                 (2, 0, 2), (3, 0, 2), (2, 1, 2), (3, 1, 2)]))
        eq_(self.client.requested,
            [((-180.0, -90.0, 0.0, 90.0), (512, 512), SRS(4326)),
            ((0.0, -90.0, 180.0, 90.0), (512, 512), SRS(4326))])