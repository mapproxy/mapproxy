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
import stat

from io import BytesIO
from collections import defaultdict

import pytest

from mapproxy.cache.base import TileLocker
from mapproxy.cache.file import FileCache
from mapproxy.cache.tile import Tile, TileManager
from mapproxy.client.http import HTTPClient
from mapproxy.client.wms import WMSClient
from PIL import Image
from mapproxy.config.coverage import load_coverage
from mapproxy.grid.tile_grid import TileGrid
from mapproxy.grid.resolutions import resolution_range
from mapproxy.image import ImageSource, BlankImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.layer import (
    BlankImage,
    CacheMapLayer,
    DirectMapLayer,
    MapBBOXError,
    MapLayer,
    ResolutionConditional,
    SRSConditional,
)
from mapproxy.extent import MapExtent
from mapproxy.query import MapQuery
from mapproxy.request.wms import WMS111MapRequest
from mapproxy.source import InvalidSourceQuery, SourceError
from mapproxy.source.tile import TiledSource
from mapproxy.source.wms import WMSSource
from mapproxy.source.error import HTTPSourceErrorHandler
from mapproxy.srs import SRS, SupportedSRS, PreferredSrcSRS
from mapproxy.test.helper import TempFile
from mapproxy.test.http import assert_query_eq, wms_query_eq, query_eq, mock_httpd
from mapproxy.test.image import create_debug_img, is_png, tmp_image, create_tmp_image_buf
from mapproxy.util.coverage import BBOXCoverage, coverage


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
    def setup_method(self):
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
        self.is_cached_call_count = 0
        self.directory_permissions = kw.get('directory_permissions')

    def store_tile(self, tile, dimensions=None):
        assert tile.coord not in self.stored_tiles
        self.stored_tiles.add(tile.coord)
        if self.cache_dir != '/dev/null':
            FileCache.store_tile(self, tile, dimensions=dimensions)

    def load_tile(self, tile, with_metadata=False, dimensions=None):
        if tile.source:
            # Do not record tiles with source as "loaded" as FileCache will
            # return tile without checking/loading from filesystem.
            return True
        self.loaded_tiles.add(tile.coord)
        return FileCache.load_tile(self, tile, with_metadata, dimensions=dimensions)

    def is_cached(self, tile, dimensions=None):
        self.is_cached_call_count += 1
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
def tile_locker_restricted(tmpdir):
    return TileLocker(tmpdir.join('lock').strpath, 10, "id", '666')


