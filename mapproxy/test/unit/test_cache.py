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


import base64
import os
import re
import shutil
import tempfile
import threading
import time

from io import BytesIO
from collections import defaultdict

import pytest

from mapproxy.cache.base import TileLocker
from mapproxy.cache.file import FileCache
from mapproxy.cache.tile import Tile, TileManager
from mapproxy.client.http import HTTPClient
from mapproxy.client.wms import WMSClient
from mapproxy.compat.image import Image
from mapproxy.grid import TileGrid, resolution_range
from mapproxy.image import ImageSource, BlankImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.layer import (
    BlankImage,
    CacheMapLayer,
    DirectMapLayer,
    MapBBOXError,
    MapExtent,
    MapLayer,
    MapQuery,
    ResolutionConditional,
    SRSConditional,
)
from mapproxy.request.wms import WMS111MapRequest
from mapproxy.source import InvalidSourceQuery, SourceError
from mapproxy.source.tile import TiledSource
from mapproxy.source.wms import WMSSource
from mapproxy.source.error import HTTPSourceErrorHandler
from mapproxy.srs import SRS, SupportedSRS, PreferredSrcSRS
from mapproxy.test.http import assert_query_eq, wms_query_eq, query_eq, mock_httpd
from mapproxy.test.image import create_debug_img, is_png, tmp_image, create_tmp_image_buf
from mapproxy.util.coverage import BBOXCoverage


TEST_SERVER_ADDRESS = ('127.0.0.1', 56413)
GLOBAL_GEOGRAPHIC_EXTENT = MapExtent((-180, -90, 180, 90), SRS(4326))

tmp_lock_dir = None
def setup():
    global tmp_lock_dir
    tmp_lock_dir = tempfile.mkdtemp()

def teardown():
    shutil.rmtree(tmp_lock_dir)

class counting_set(object):
    def __init__(self, items):
        self.data = defaultdict(int)
        for item in items:
            self.data[item] += 1
    def add(self, item):
        self.data[item] += 1

    def __repr__(self):
        return 'counting_set(%r)' % dict(self.data)

    def __eq__(self, other):
        return self.data == other.data

class MockTileClient(object):
    def __init__(self):
        self.requested_tiles = []

    def get_tile(self, tile_coord, format=None):
        self.requested_tiles.append(tile_coord)
        return ImageSource(create_debug_img((256, 256)))

class TestTiledSourceGlobalGeodetic(object):
    def setup(self):
        self.grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        self.client = MockTileClient()
        self.source = TiledSource(self.grid, self.client)
    def test_match(self):
        self.source.get_map(MapQuery([-180, -90, 0, 90], (256, 256), SRS(4326)))
        self.source.get_map(MapQuery([0, -90, 180, 90], (256, 256), SRS(4326)))
        assert self.client.requested_tiles == [(0, 0, 1), (1, 0, 1)]
    def test_wrong_size(self):
        with pytest.raises(InvalidSourceQuery):
            self.source.get_map(MapQuery([-180, -90, 0, 90], (512, 256), SRS(4326)))
    def test_wrong_srs(self):
        with pytest.raises(InvalidSourceQuery):
            self.source.get_map(MapQuery([-180, -90, 0, 90], (512, 256), SRS(4326)))

class RecordFileCache(FileCache):
    def __init__(self, *args, **kw):
        super(RecordFileCache, self).__init__(*args, **kw)
        self.stored_tiles = set()
        self.loaded_tiles = counting_set([])

    def store_tile(self, tile):
        assert tile.coord not in self.stored_tiles
        self.stored_tiles.add(tile.coord)
        if self.cache_dir != '/dev/null':
            FileCache.store_tile(self, tile)

    def load_tile(self, tile, with_metadata=False):
        if tile.source:
            # Do not record tiles with source as "loaded" as FileCache will
            # return tile without checking/loading from filesystem.
            return True
        self.loaded_tiles.add(tile.coord)
        return FileCache.load_tile(self, tile, with_metadata)

    def is_cached(self, tile):
        return tile.coord in self.stored_tiles


def create_cached_tile(tile, cache, timestamp=None):
    loc = cache.tile_location(tile, create_dir=True)
    with open(loc, 'wb') as f:
        f.write(b'foo')

    if timestamp:
        os.utime(loc, (timestamp, timestamp))


@pytest.fixture
def file_cache(tmpdir):
    return FileCache(cache_dir=tmpdir.join('cache').strpath, file_ext='png')

@pytest.fixture
def tile_locker(tmpdir):
    return TileLocker(tmpdir.join('lock').strpath, 10, "id")

@pytest.fixture
def mock_tile_client():
    return MockTileClient()

@pytest.fixture
def mock_file_cache():
    return RecordFileCache('/dev/null', 'png')


class TestTileManagerStaleTiles(object):

    @pytest.fixture
    def tile_mgr(self, file_cache, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        client = MockTileClient()
        source = TiledSource(grid, client)
        tile_mgr = TileManager(grid, file_cache, [source], 'png', locker=tile_locker)
        return tile_mgr

    def test_is_stale_missing(self, tile_mgr):
        assert not tile_mgr.is_stale(Tile((0, 0, 1)))

    def test_is_stale_not_expired(self, tile_mgr, file_cache):
        create_cached_tile(Tile((0, 0, 1)), file_cache)
        assert not tile_mgr.is_stale(Tile((0, 0, 1)))

    def test_is_stale_expired(self, tile_mgr, file_cache):
        create_cached_tile(Tile((0, 0, 1)), file_cache, timestamp=time.time()-3600)
        tile_mgr._expire_timestamp = time.time()
        assert tile_mgr.is_stale(Tile((0, 0, 1)))


class TestTileManagerRemoveTiles(object):
    @pytest.fixture
    def tile_mgr(self, file_cache, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        client = MockTileClient()
        source = TiledSource(grid, client)
        image_opts = ImageOptions(format='image/png')
        return TileManager(grid, file_cache, [source], 'png',
            image_opts=image_opts,
            locker=tile_locker)

    def test_remove_missing(self, tile_mgr):
        tile_mgr.remove_tile_coords([(0, 0, 0), (0, 0, 1)])

    def test_remove_existing(self, tile_mgr, file_cache):
        create_cached_tile(Tile((0, 0, 1)), file_cache)
        assert tile_mgr.is_cached(Tile((0, 0, 1)))
        tile_mgr.remove_tile_coords([(0, 0, 0), (0, 0, 1)])
        assert not tile_mgr.is_cached(Tile((0, 0, 1)))


class TestTileManagerTiledSource(object):
    @pytest.fixture
    def tile_mgr(self, tile_locker, mock_file_cache, mock_tile_client):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        source = TiledSource(grid, mock_tile_client)
        image_opts = ImageOptions(format='image/png')
        return TileManager(grid, mock_file_cache, [source], 'png',
            image_opts=image_opts,
            locker=tile_locker,
        )

    def test_create_tiles(self, tile_mgr, mock_file_cache, mock_tile_client):
        tile_mgr.creator().create_tiles([Tile((0, 0, 1)), Tile((1, 0, 1))])
        assert mock_file_cache.stored_tiles == set([(0, 0, 1), (1, 0, 1)])
        assert sorted(mock_tile_client.requested_tiles) == [(0, 0, 1), (1, 0, 1)]

class TestTileManagerDifferentSourceGrid(object):
    @pytest.fixture
    def tile_mgr(self, mock_file_cache, mock_tile_client, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        source_grid = TileGrid(SRS(4326), bbox=[0, -90, 180, 90])
        source = TiledSource(source_grid, mock_tile_client)
        image_opts = ImageOptions(format='image/png')
        return TileManager(grid, mock_file_cache, [source], 'png',
            image_opts=image_opts,
            locker=tile_locker,
        )

    def test_create_tiles(self, tile_mgr, mock_file_cache, mock_tile_client):
        tile_mgr.creator().create_tiles([Tile((1, 0, 1))])
        assert mock_file_cache.stored_tiles == set([(1, 0, 1)])
        assert mock_tile_client.requested_tiles == [(0, 0, 0)]

    def test_create_tiles_out_of_bounds(self, tile_mgr):
        with pytest.raises(InvalidSourceQuery):
            tile_mgr.creator().create_tiles([Tile((0, 0, 0))])

class MockSource(MapLayer):
    def __init__(self, *args):
        MapLayer.__init__(self, *args)
        self.requested = []

    def _image(self, size):
        return create_debug_img(size)

    def get_map(self, query):
        self.requested.append((query.bbox, query.size, query.srs))
        return ImageSource(self._image(query.size))

@pytest.fixture
def mock_source():
    return MockSource()

class TestTileManagerSource(object):

    @pytest.fixture
    def tile_mgr(self, mock_file_cache, mock_source, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        image_opts = ImageOptions(format='image/png')
        return TileManager(grid, mock_file_cache, [mock_source], 'png',
            image_opts=image_opts,
            locker=tile_locker,
        )

    def test_create_tile(self, tile_mgr, mock_file_cache, mock_source):
        tile_mgr.creator().create_tiles([Tile((0, 0, 1)), Tile((1, 0, 1))])
        assert mock_file_cache.stored_tiles == set([(0, 0, 1), (1, 0, 1)])
        assert sorted(mock_source.requested) == \
            [((-180.0, -90.0, 0.0, 90.0), (256, 256), SRS(4326)),
             ((0.0, -90.0, 180.0, 90.0), (256, 256), SRS(4326))]

class MockWMSClient(object):
    def __init__(self):
        self.requested = []

    def retrieve(self, query, format):
        self.requested.append((query.bbox, query.size, query.srs))
        return create_debug_img(query.size)

@pytest.fixture
def mock_wms_client():
    return MockWMSClient()

class TestTileManagerWMSSource(object):
    @pytest.fixture
    def tile_mgr(self, mock_file_cache, tile_locker, mock_wms_client):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        source = WMSSource(mock_wms_client)
        image_opts = ImageOptions(format='image/png')
        return TileManager(grid, mock_file_cache, [source], 'png',
            meta_size=[2, 2], meta_buffer=0, image_opts=image_opts,
            locker=tile_locker,
        )

    def test_same_lock_for_meta_tile(self, tile_mgr):
        assert tile_mgr.lock(Tile((0, 0, 1))).lock_file == \
            tile_mgr.lock(Tile((1, 0, 1))).lock_file
    def test_locks_for_meta_tiles(self, tile_mgr):
        assert tile_mgr.lock(Tile((0, 0, 2))).lock_file != \
            tile_mgr.lock(Tile((2, 0, 2))).lock_file

    def test_create_tile_first_level(self, tile_mgr, mock_file_cache, mock_wms_client):
        tile_mgr.creator().create_tiles([Tile((0, 0, 1)), Tile((1, 0, 1))])
        assert mock_file_cache.stored_tiles == set([(0, 0, 1), (1, 0, 1)])
        assert mock_wms_client.requested == \
            [((-180.0, -90.0, 180.0, 90.0), (512, 256), SRS(4326))]

    def test_create_tile(self, tile_mgr, mock_file_cache, mock_wms_client):
        tile_mgr.creator().create_tiles([Tile((0, 0, 2))])
        assert mock_file_cache.stored_tiles == \
            set([(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2)])
        assert sorted(mock_wms_client.requested) == \
            [((-180.0, -90.0, 0.0, 90.0), (512, 512), SRS(4326))]

    def test_create_tiles(self, tile_mgr, mock_file_cache, mock_wms_client):
        tile_mgr.creator().create_tiles([Tile((0, 0, 2)), Tile((2, 0, 2))])
        assert mock_file_cache.stored_tiles == \
            set([(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2),
                 (2, 0, 2), (3, 0, 2), (2, 1, 2), (3, 1, 2)])
        assert sorted(mock_wms_client.requested) == \
            [((-180.0, -90.0, 0.0, 90.0), (512, 512), SRS(4326)),
             ((0.0, -90.0, 180.0, 90.0), (512, 512), SRS(4326))]

    def test_load_tile_coords(self, tile_mgr, mock_file_cache, mock_wms_client):
        tiles = tile_mgr.load_tile_coords(((0, 0, 2), (2, 0, 2)))
        assert tiles[0].coord == (0, 0, 2)
        assert isinstance(tiles[0].source, ImageSource)
        assert tiles[1].coord == (2, 0, 2)
        assert isinstance(tiles[1].source, ImageSource)

        assert mock_file_cache.stored_tiles == \
            set([(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2),
                 (2, 0, 2), (3, 0, 2), (2, 1, 2), (3, 1, 2)])
        assert sorted(mock_wms_client.requested) == \
            [((-180.0, -90.0, 0.0, 90.0), (512, 512), SRS(4326)),
             ((0.0, -90.0, 180.0, 90.0), (512, 512), SRS(4326))]


class TestTileManagerWMSSourceConcurrent(TestTileManagerWMSSource):
    @pytest.fixture
    def tile_mgr(self, mock_file_cache, tile_locker, mock_wms_client):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        source = WMSSource(mock_wms_client)
        image_opts = ImageOptions(format='image/png')
        return TileManager(grid, mock_file_cache, [source], 'png',
            meta_size=[2, 2], meta_buffer=0, image_opts=image_opts,
            locker=tile_locker,
            concurrent_tile_creators=2,
        )

class TestTileManagerWMSSourceMinimalMetaRequests(object):
    @pytest.fixture
    def tile_mgr(self, mock_file_cache, mock_wms_client, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        source = WMSSource(mock_wms_client)
        return TileManager(grid, mock_file_cache, [source], 'png',
            meta_size=[2, 2], meta_buffer=10, minimize_meta_requests=True,
            locker=tile_locker,
        )

    def test_create_tile_single(self, tile_mgr, mock_file_cache, mock_wms_client):
        # not enabled for single tile requests
        tile_mgr.creator().create_tiles([Tile((0, 0, 2))])
        assert mock_file_cache.stored_tiles == \
            set([(0, 0, 2), (0, 1, 2), (1, 0, 2), (1, 1, 2)])
        assert sorted(mock_wms_client.requested) == \
            [((-180.0, -90.0, 3.515625, 90.0), (522, 512), SRS(4326))]

    def test_create_tile_multiple(self, tile_mgr, mock_file_cache, mock_wms_client):
        tile_mgr.creator().create_tiles([Tile((4, 0, 3)), Tile((4, 1, 3)), Tile((4, 2, 3))])
        assert mock_file_cache.stored_tiles == \
            set([(4, 0, 3), (4, 1, 3), (4, 2, 3)])
        assert sorted(mock_wms_client.requested) == \
            [((-1.7578125, -90, 46.7578125, 46.7578125), (276, 778), SRS(4326))]

    def test_create_tile_multiple_fragmented(self, tile_mgr, mock_file_cache, mock_wms_client):
        tile_mgr.creator().create_tiles([Tile((4, 0, 3)), Tile((5, 2, 3))])
        assert mock_file_cache.stored_tiles == \
            set([(4, 0, 3), (4, 1, 3), (4, 2, 3), (5, 0, 3), (5, 1, 3), (5, 2, 3)])
        assert sorted(mock_wms_client.requested) == \
            [((-1.7578125, -90, 91.7578125, 46.7578125), (532, 778), SRS(4326))]

class SlowMockSource(MockSource):
    supports_meta_tiles = True
    def get_map(self, query):
        time.sleep(0.1)
        return MockSource.get_map(self, query)

class TestTileManagerLocking(object):
    @pytest.fixture
    def slow_source(self):
        return SlowMockSource()
    @pytest.fixture
    def file_cache(self, tmpdir):
        return RecordFileCache(tmpdir.strpath, 'png')

    @pytest.fixture
    def tile_mgr(self, file_cache, slow_source, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        image_opts = ImageOptions(format='image/png')
        return TileManager(grid, file_cache, [slow_source], 'png',
            meta_size=[2, 2], meta_buffer=0, image_opts=image_opts,
            locker=tile_locker,
        )

    def test_get_single(self, tile_mgr, file_cache, slow_source):
        tile_mgr.creator().create_tiles([Tile((0, 0, 1)), Tile((1, 0, 1))])
        assert file_cache.stored_tiles == set([(0, 0, 1), (1, 0, 1)])
        assert slow_source.requested == \
            [((-180.0, -90.0, 180.0, 90.0), (512, 256), SRS(4326))]

    def test_concurrent(self, tile_mgr, file_cache, slow_source):
        def do_it():
            tile_mgr.creator().create_tiles([Tile((0, 0, 1)), Tile((1, 0, 1))])

        threads = [threading.Thread(target=do_it) for _ in range(3)]
        [t.start() for t in threads]
        [t.join() for t in threads]

        assert file_cache.stored_tiles == set([(0, 0, 1), (1, 0, 1)])
        assert file_cache.loaded_tiles == counting_set([(0, 0, 1), (1, 0, 1), (0, 0, 1), (1, 0, 1)])
        assert slow_source.requested == \
            [((-180.0, -90.0, 180.0, 90.0), (512, 256), SRS(4326))]

        assert os.path.exists(file_cache.tile_location(Tile((0, 0, 1))))



class TestTileManagerMultipleSources(object):
    @pytest.fixture
    def source_base(self):
        return MockSource()

    @pytest.fixture
    def source_overlay(self):
        return MockSource()

    @pytest.fixture
    def tile_mgr(self, mock_file_cache, tile_locker, source_base, source_overlay):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        image_opts = ImageOptions(format='image/png')
        return TileManager(grid, mock_file_cache,
            [source_base, source_overlay], 'png',
            image_opts=image_opts,
            locker=tile_locker,
        )

    def test_get_single(self, tile_mgr, mock_file_cache, source_base, source_overlay):
        tile_mgr.creator().create_tiles([Tile((0, 0, 1))])
        assert mock_file_cache.stored_tiles == set([(0, 0, 1)])
        assert source_base.requested == \
            [((-180.0, -90.0, 0.0, 90.0), (256, 256), SRS(4326))]
        assert source_overlay.requested == \
            [((-180.0, -90.0, 0.0, 90.0), (256, 256), SRS(4326))]

class SolidColorMockSource(MockSource):
    def __init__(self, color='#ff0000'):
        MockSource.__init__(self)
        self.color = color
    def _image(self, size):
        return Image.new('RGB', size, self.color)

class TestTileManagerMultipleSourcesWithMetaTiles(object):
    @pytest.fixture
    def source_base(self):
        src = SolidColorMockSource(color='#ff0000')
        src.supports_meta_tiles = True
        return src

    @pytest.fixture
    def source_overlay(self):
        src = MockSource()
        src.supports_meta_tiles = True
        return src

    @pytest.fixture
    def tile_mgr(self, mock_file_cache, tile_locker, source_base, source_overlay):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        image_opts = ImageOptions(format='image/png')
        return TileManager(grid, mock_file_cache,
            [source_base, source_overlay], 'png',
            image_opts=image_opts,
            meta_size=[2, 2], meta_buffer=0,
            locker=tile_locker,
        )

    def test_merged_tiles(self, tile_mgr, mock_file_cache, source_base, source_overlay):
        tiles = tile_mgr.creator().create_tiles([Tile((0, 0, 1)), Tile((1, 0, 1))])
        assert mock_file_cache.stored_tiles == set([(0, 0, 1), (1, 0, 1)])
        assert source_base.requested == \
            [((-180.0, -90.0, 180.0, 90.0), (512, 256), SRS(4326))]
        assert source_overlay.requested == \
            [((-180.0, -90.0, 180.0, 90.0), (512, 256), SRS(4326))]

        hist = tiles[0].source.as_image().histogram()
        # lots of red (base), but not everything (overlay)
        assert 55000 < hist[255] < 60000 # red   = 0xff
        assert 55000 < hist[256]         # green = 0x00
        assert 55000 < hist[512]         # blue  = 0x00


    def test_sources_with_mixed_support_for_meta_tiles(self, mock_file_cache, source_base, source_overlay, tile_locker):
        source_base.supports_meta_tiles = False
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        with pytest.raises(ValueError):
            TileManager(grid, file_cache,
                [source_base, source_overlay], 'png',
                meta_size=[2, 2], meta_buffer=0,
                locker=tile_locker)

    def test_sources_with_no_support_for_meta_tiles(self, mock_file_cache, source_base, source_overlay, tile_locker):
        source_base.supports_meta_tiles = False
        source_overlay.supports_meta_tiles = False

        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        tile_mgr = TileManager(grid, mock_file_cache,
            [source_base, source_overlay], 'png',
            meta_size=[2, 2], meta_buffer=0,
            locker=tile_locker)

        assert tile_mgr.meta_grid is None


class TestTileManagerBulkMetaTiles(object):
    @pytest.fixture
    def source_base(self):
        src = SolidColorMockSource(color='#ff0000')
        src.supports_meta_tiles = False
        return src

    @pytest.fixture
    def source_overlay(self):
        src = MockSource()
        src.supports_meta_tiles = False
        return src

    @pytest.fixture
    def tile_mgr(self, mock_file_cache, source_base, source_overlay, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90], origin='ul')
        return TileManager(grid, mock_file_cache,
            [source_base, source_overlay], 'png',
            meta_size=[2, 2], meta_buffer=0,
            locker=tile_locker,
            bulk_meta_tiles=True,
        )

    def test_bulk_get(self, tile_mgr, mock_file_cache, source_base, source_overlay):
        tiles = tile_mgr.creator().create_tiles([Tile((0, 0, 2))])
        assert len(tiles) == 2*2
        assert mock_file_cache.stored_tiles == set([(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2)])
        for requested in [source_base.requested, source_overlay.requested]:
            assert set(requested) == set([
                ((-180.0, 0.0, -90.0, 90.0), (256, 256), SRS(4326)),
                ((-90.0, 0.0, 0.0, 90.0), (256, 256), SRS(4326)),
                ((-180.0, -90.0, -90.0, 0.0), (256, 256), SRS(4326)),
                ((-90.0, -90.0, 0.0, 0.0), (256, 256), SRS(4326)),
            ])

    def test_bulk_get_error(self, tile_mgr, source_base):
        tile_mgr.sources = [source_base, ErrorSource()]
        try:
            tile_mgr.creator().create_tiles([Tile((0, 0, 2))])
        except Exception as ex:
            assert ex.args[0] == "source error"

    def test_bulk_get_multiple_meta_tiles(self, tile_mgr, mock_file_cache):
        tiles = tile_mgr.creator().create_tiles([Tile((1, 0, 2)), Tile((2, 0, 2))])
        assert len(tiles) == 2*2*2
        assert mock_file_cache.stored_tiles, set([
            (0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2),
            (2, 0, 2), (3, 0, 2), (2, 1, 2), (3, 1, 2),
        ])

class TestTileManagerBulkMetaTilesConcurrent(TestTileManagerBulkMetaTiles):
    @pytest.fixture
    def tile_mgr(self, mock_file_cache, source_base, source_overlay, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90], origin='ul')
        return TileManager(
            grid, mock_file_cache,
            [source_base, source_overlay], 'png',
            meta_size=[2, 2], meta_buffer=0,
            locker=tile_locker,
            bulk_meta_tiles=True,
            concurrent_tile_creators=2,
        )

class ErrorSource(MapLayer):
    def __init__(self, *args):
        MapLayer.__init__(self, *args)
        self.requested = []

    def get_map(self, query):
        self.requested.append((query.bbox, query.size, query.srs))
        raise Exception("source error")


default_image_opts = ImageOptions(resampling='bicubic')

class TestCacheMapLayer(object):
    @pytest.fixture
    def layer(self, mock_file_cache, mock_wms_client, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        source = WMSSource(mock_wms_client)
        image_opts = ImageOptions(resampling='nearest')
        tile_mgr = TileManager(grid, mock_file_cache, [source], 'png',
            meta_size=[2, 2], meta_buffer=0, image_opts=image_opts,
            locker=tile_locker)
        return CacheMapLayer(tile_mgr, image_opts=default_image_opts)

    def test_get_map_small(self, layer, mock_file_cache):
        result = layer.get_map(MapQuery((-180, -90, 180, 90), (300, 150), SRS(4326), 'png'))
        assert mock_file_cache.stored_tiles == set([(0, 0, 1), (1, 0, 1)])
        assert result.size == (300, 150)

    def test_get_map_large(self, layer, mock_file_cache):
        # gets next resolution layer
        result = layer.get_map(MapQuery((-180, -90, 180, 90), (600, 300), SRS(4326), 'png'))
        assert mock_file_cache.stored_tiles == \
            set([(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2),
                 (2, 0, 2), (3, 0, 2), (2, 1, 2), (3, 1, 2)])
        assert result.size == (600, 300)

    def test_transformed(self, layer, mock_file_cache):
        result = layer.get_map(MapQuery(
            (-20037508.34, -20037508.34, 20037508.34, 20037508.34), (500, 500),
            SRS(900913), 'png'))
        assert mock_file_cache.stored_tiles == \
            set([(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2),
                 (2, 0, 2), (3, 0, 2), (2, 1, 2), (3, 1, 2)])
        assert result.size == (500, 500)

    def test_single_tile_match(self, layer, mock_file_cache):
        result = layer.get_map(MapQuery(
            (0.001, 0, 90, 90), (256, 256), SRS(4326), 'png', tiled_only=True))
        assert mock_file_cache.stored_tiles == \
            set([(3, 0, 2), (2, 0, 2), (3, 1, 2), (2, 1, 2)])
        assert result.size == (256, 256)

    def test_single_tile_no_match(self, layer):
        with pytest.raises(MapBBOXError):
            layer.get_map(
                MapQuery((0.1, 0, 90, 90), (256, 256),
                         SRS(4326), 'png', tiled_only=True)
            )

    def test_get_map_with_res_range(self, mock_file_cache, mock_wms_client, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        res_range = resolution_range(1000, 10)
        source = WMSSource(mock_wms_client, res_range=res_range)
        image_opts = ImageOptions(resampling='nearest')
        tile_mgr = TileManager(grid, mock_file_cache, [source], 'png',
            meta_size=[2, 2], meta_buffer=0, image_opts=image_opts,
            locker=tile_locker)
        layer = CacheMapLayer(tile_mgr, image_opts=default_image_opts)

        with pytest.raises(BlankImage):
            result = layer.get_map(MapQuery(
                (-20037508.34, -20037508.34, 20037508.34, 20037508.34), (500, 500),
                SRS(900913), 'png'))
        assert mock_file_cache.stored_tiles == set()

        result = layer.get_map(MapQuery(
                (0, 0, 10000, 10000), (50, 50),
                SRS(900913), 'png'))
        assert mock_file_cache.stored_tiles == \
            set([(512, 257, 10), (513, 256, 10), (512, 256, 10), (513, 257, 10)])
        assert result.size == (50, 50)

class TestCacheMapLayerWithExtent(object):
    @pytest.fixture
    def source(self, mock_wms_client):
        return WMSSource(mock_wms_client)

    @pytest.fixture
    def layer(self, mock_file_cache, source, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        image_opts = ImageOptions(resampling='nearest', format='png')
        tile_mgr = TileManager(grid, mock_file_cache, [source], 'png',
            meta_size=[1, 1], meta_buffer=0, image_opts=image_opts,
            locker=tile_locker)
        layer = CacheMapLayer(tile_mgr, image_opts=default_image_opts)
        layer.extent = BBOXCoverage([0, 0, 90, 45], SRS(4326)).extent
        return layer

    def test_get_outside_extent(self, layer):
        with pytest.raises(BlankImage):
            layer.get_map(MapQuery((-180, -90, 0, 0), (300, 150), SRS(4326), 'png'))

    def test_get_map_small(self, layer, mock_file_cache, mock_wms_client):
        result = layer.get_map(MapQuery((-180, -90, 180, 90), (300, 150), SRS(4326), 'png'))
        assert mock_file_cache.stored_tiles == set([(1, 0, 1)])
        # source requests one tile (no meta-tiling configured)
        assert mock_wms_client.requested == [((0.0, -90.0, 180.0, 90.0), (256, 256), SRS('EPSG:4326'))]
        assert result.size == (300, 150)

    def test_get_map_small_with_source_extent(self, source, layer, mock_file_cache, mock_wms_client):
        source.extent = BBOXCoverage([0, 0, 90, 45], SRS(4326)).extent
        result = layer.get_map(MapQuery((-180, -90, 180, 90), (300, 150), SRS(4326), 'png'))
        assert mock_file_cache.stored_tiles == set([(1, 0, 1)])
        # source requests one tile (no meta-tiling configured) limited to source.extent
        assert mock_wms_client.requested == [((0, 0, 90, 45), (128, 64), (SRS(4326)))]
        assert result.size == (300, 150)

class TestDirectMapLayer(object):
    @pytest.fixture
    def layer(self, mock_wms_client):
        source = WMSSource(mock_wms_client)
        return DirectMapLayer(source, GLOBAL_GEOGRAPHIC_EXTENT)

    def test_get_map(self, layer, mock_wms_client):
        result = layer.get_map(MapQuery((-180, -90, 180, 90), (300, 150), SRS(4326), 'png'))
        assert mock_wms_client.requested == [((-180, -90, 180, 90), (300, 150), SRS(4326))]
        assert result.size == (300, 150)

    def test_get_map_mercator(self, layer, mock_wms_client):
        result = layer.get_map(MapQuery(
            (-20037508.34, -20037508.34, 20037508.34, 20037508.34), (500, 500),
            SRS(900913), 'png'))
        assert mock_wms_client.requested == \
            [((-20037508.34, -20037508.34, 20037508.34, 20037508.34), (500, 500),
              SRS(900913))]
        assert result.size == (500, 500)

class TestDirectMapLayerWithSupportedSRS(object):
    @pytest.fixture
    def layer(self, mock_wms_client):
        source = WMSSource(mock_wms_client)
        return DirectMapLayer(source, GLOBAL_GEOGRAPHIC_EXTENT)

    def test_get_map(self, layer, mock_wms_client):
        result = layer.get_map(MapQuery((-180, -90, 180, 90), (300, 150), SRS(4326), 'png'))
        assert mock_wms_client.requested == [((-180, -90, 180, 90), (300, 150), SRS(4326))]
        assert result.size == (300, 150)

    def test_get_map_mercator(self, layer, mock_wms_client):
        result = layer.get_map(MapQuery(
            (-20037508.34, -20037508.34, 20037508.34, 20037508.34), (500, 500),
            SRS(900913), 'png'))
        assert mock_wms_client.requested == \
            [((-20037508.34, -20037508.34, 20037508.34, 20037508.34), (500, 500),
              SRS(900913))]
        assert result.size == (500, 500)


class MockHTTPClient(object):
    def __init__(self):
        self.requested = []

    def open(self, url, data=None):
        self.requested.append(url)
        w = int(re.search(r'width=(\d+)', url, re.IGNORECASE).group(1))
        h = int(re.search(r'height=(\d+)', url, re.IGNORECASE).group(1))
        format = re.search(r'format=image(/|%2F)(\w+)', url, re.IGNORECASE).group(2)
        transparent = re.search(r'transparent=(\w+)', url, re.IGNORECASE)
        transparent = True if transparent and transparent.group(1).lower() == 'true' else False
        result = BytesIO()
        create_debug_img((int(w), int(h)), transparent).save(result, format=format)
        result.seek(0)
        result.headers = {'Content-type': 'image/'+format}
        return result


@pytest.fixture
def mock_http_client():
    return MockHTTPClient()

class TestWMSSourceTransform(object):
    @pytest.fixture
    def source(self, mock_http_client):
        req_template = WMS111MapRequest(url='http://localhost/service?', param={
            'format': 'image/png', 'layers': 'foo'
        })
        client = WMSClient(req_template, http_client=mock_http_client)
        return WMSSource(client, supported_srs=SupportedSRS([SRS(4326)]),
            image_opts=ImageOptions(resampling='bilinear'))

    def test_get_map(self, source, mock_http_client):
        source.get_map(MapQuery((-180, -90, 180, 90), (300, 150), SRS(4326)))
        assert query_eq(mock_http_client.requested[0], "http://localhost/service?"
            "layers=foo&width=300&version=1.1.1&bbox=-180,-90,180,90&service=WMS"
            "&format=image%2Fpng&styles=&srs=EPSG%3A4326&request=GetMap&height=150")

    def test_get_map_transformed(self, source, mock_http_client):
        source.get_map(MapQuery(
           (556597, 4865942, 1669792, 7361866), (300, 150), SRS(900913)))
        assert wms_query_eq(mock_http_client.requested[0], "http://localhost/service?"
            "layers=foo&width=300&version=1.1.1"
            "&bbox=4.99999592195,39.9999980766,14.999996749,54.9999994175&service=WMS"
            "&format=image%2Fpng&styles=&srs=EPSG%3A4326&request=GetMap&height=450")


class TestWMSSourceWithClient(object):

    @pytest.fixture
    def req_template(self):
        return WMS111MapRequest(
            url='http://%s:%d/service?' % TEST_SERVER_ADDRESS,
            param={'format': 'image/png', 'layers': 'foo'},
        )

    @pytest.fixture
    def client(self, req_template):
        return WMSClient(req_template)

    @pytest.fixture
    def source(self, client):
        return WMSSource(client)

    def test_get_map(self, source):
        with tmp_image((512, 512)) as img:
            expected_req = ({'path': r'/service?LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                     '&REQUEST=GetMap&HEIGHT=512&SRS=EPSG%3A4326&styles='
                                     '&VERSION=1.1.1&BBOX=0.0,10.0,10.0,20.0&WIDTH=512'},
                           {'body': img.read(), 'headers': {'content-type': 'image/png'}})
            with mock_httpd(TEST_SERVER_ADDRESS, [expected_req]):
                q = MapQuery((0.0, 10.0, 10.0, 20.0), (512, 512), SRS(4326))
                result = source.get_map(q)
                assert isinstance(result, ImageSource)
                assert result.size == (512, 512)
                assert is_png(result.as_buffer(seekable=True))
                assert result.as_image().size == (512, 512)

    def test_get_map_non_image_content_type(self, source):
        with tmp_image((512, 512)) as img:
            expected_req = ({'path': r'/service?LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                     '&REQUEST=GetMap&HEIGHT=512&SRS=EPSG%3A4326&styles='
                                     '&VERSION=1.1.1&BBOX=0.0,10.0,10.0,20.0&WIDTH=512'},
                           {'body': img.read(), 'headers': {'content-type': 'text/plain'}})
            with mock_httpd(TEST_SERVER_ADDRESS, [expected_req]):
                q = MapQuery((0.0, 10.0, 10.0, 20.0), (512, 512), SRS(4326))
                try:
                    source.get_map(q)
                except SourceError as e:
                    assert 'no image returned' in e.args[0]
                else:
                    assert False, 'no SourceError raised'

    def test_basic_auth(self, req_template, client, source):
        http_client = HTTPClient(req_template.url, username='foo', password='bar@')
        client.http_client = http_client
        def assert_auth(req_handler):
            assert 'Authorization' in req_handler.headers
            auth_data = req_handler.headers['Authorization'].split()[1]
            auth_data = base64.b64decode(auth_data.encode('utf-8')).decode('utf-8')
            assert auth_data == 'foo:bar@'
            return True
        expected_req = ({'path': r'/service?LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&HEIGHT=512&SRS=EPSG%3A4326'
                                  '&VERSION=1.1.1&BBOX=0.0,10.0,10.0,20.0&WIDTH=512&STYLES=',
                         'require_basic_auth': True,
                         'req_assert_function': assert_auth},
                        {'body': b'no image', 'headers': {'content-type': 'image/png'}})
        with mock_httpd(TEST_SERVER_ADDRESS, [expected_req]):
            q = MapQuery((0.0, 10.0, 10.0, 20.0), (512, 512), SRS(4326))
            source.get_map(q)

    def test_http_error_handler(self, client):
        error_handler = HTTPSourceErrorHandler()
        error_handler.add_handler(500, (255, 0, 0), cacheable=True)
        error_handler.add_handler(400, (0, 0, 0), cacheable=False)
        source = WMSSource(client, error_handler=error_handler)
        expected_req = [
            (
                {
                    'path': r'/service?LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                     '&REQUEST=GetMap&HEIGHT=512&SRS=EPSG%3A4326'
                                     '&VERSION=1.1.1&BBOX=0.0,10.0,10.0,20.0&WIDTH=512&STYLES='
                },
                {
                    'body': b'error',
                    'status': 500,
                    'headers': {'content-type': 'text/plain'},
                },
            ),
            (
                {
                    'path': r'/service?LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                     '&REQUEST=GetMap&HEIGHT=512&SRS=EPSG%3A4326'
                                     '&VERSION=1.1.1&BBOX=0.0,10.0,10.0,20.0&WIDTH=512&STYLES='
                },
                {
                    'body': b'error',
                    'status': 400,
                    'headers': {'content-type': 'text/plain'},
                },
            ),
        ]
        with mock_httpd(TEST_SERVER_ADDRESS, expected_req):
            query = MapQuery((0.0, 10.0, 10.0, 20.0), (512, 512), SRS(4326))
            resp = source.get_map(query)
            assert resp.cacheable
            assert resp.as_image().getcolors() == [((512 * 512), (255, 0, 0))]

            resp = source.get_map(query)
            assert not resp.cacheable
            assert resp.as_image().getcolors() == [((512 * 512), (0, 0, 0))]


TESTSERVER_URL = 'http://%s:%d' % TEST_SERVER_ADDRESS

class TestWMSSource(object):

    @pytest.fixture
    def source(self, mock_http_client):
        req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo', param={'layers':'foo'})
        wms = WMSClient(req, http_client=mock_http_client)
        return WMSSource(wms, supported_srs=SupportedSRS([SRS(4326)]),
            image_opts=ImageOptions(resampling='bilinear'))

    def test_request(self, source, mock_http_client):
        req = MapQuery((-180.0, -90.0, 180.0, 90.0), (512, 256), SRS(4326), 'png')
        source.get_map(req)
        assert len(mock_http_client.requested) == 1
        assert_query_eq(mock_http_client.requested[0],
            TESTSERVER_URL+'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                           '&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A4326'
                           '&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,90.0&WIDTH=512&STYLES=')

    def test_transformed_request(self, source, mock_http_client):
        req = MapQuery((-200000, -200000, 200000, 200000), (512, 512), SRS(900913), 'png')
        resp = source.get_map(req)
        assert len(mock_http_client.requested) == 1

        assert wms_query_eq(mock_http_client.requested[0],
            TESTSERVER_URL+'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                           '&REQUEST=GetMap&HEIGHT=512&SRS=EPSG%3A4326'
                           '&VERSION=1.1.1&WIDTH=512&STYLES='
                           '&BBOX=-1.79663056824,-1.7963362121,1.79663056824,1.7963362121')
        img = resp.as_image()
        assert img.mode in ('P', 'RGB')

    def test_transformed_request_transparent(self, mock_http_client):
        req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo',
                                    param={'layers':'foo', 'transparent': 'true'})
        wms = WMSClient(req, http_client=mock_http_client)
        source = WMSSource(wms, supported_srs=SupportedSRS([SRS(4326)]),
            image_opts=ImageOptions(resampling='bilinear'))

        req = MapQuery((-200000, -200000, 200000, 200000), (512, 512), SRS(900913), 'png')
        resp = source.get_map(req)
        assert len(mock_http_client.requested) == 1

        assert wms_query_eq(mock_http_client.requested[0],
            TESTSERVER_URL+'/service?map=foo&LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                           '&REQUEST=GetMap&HEIGHT=512&SRS=EPSG%3A4326'
                           '&VERSION=1.1.1&WIDTH=512&STYLES=&transparent=true'
                           '&BBOX=-1.79663056824,-1.7963362121,1.79663056824,1.7963362121')
        img = resp.as_image()
        assert img.mode in ('P', 'RGBA')
        img = img.convert('RGBA')
        assert img.getpixel((5, 5))[3] == 0


class MockLayer(object):
    def __init__(self):
        self.requested = []
    def get_map(self, query):
        self.requested.append((query.bbox, query.size, query.srs))

@pytest.mark.parametrize('case,map_query,low_requested', [
    ['low', MapQuery((0, 0, 10000, 10000), (100, 100), SRS(3857)), True],
    ['high', MapQuery((0, 0, 100, 100), (100, 100), SRS(3857)), False],
    ['match', MapQuery((0, 0, 10, 10), (100, 100), SRS(3857)), False],
    ['low_transform', MapQuery((0, 0, 0.1, 0.1), (100, 100), SRS(4326)), True],
    ['high_transform', MapQuery((0, 0, 0.005, 0.005), (100, 100), SRS(4326)), False],
])
def test_resolution_conditional_layers(case, map_query, low_requested):
    low = MockLayer()
    high = MockLayer()
    layer = ResolutionConditional(low, high, 10, SRS(3857),
        GLOBAL_GEOGRAPHIC_EXTENT)

    layer.get_map(map_query)
    assert bool(low.requested) == low_requested
    assert bool(high.requested) != low_requested


def test_srs_conditional_layers():
    l4326 = MockLayer()
    l3857 = MockLayer()
    l25832 = MockLayer()
    preferred = PreferredSrcSRS()
    preferred.add(SRS(31467), [SRS(25832), SRS(3857)])
    layer = SRSConditional([
        (l4326, SRS(4326)),
        (l3857, SRS(3857)),
        (l25832, SRS(25832)),
    ], GLOBAL_GEOGRAPHIC_EXTENT, preferred_srs=preferred,
    )

    # srs match
    assert layer._select_layer(SRS(4326)) == l4326
    assert layer._select_layer(SRS(3857)) == l3857
    assert layer._select_layer(SRS(25832)) == l25832
    # type match (projected)
    assert layer._select_layer(SRS(31466)) == l3857
    assert layer._select_layer(SRS(32633)) == l3857
    assert layer._select_layer(SRS(4258)) == l4326
    # preferred
    assert layer._select_layer(SRS(31467)) == l25832

@pytest.mark.parametrize('case,map_query,is_direct,is_l3857,is_l4326', [
    ['high_3857', MapQuery((0, 0, 100, 100), (100, 100), SRS(900913)), True, False, False],
    ['high_4326', MapQuery((0, 0, 0.0001, 0.0001), (100, 100), SRS(4326)), True, False, False],
    ['low_4326', MapQuery((0, 0, 10, 10), (100, 100), SRS(4326)), False, False, True],
    ['low_3857', MapQuery((0, 0, 10000, 10000), (100, 100), SRS(31467)), False, True, False],
    ['low_projected', MapQuery((0, 0, 10000, 10000), (100, 100), SRS(31467)), False, True, False],
])
def test_neasted_conditional_layers(case, map_query, is_direct, is_l3857, is_l4326):
    direct = MockLayer()
    l3857 = MockLayer()
    l4326 = MockLayer()
    layer = ResolutionConditional(
        SRSConditional([
            (l3857, SRS('EPSG:3857')),
            (l4326, SRS('EPSG:4326'))
        ], GLOBAL_GEOGRAPHIC_EXTENT),
        direct, 10, SRS(3857), GLOBAL_GEOGRAPHIC_EXTENT
        )
    layer.get_map(map_query)
    assert bool(direct.requested) == is_direct
    assert bool(l3857.requested) == is_l3857
    assert bool(l4326.requested) == is_l4326


def is_blank(tiles):
    return all([t.source is None or isinstance(t.source, BlankImageSource) for t in tiles.tiles])

class TestTileManagerEmptySources(object):
    def test_upscale(self, mock_file_cache, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        image_opts = ImageOptions(format='image/png')
        tm = TileManager(
            grid, mock_file_cache, [], 'png',
            locker=tile_locker,
            image_opts=image_opts,
        )

        assert is_blank(tm.load_tile_coords([(0, 0, 0)]))
        assert is_blank(tm.load_tile_coords([(3, 2, 5)]))

        assert mock_file_cache.stored_tiles == set()
        assert mock_file_cache.loaded_tiles == counting_set([(0, 0, 0), (3, 2, 5)])

class TestTileManagerRescaleTiles(object):
    @pytest.fixture
    def file_cache(self, tmpdir):
        return RecordFileCache(tmpdir.strpath, 'png')

    @pytest.mark.parametrize("name,rescale_tiles,tiles,store,expected_load,output", [
        (
            "no-scale: missing tile, no rescale",
            0, [(0, 0, 0)], [], [(0, 0, 0)], "blank",
        ),
        (
            "downscale: missing tile, 1 level rescale with None tiles",
            1, [(0, 0, 0)], [], [(0, 0, 0), None, None, (0, 0, 1), (1, 0, 1)], "blank",
        ),
        (
            "downscale: missing tile, 1 level rescale",
            1, [(1, 2, 4)], [], [(1, 2, 4), (2, 4, 5), (3, 4, 5), (2, 5, 5), (3, 5, 5)], "blank",
        ),
        (
            "downscale: missing tile, 2 level rescale",
            2, [(1, 2, 4)], [], [
                (1, 2, 4),
                (2, 4, 5), (3, 4, 5), (2, 5, 5), (3, 5, 5),
                (4, 8, 6), (5, 8, 6), (6, 8, 6), (7, 8, 6),
                (4, 9, 6), (5, 9, 6), (6, 9, 6), (7, 9, 6),
                (4, 10, 6), (5, 10, 6), (6, 10, 6), (7, 10, 6),
                (4, 11, 6), (5, 11, 6), (6, 11, 6), (7, 11, 6),
            ], "blank",
        ),
        (
            "downscale: exact tile cached",
            1, [(0, 0, 1)], [(0, 0, 1)], [(0, 0, 1)], "full",
        ),
        (
            "downscale: next level tiles partially cached",
            1, [(0, 0, 1)], [(0, 0, 2)], [(0, 0, 1), (0, 0, 2), (0, 1, 2), (1, 0, 2), (1, 1, 2)], "partial",
        ),
        (
            "downscale: next level tiles fully cached",
            1, [(0, 0, 1)], [(0, 0, 2), (0, 1, 2), (1, 0, 2), (1, 1, 2)], [(0, 0, 1), (0, 0, 2), (0, 1, 2), (1, 0, 2), (1, 1, 2)], "full",
        ),
        (
            "upscale: missing tile level 1 rescale",
            -1, [(16, 8, 5)], [], [(16, 8, 5), (8, 4, 4)], "blank",
        ),
        (
            "upscale: missing tile level 1 rescale, odd coords",
            -1, [(15, 7, 5)], [], [(15, 7, 5), (7, 3, 4)], "blank",
        ),
        (
            "upscale: missing tile level 1 rescale, multiple tiles",
            -1, [(15, 6, 5), (16, 6, 5), (15, 7, 5), (16, 7, 5)], [],
            [(15, 6, 5), (16, 6, 5), (15, 7, 5), (16, 7, 5), (7, 3, 4), (8, 3, 4)], "blank",
        ),
        (
            "upscale: tile in level 2",
            -3, [(15, 7, 5)], [(3, 1, 3)], [(15, 7, 5), (7, 3, 4), (3, 1, 3)], "full",
        ),
        (
            "upscale: missing tile level 99 rescale",
            -99, [(16, 8, 5)], [], [(16, 8, 5), (8, 4, 4), (4, 2, 3), (2, 1, 2), (1, 0, 1), (0, 0, 0)], "blank",
        ),
        (
            "upscale: unregular grid, partial match",
            -2, [(201, 101, 10)], [(78, 40, 8), (79, 40, 8), (79, 39, 8)], [
                (201, 101, 10), (100, 50, 9),
                # check all four tiles above 100/50/9
                (78, 40, 8), (79, 40, 8), (78, 39, 8), (79, 39, 8),
            ], "partial",
        ),
        (
            "upscale: unregular grid, multiple tiles, partial match",
            -2, [(200, 100, 10), (201, 100, 10), (200, 101, 10), (201, 101, 10)],
            [(78, 40, 8), (79, 40, 8), (79, 39, 8)], [
                (200, 100, 10), (201, 100, 10), (200, 101, 10), (201, 101, 10),
                (100, 50, 9),
                (78, 40, 8), (79, 40, 8), (78, 39, 8), (79, 39, 8),
            ], "partial",
        ),
        (
            "upscale: unregular grid",
            -3, [(200, 100, 10)], [], [
                (200, 100, 10), (100, 50, 9),
                # check all four tiles above 100/50/9
                (78, 40, 8), (79, 40, 8), (78, 39, 8), (79, 39, 8),
                # check tiles above level 8 for each tile individually.
                # this is due to the recursive nature of our rescaling algorithm
                (49, 24, 7),
                (50, 24, 7),
                (49, 25, 7),
                (50, 25, 7),
                (49, 26, 7),
                (50, 26, 7),
            ],
            "blank",
        ),
    ])
    def test_scaled_tiles(self, name, file_cache, tile_locker, rescale_tiles, tiles, store, expected_load, output):
        res = [
            1.40625,               # 0
            0.703125,              # 1
            0.3515625,             # 2
            0.17578125,            # 3
            0.087890625,           # 4
            0.0439453125,          # 5
            0.02197265625,         # 6
            0.010986328125,        # 7
            0.007,                 # 8 additional resolution to test unregular grids
            0.0054931640625,       # 9
            0.00274658203125,      # 10
        ]
        grid = TileGrid(SRS(4326), origin='sw', bbox=[-180, -90, 180, 90], res=res)
        image_opts = ImageOptions(format='image/png', resampling='nearest')
        tm = TileManager(
            grid, file_cache, [], 'png',
            locker=tile_locker,
            image_opts=image_opts,
            rescale_tiles=rescale_tiles,
        )

        if store:
            colors = set()
            if output == "partial":
                colors.add((255, 255, 255))
            for i, t in enumerate(store):
                color = (150+i*35, 5+i*35, 5+i*35)
                colors.add(color)
                tile = Tile(t, ImageSource(create_tmp_image_buf((256, 256), color=color)))
                file_cache.store_tile(tile)

            loaded_tiles = tm.load_tile_coords(tiles)
            assert not is_blank(loaded_tiles)
            assert len(loaded_tiles) == len(tiles)
            got_colors = set()
            for t in loaded_tiles:
                got_colors.update([c for _, c in t.source.as_image().getcolors()])
            assert got_colors == colors
        else:
            loaded_tiles = tm.load_tile_coords(tiles)
            assert is_blank(loaded_tiles) == (output == "blank")
            assert len(loaded_tiles.tiles) == len(tiles)

        assert file_cache.stored_tiles == set(store)
        assert file_cache.loaded_tiles == counting_set(expected_load)