@pytest.fixture
def tile_locker_permissive(tmpdir):
    return TileLocker(tmpdir.join('lock').strpath, 10, "id", '775')


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
        assert mock_file_cache.stored_tiles == {(0, 0, 1), (1, 0, 1)}
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
        assert mock_file_cache.stored_tiles == {(1, 0, 1)}
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
        assert mock_file_cache.stored_tiles == {(0, 0, 1), (1, 0, 1)}
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
        assert mock_file_cache.stored_tiles == {(0, 0, 1), (1, 0, 1)}
        assert mock_wms_client.requested == \
            [((-180.0, -90.0, 180.0, 90.0), (512, 256), SRS(4326))]

    def test_create_tile(self, tile_mgr, mock_file_cache, mock_wms_client):
        tile_mgr.creator().create_tiles([Tile((0, 0, 2))])
        assert mock_file_cache.stored_tiles == \
               {(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2)}
        assert sorted(mock_wms_client.requested) == \
            [((-180.0, -90.0, 0.0, 90.0), (512, 512), SRS(4326))]

    def test_create_tiles(self, tile_mgr, mock_file_cache, mock_wms_client):
        tile_mgr.creator().create_tiles([Tile((0, 0, 2)), Tile((2, 0, 2))])
        assert mock_file_cache.stored_tiles == \
               {(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2), (2, 0, 2), (3, 0, 2), (2, 1, 2), (3, 1, 2)}
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
               {(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2), (2, 0, 2), (3, 0, 2), (2, 1, 2), (3, 1, 2)}
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
               {(0, 0, 2), (0, 1, 2), (1, 0, 2), (1, 1, 2)}
        assert sorted(mock_wms_client.requested) == \
            [((-180.0, -90.0, 3.515625, 90.0), (522, 512), SRS(4326))]

    def test_create_tile_multiple(self, tile_mgr, mock_file_cache, mock_wms_client):
        tile_mgr.creator().create_tiles([Tile((4, 0, 3)), Tile((4, 1, 3)), Tile((4, 2, 3))])
        assert mock_file_cache.stored_tiles == \
               {(4, 0, 3), (4, 1, 3), (4, 2, 3)}
        assert sorted(mock_wms_client.requested) == \
            [((-1.7578125, -90, 46.7578125, 46.7578125), (276, 778), SRS(4326))]

    def test_create_tile_multiple_fragmented(self, tile_mgr, mock_file_cache, mock_wms_client):
        tile_mgr.creator().create_tiles([Tile((4, 0, 3)), Tile((5, 2, 3))])
        assert mock_file_cache.stored_tiles == \
               {(4, 0, 3), (4, 1, 3), (4, 2, 3), (5, 0, 3), (5, 1, 3), (5, 2, 3)}
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
    def file_cache_permissive(self, tmpdir):
        return RecordFileCache(tmpdir.strpath, 'png', directory_permissions='775')

    @pytest.fixture
    def tile_mgr(self, file_cache, slow_source, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        image_opts = ImageOptions(format='image/png')
        return TileManager(grid, file_cache, [slow_source], 'png',
                           meta_size=[2, 2], meta_buffer=0, image_opts=image_opts,
                           locker=tile_locker,
                           )

    @pytest.fixture
    def tile_mgr_restricted(self, file_cache, slow_source, tile_locker_restricted):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        image_opts = ImageOptions(format='image/png')
        return TileManager(grid, file_cache, [slow_source], 'png',
                           meta_size=[2, 2], meta_buffer=0, image_opts=image_opts,
                           locker=tile_locker_restricted,
                           )

    @pytest.fixture
    def tile_mgr_permissive(self, file_cache_permissive, slow_source, tile_locker_permissive):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        image_opts = ImageOptions(format='image/png')
        return TileManager(grid, file_cache_permissive, [slow_source], 'png',
                           meta_size=[2, 2], meta_buffer=0, image_opts=image_opts,
                           locker=tile_locker_permissive,
                           )

    def test_get_single(self, tile_mgr, file_cache, slow_source):
        tile_mgr.creator().create_tiles([Tile((0, 0, 1)), Tile((1, 0, 1))])
        assert file_cache.stored_tiles == {(0, 0, 1), (1, 0, 1)}
        assert slow_source.requested == \
            [((-180.0, -90.0, 180.0, 90.0), (512, 256), SRS(4326))]

    def test_concurrent(self, tile_mgr, file_cache, slow_source):
        def do_it():
            tile_mgr.creator().create_tiles([Tile((0, 0, 1)), Tile((1, 0, 1))])

        threads = [threading.Thread(target=do_it) for _ in range(3)]
        [t.start() for t in threads]
        [t.join() for t in threads]

        assert file_cache.stored_tiles == {(0, 0, 1), (1, 0, 1)}
        assert file_cache.loaded_tiles == counting_set([(0, 0, 1), (1, 0, 1), (0, 0, 1), (1, 0, 1)])
        assert slow_source.requested == \
            [((-180.0, -90.0, 180.0, 90.0), (512, 256), SRS(4326))]

        assert os.path.exists(file_cache.tile_location(Tile((0, 0, 1))))

    def test_insufficient_permissions_on_dir(self, tile_mgr_restricted):
        # TileLocker has restrictive permissions set for creating directories
        try:
            tile_mgr_restricted.creator().create_tiles([Tile((0, 0, 1)), Tile((1, 0, 1))])
        except Exception as e:
            assert 'Could not create Lock-file, wrong permissions on lock directory?' in e.args[0]
        else:
            assert False, 'no PermissionError raised'

    def test_permissive_grants(self, tile_mgr_permissive, file_cache_permissive):
        tile_mgr_permissive.creator().create_tiles([Tile((0, 0, 1)), Tile((1, 0, 1))])
        location = file_cache_permissive.tile_location(Tile((0, 0, 1)))
        assert os.path.exists(location)
        dir = os.path.dirname(location)
        mode = os.stat(dir).st_mode
        assert stat.filemode(mode) == 'drwxrwxr-x'


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
        assert mock_file_cache.stored_tiles == {(0, 0, 1)}
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
        assert mock_file_cache.stored_tiles == {(0, 0, 1), (1, 0, 1)}
        assert source_base.requested == \
            [((-180.0, -90.0, 180.0, 90.0), (512, 256), SRS(4326))]
        assert source_overlay.requested == \
            [((-180.0, -90.0, 180.0, 90.0), (512, 256), SRS(4326))]

        hist = tiles[0].source.as_image().histogram()
        # lots of red (base), but not everything (overlay)
        assert 55000 < hist[255] < 60000  # red   = 0xff
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
        assert mock_file_cache.stored_tiles == {(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2)}
        for requested in [source_base.requested, source_overlay.requested]:
            assert set(requested) == {((-180.0, 0.0, -90.0, 90.0), (256, 256), SRS(4326)),
                                      ((-90.0, 0.0, 0.0, 90.0), (256, 256), SRS(4326)),
                                      ((-180.0, -90.0, -90.0, 0.0), (256, 256), SRS(4326)),
                                      ((-90.0, -90.0, 0.0, 0.0), (256, 256), SRS(4326))}

    def test_bulk_get_error(self, tile_mgr, source_base):
        tile_mgr.sources = [source_base, ErrorSource()]
        try:
            tile_mgr.creator().create_tiles([Tile((0, 0, 2))])
        except Exception as ex:
            assert ex.args[0] == "source error"

    def test_bulk_get_multiple_meta_tiles(self, tile_mgr, mock_file_cache):
        tiles = tile_mgr.creator().create_tiles([Tile((1, 0, 2)), Tile((2, 0, 2))])
        assert len(tiles) == 2*2*2
        assert mock_file_cache.stored_tiles, {(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2), (2, 0, 2), (3, 0, 2),
                                              (2, 1, 2), (3, 1, 2)}


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
        assert mock_file_cache.stored_tiles == {(0, 0, 1), (1, 0, 1)}
        assert result.size == (300, 150)

    def test_get_map_large(self, layer, mock_file_cache):
        # gets next resolution layer
        result = layer.get_map(MapQuery((-180, -90, 180, 90), (600, 300), SRS(4326), 'png'))
        assert mock_file_cache.stored_tiles == \
               {(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2), (2, 0, 2), (3, 0, 2), (2, 1, 2), (3, 1, 2)}
        assert result.size == (600, 300)

    def test_transformed(self, layer, mock_file_cache):
        result = layer.get_map(MapQuery(
            (-20037508.34, -20037508.34, 20037508.34, 20037508.34), (500, 500),
            SRS(900913), 'png'))
        assert mock_file_cache.stored_tiles == \
               {(0, 0, 2), (1, 0, 2), (0, 1, 2), (1, 1, 2), (2, 0, 2), (3, 0, 2), (2, 1, 2), (3, 1, 2)}
        assert result.size == (500, 500)

    def test_single_tile_match(self, layer, mock_file_cache):
        result = layer.get_map(MapQuery(
            (0.001, 0, 90, 90), (256, 256), SRS(4326), 'png', tiled_only=True))
        assert mock_file_cache.stored_tiles == \
               {(3, 0, 2), (2, 0, 2), (3, 1, 2), (2, 1, 2)}
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
               {(512, 257, 10), (513, 256, 10), (512, 256, 10), (513, 257, 10)}
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
        assert mock_file_cache.stored_tiles == {(1, 0, 1)}
        # source requests one tile (no meta-tiling configured)
        assert mock_wms_client.requested == [((0.0, -90.0, 180.0, 90.0), (256, 256), SRS('EPSG:4326'))]
        assert result.size == (300, 150)

    def test_get_map_small_with_source_extent(self, source, layer, mock_file_cache, mock_wms_client):
        source.extent = BBOXCoverage([0, 0, 90, 45], SRS(4326)).extent
        result = layer.get_map(MapQuery((-180, -90, 180, 90), (300, 150), SRS(4326), 'png'))
        assert mock_file_cache.stored_tiles == {(1, 0, 1)}
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
    def __init__(self, response_type='image'):
        self.requested = []
        self.response_type = response_type

    def open(self, url, data=None):
        self.requested.append(url)
        if self.response_type == 'image':
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
        elif self.response_type == 'text':
            result = BytesIO(b'text')
            result.headers = {'Content-type': 'text/plain'}
            return result
        else:
            raise Exception('Unknown response type')


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
        req = WMS111MapRequest(url=TESTSERVER_URL + '/service?map=foo', param={'layers': 'foo'})
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
                               param={'layers': 'foo', 'transparent': 'true'})
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
def test_nested_conditional_layers(case, map_query, is_direct, is_l3857, is_l4326):
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
            1, [(0, 0, 1)], [(0, 0, 2), (0, 1, 2), (1, 0, 2), (1, 1, 2)],
            [(0, 0, 1), (0, 0, 2), (0, 1, 2), (1, 0, 2), (1, 1, 2)], "full",
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
            "upscale: irregular grid, partial match",
            -2, [(201, 101, 10)], [(78, 40, 8), (79, 40, 8), (79, 39, 8)], [
                (201, 101, 10), (100, 50, 9),
                # check all four tiles above 100/50/9
                (78, 40, 8), (79, 40, 8), (78, 39, 8), (79, 39, 8),
            ], "partial",
        ),
        (
            "upscale: irregular grid, multiple tiles, partial match",
            -2, [(200, 100, 10), (201, 100, 10), (200, 101, 10), (201, 101, 10)],
            [(78, 40, 8), (79, 40, 8), (79, 39, 8)], [
                (200, 100, 10), (201, 100, 10), (200, 101, 10), (201, 101, 10),
                (100, 50, 9),
                (78, 40, 8), (79, 40, 8), (78, 39, 8), (79, 39, 8),
            ], "partial",
        ),
        (
            "upscale: irregular grid",
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
            0.007,                 # 8 additional resolution to test irregular grids
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
        assert file_cache.is_cached_call_count == 0


class TileCacheTestBase(object):
    cache = None  # set by subclasses

    def setup_method(self):
        self.cache_dir = tempfile.mkdtemp()

    def teardown_method(self):
        if hasattr(self.cache, 'cleanup'):
            self.cache.cleanup()
        if hasattr(self, 'cache_dir') and os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)


class TestTileManagerCacheBboxCoverage(TileCacheTestBase):
    def setup_method(self):
        TileCacheTestBase.setup_method(self)
        self.cache = RecordFileCache(self.cache_dir, 'png', coverage=coverage([-50, -50, 50, 50], SRS(4326)))

    def test_load_tiles_in_coverage(self, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90], origin='ul')
        image_opts = ImageOptions(format='image/png')
        tm = TileManager(
            grid, self.cache, [], 'png',
            locker=tile_locker,
            image_opts=image_opts,
        )

        coords = [(2, 1, 2), (36, 7, 6), (18082, 6028, 15)]
        collection = tm.load_tile_coords(coords)

        # Check that tiles inside of coverage loaded
        assert all(coord in collection for coord in coords)
        assert all(t.coord is not None for t in collection)

        all(t.coord in self.cache.stored_tiles for t in collection)
        assert self.cache.loaded_tiles == counting_set(coords)
        assert self.cache.is_cached_call_count == 0

    def test_empty_tiles_outside_coverage(self, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90], origin='ul')
        image_opts = ImageOptions(format='image/png')
        tm = TileManager(
            grid, self.cache, [], 'png',
            locker=tile_locker,
            image_opts=image_opts,
        )

        coords = [(0, 1, 1), (33, 5, 5), (19449, 3638, 15)]
        collection = tm.load_tile_coords(coords)

        # Check that tiles did not load
        assert collection.blank
        assert all(t.coord is None for t in collection)

        assert self.cache.stored_tiles == set([])
        assert self.cache.loaded_tiles == counting_set([None for _ in coords])


# From: https://www.kaggle.com/datasets/chapagain/country-state-geo-location
boundary_geojson = (
    b"""
{"type":"FeatureCollection","features":[
{"type":"Feature","geometry":{"type":"MultiPolygon","coordinates":[[[[-155.54211,19.08348],[-155.68817,18.91619],[-155.93665,19.05939],[-155.90806,19.33888],[-156.07347,19.70294],[-156.02368,19.81422],[-155.85008,19.97729],[-155.91907,20.17395],[-155.86108,20.26721],[-155.78505,20.2487],[-155.40214,20.07975],[-155.22452,19.99302],[-155.06226,19.8591],[-154.80741,19.50871],[-154.83147,19.45328],[-155.22217,19.23972],[-155.54211,19.08348]]],[[[-156.07926,20.64397],[-156.41445,20.57241],[-156.58673,20.783],[-156.70167,20.8643],[-156.71055,20.92676],[-156.61258,21.01249],[-156.25711,20.91745],[-155.99566,20.76404],[-156.07926,20.64397]]],[[[-156.75824,21.17684],[-156.78933,21.06873],[-157.32521,21.09777],[-157.25027,21.21958],[-156.75824,21.17684]]],[[[-157.65283,21.32217],[-157.70703,21.26442],[-157.7786,21.27729],[-158.12667,21.31244],[-158.2538,21.53919],[-158.29265,21.57912],[-158.0252,21.71696],[-157.94161,21.65272],[-157.65283,21.32217]]],[[[-159.34512,21.982],[-159.46372,21.88299],[-159.80051,22.06533],[-159.74877,22.1382],[-159.5962,22.23618],[-159.36569,22.21494],[-159.34512,21.982]]],[[[-94.81758,49.38905],[-94.64,48.84],[-94.32914,48.67074],[-93.63087,48.60926],[-92.61,48.45],[-91.64,48.14],[-90.83,48.27],[-89.6,48.01],[-89.272917,48.019808],[-88.378114,48.302918],[-87.439793,47.94],[-86.461991,47.553338],[-85.652363,47.220219],[-84.87608,46.900083],[-84.779238,46.637102],[-84.543749,46.538684],[-84.6049,46.4396],[-84.3367,46.40877],[-84.14212,46.512226],[-84.091851,46.275419],[-83.890765,46.116927],[-83.616131,46.116927],[-83.469551,45.994686],[-83.592851,45.816894],[-82.550925,45.347517],[-82.337763,44.44],[-82.137642,43.571088],[-82.43,42.98],[-82.9,42.43],[-83.12,42.08],[-83.142,41.975681],[-83.02981,41.832796],[-82.690089,41.675105],[-82.439278,41.675105],[-81.277747,42.209026],[-80.247448,42.3662],[-78.939362,42.863611],[-78.92,42.965],[-79.01,43.27],[-79.171674,43.466339],[-78.72028,43.625089],[-77.737885,43.629056],[-76.820034,43.628784],[-76.5,44.018459],[-76.375,44.09631],[-75.31821,44.81645],[-74.867,45.00048],[-73.34783,45.00738],[-71.50506,45.0082],[-71.405,45.255],[-71.08482,45.30524],[-70.66,45.46],[-70.305,45.915],[-69.99997,46.69307],[-69.237216,47.447781],[-68.905,47.185],[-68.23444,47.35486],[-67.79046,47.06636],[-67.79134,45.70281],[-67.13741,45.13753],[-66.96466,44.8097],[-68.03252,44.3252],[-69.06,43.98],[-70.11617,43.68405],[-70.645476,43.090238],[-70.81489,42.8653],[-70.825,42.335],[-70.495,41.805],[-70.08,41.78],[-70.185,42.145],[-69.88497,41.92283],[-69.96503,41.63717],[-70.64,41.475],[-71.12039,41.49445],[-71.86,41.32],[-72.295,41.27],[-72.87643,41.22065],[-73.71,40.931102],[-72.24126,41.11948],[-71.945,40.93],[-73.345,40.63],[-73.982,40.628],[-73.952325,40.75075],[-74.25671,40.47351],[-73.96244,40.42763],[-74.17838,39.70926],[-74.90604,38.93954],[-74.98041,39.1964],[-75.20002,39.24845],[-75.52805,39.4985],[-75.32,38.96],[-75.071835,38.782032],[-75.05673,38.40412],[-75.37747,38.01551],[-75.94023,37.21689],[-76.03127,37.2566],[-75.72205,37.93705],[-76.23287,38.319215],[-76.35,39.15],[-76.542725,38.717615],[-76.32933,38.08326],[-76.989998,38.239992],[-76.30162,37.917945],[-76.25874,36.9664],[-75.9718,36.89726],[-75.86804,36.55125],[-75.72749,35.55074],[-76.36318,34.80854],[-77.397635,34.51201],[-78.05496,33.92547],[-78.55435,33.86133],[-79.06067,33.49395],[-79.20357,33.15839],[-80.301325,32.509355],[-80.86498,32.0333],[-81.33629,31.44049],[-81.49042,30.72999],[-81.31371,30.03552],[-80.98,29.18],[-80.535585,28.47213],[-80.53,28.04],[-80.056539,26.88],[-80.088015,26.205765],[-80.13156,25.816775],[-80.38103,25.20616],[-80.68,25.08],[-81.17213,25.20126],[-81.33,25.64],[-81.71,25.87],[-82.24,26.73],[-82.70515,27.49504],[-82.85526,27.88624],[-82.65,28.55],[-82.93,29.1],[-83.70959,29.93656],[-84.1,30.09],[-85.10882,29.63615],[-85.28784,29.68612],[-85.7731,30.15261],[-86.4,30.4],[-87.53036,30.27433],[-88.41782,30.3849],[-89.18049,30.31598],[-89.593831,30.159994],[-89.413735,29.89419],[-89.43,29.48864],[-89.21767,29.29108],[-89.40823,29.15961],[-89.77928,29.30714],[-90.15463,29.11743],[-90.880225,29.148535],[-91.626785,29.677],[-92.49906,29.5523],[-93.22637,29.78375],[-93.84842,29.71363],[-94.69,29.48],[-95.60026,28.73863],[-96.59404,28.30748],[-97.14,27.83],[-97.37,27.38],[-97.38,26.69],[-97.33,26.21],[-97.14,25.87],[-97.53,25.84],[-98.24,26.06],[-99.02,26.37],[-99.3,26.84],[-99.52,27.54],[-100.11,28.11],[-100.45584,28.69612],[-100.9576,29.38071],[-101.6624,29.7793],[-102.48,29.76],[-103.11,28.97],[-103.94,29.27],[-104.45697,29.57196],[-104.70575,30.12173],[-105.03737,30.64402],[-105.63159,31.08383],[-106.1429,31.39995],[-106.50759,31.75452],[-108.24,31.754854],[-108.24194,31.34222],[-109.035,31.34194],[-111.02361,31.33472],[-113.30498,32.03914],[-114.815,32.52528],[-114.72139,32.72083],[-115.99135,32.61239],[-117.12776,32.53534],[-117.295938,33.046225],[-117.944,33.621236],[-118.410602,33.740909],[-118.519895,34.027782],[-119.081,34.078],[-119.438841,34.348477],[-120.36778,34.44711],[-120.62286,34.60855],[-120.74433,35.15686],[-121.71457,36.16153],[-122.54747,37.55176],[-122.51201,37.78339],[-122.95319,38.11371],[-123.7272,38.95166],[-123.86517,39.76699],[-124.39807,40.3132],[-124.17886,41.14202],[-124.2137,41.99964],[-124.53284,42.76599],[-124.14214,43.70838],[-124.020535,44.615895],[-123.89893,45.52341],[-124.079635,46.86475],[-124.39567,47.72017],[-124.68721,48.184433],[-124.566101,48.379715],[-123.12,48.04],[-122.58736,47.096],[-122.34,47.36],[-122.5,48.18],[-122.84,49],[-120,49],[-117.03121,49],[-116.04818,49],[-113,49],[-110.05,49],[-107.05,49],[-104.04826,48.99986],[-100.65,49],[-97.22872,49.0007],[-95.15907,49],[-95.15609,49.38425],[-94.81758,49.38905]]],[[[-153.006314,57.115842],[-154.00509,56.734677],[-154.516403,56.992749],[-154.670993,57.461196],[-153.76278,57.816575],[-153.228729,57.968968],[-152.564791,57.901427],[-152.141147,57.591059],[-153.006314,57.115842]]],[[[-165.579164,59.909987],[-166.19277,59.754441],[-166.848337,59.941406],[-167.455277,60.213069],[-166.467792,60.38417],[-165.67443,60.293607],[-165.579164,59.909987]]],[[[-171.731657,63.782515],[-171.114434,63.592191],[-170.491112,63.694975],[-169.682505,63.431116],[-168.689439,63.297506],[-168.771941,63.188598],[-169.52944,62.976931],[-170.290556,63.194438],[-170.671386,63.375822],[-171.553063,63.317789],[-171.791111,63.405846],[-171.731657,63.782515]]],[[[-155.06779,71.147776],[-154.344165,70.696409],[-153.900006,70.889989],[-152.210006,70.829992],[-152.270002,70.600006],[-150.739992,70.430017],[-149.720003,70.53001],[-147.613362,70.214035],[-145.68999,70.12001],[-144.920011,69.989992],[-143.589446,70.152514],[-142.07251,69.851938],[-140.985988,69.711998],[-140.992499,66.000029],[-140.99777,60.306397],[-140.012998,60.276838],[-139.039,60.000007],[-138.34089,59.56211],[-137.4525,58.905],[-136.47972,59.46389],[-135.47583,59.78778],[-134.945,59.27056],[-134.27111,58.86111],[-133.355549,58.410285],[-132.73042,57.69289],[-131.70781,56.55212],[-130.00778,55.91583],[-129.979994,55.284998],[-130.53611,54.802753],[-131.085818,55.178906],[-131.967211,55.497776],[-132.250011,56.369996],[-133.539181,57.178887],[-134.078063,58.123068],[-135.038211,58.187715],[-136.628062,58.212209],[-137.800006,58.499995],[-139.867787,59.537762],[-140.825274,59.727517],[-142.574444,60.084447],[-143.958881,59.99918],[-145.925557,60.45861],[-147.114374,60.884656],[-148.224306,60.672989],[-148.018066,59.978329],[-148.570823,59.914173],[-149.727858,59.705658],[-150.608243,59.368211],[-151.716393,59.155821],[-151.859433,59.744984],[-151.409719,60.725803],[-150.346941,61.033588],[-150.621111,61.284425],[-151.895839,60.727198],[-152.57833,60.061657],[-154.019172,59.350279],[-153.287511,58.864728],[-154.232492,58.146374],[-155.307491,57.727795],[-156.308335,57.422774],[-156.556097,56.979985],[-158.117217,56.463608],[-158.433321,55.994154],[-159.603327,55.566686],[-160.28972,55.643581],[-161.223048,55.364735],[-162.237766,55.024187],[-163.069447,54.689737],[-164.785569,54.404173],[-164.942226,54.572225],[-163.84834,55.039431],[-162.870001,55.348043],[-161.804175,55.894986],[-160.563605,56.008055],[-160.07056,56.418055],[-158.684443,57.016675],[-158.461097,57.216921],[-157.72277,57.570001],[-157.550274,58.328326],[-157.041675,58.918885],[-158.194731,58.615802],[-158.517218,58.787781],[-159.058606,58.424186],[-159.711667,58.93139],[-159.981289,58.572549],[-160.355271,59.071123],[-161.355003,58.670838],[-161.968894,58.671665],[-162.054987,59.266925],[-161.874171,59.633621],[-162.518059,59.989724],[-163.818341,59.798056],[-164.662218,60.267484],[-165.346388,60.507496],[-165.350832,61.073895],[-166.121379,61.500019],[-165.734452,62.074997],[-164.919179,62.633076],[-164.562508,63.146378],[-163.753332,63.219449],[-163.067224,63.059459],[-162.260555,63.541936],[-161.53445,63.455817],[-160.772507,63.766108],[-160.958335,64.222799],[-161.518068,64.402788],[-160.777778,64.788604],[-161.391926,64.777235],[-162.45305,64.559445],[-162.757786,64.338605],[-163.546394,64.55916],[-164.96083,64.446945],[-166.425288,64.686672],[-166.845004,65.088896],[-168.11056,65.669997],[-166.705271,66.088318],[-164.47471,66.57666],[-163.652512,66.57666],[-163.788602,66.077207],[-161.677774,66.11612],[-162.489715,66.735565],[-163.719717,67.116395],[-164.430991,67.616338],[-165.390287,68.042772],[-166.764441,68.358877],[-166.204707,68.883031],[-164.430811,68.915535],[-163.168614,69.371115],[-162.930566,69.858062],[-161.908897,70.33333],[-160.934797,70.44769],[-159.039176,70.891642],[-158.119723,70.824721],[-156.580825,71.357764],[-155.06779,71.147776]]]]}}
]}
""".strip()
)


class TestTileManagerCacheGeojsonCoverage(TileCacheTestBase):
    def setup_method(self):
        TileCacheTestBase.setup_method(self)

        with TempFile() as tf:
            with open(tf, 'wb') as f:
                f.write(boundary_geojson)
            conf = {'datasource': tf, 'srs': 'EPSG:4326'}
            self.cache = RecordFileCache(self.cache_dir, 'png', coverage=load_coverage(conf))

    def test_load_tiles_in_coverage(self, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90], origin='ul')
        image_opts = ImageOptions(format='image/png')
        tm = TileManager(
            grid, self.cache, [], 'png',
            locker=tile_locker,
            image_opts=image_opts,
        )

        coords = [(3, 2, 4), (11, 9, 6), (17, 11, 7), (359, 325, 11), (2996, 2513, 14), (22923, 20919, 17)]
        collection = tm.load_tile_coords(coords)

        # Check that tiles inside of coverage loaded
        assert all(coord in collection for coord in coords)
        assert all(t.coord is not None for t in collection)

        all(t.coord in self.cache.stored_tiles for t in collection)
        assert self.cache.loaded_tiles == counting_set(coords)

    def test_empty_tiles_outside_coverage(self, tile_locker):
        grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90], origin='ul')
        image_opts = ImageOptions(format='image/png')
        tm = TileManager(
            grid, self.cache, [], 'png',
            locker=tile_locker,
            image_opts=image_opts,
        )

        coords = [(3, 3, 4), (5, 3, 4), (8, 11, 6), (19, 11, 7), (38, 25, 8), (359, 328, 11), (22922, 20922, 17)]
        collection = tm.load_tile_coords(coords)

        # Check that tiles did not load
        assert collection.blank
        assert all(t.coord is None for t in collection)

        assert self.cache.stored_tiles == set([])
        assert self.cache.loaded_tiles == counting_set([None for _ in coords])
