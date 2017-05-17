# This file is part of the MapProxy project.
# Copyright (C) 2010-2012 Omniscale <http://omniscale.de>
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

from __future__ import with_statement, division

import os
import time
try:
    import cPickle as pickle
except ImportError:
    import pickle

from mapproxy.seed.seeder import TileWalker, SeedTask, SeedProgress
from mapproxy.cache.dummy import DummyLocker
from mapproxy.cache.tile import TileManager
from mapproxy.source.tile import TiledSource
from mapproxy.grid import tile_grid_for_epsg
from mapproxy.grid import TileGrid
from mapproxy.srs import SRS
from mapproxy.util.coverage import BBOXCoverage, GeomCoverage
from mapproxy.seed.config import before_timestamp_from_options, SeedConfigurationError
from mapproxy.seed.config import LevelsList, LevelsRange, LevelsResolutionList, LevelsResolutionRange
from mapproxy.seed.util import ProgressStore
from mapproxy.test.helper import TempFile

from collections import defaultdict
from nose.tools import eq_, assert_almost_equal, raises
from nose.plugins.skip import SkipTest

try:
    from shapely.wkt import loads as load_wkt
    load_wkt # prevent lint warning
except ImportError:
    load_wkt = None

class MockSeedPool(object):
    def __init__(self):
        self.seeded_tiles = defaultdict(set)
    def process(self, tiles, progess):
        for x, y, level in tiles:
            self.seeded_tiles[level].add((x, y))

class MockCache(object):
    def is_cached(self, tile):
        return False

class TestSeeder(object):
    def setup(self):
        self.grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        self.source = TiledSource(self.grid, None)
        self.tile_mgr = TileManager(self.grid, MockCache(), [self.source], 'png',
            locker=DummyLocker())
        self.seed_pool = MockSeedPool()

    def make_bbox_task(self, bbox, srs, levels):
        md = dict(name='', cache_name='', grid_name='')
        coverage = BBOXCoverage(bbox, srs)
        return SeedTask(md, self.tile_mgr, levels, refresh_timestamp=None, coverage=coverage)

    def make_geom_task(self, geom, srs, levels):
        md = dict(name='', cache_name='', grid_name='')
        coverage = GeomCoverage(geom, srs)
        return SeedTask(md, self.tile_mgr, levels, refresh_timestamp=None, coverage=coverage)

    def test_seed_full_bbox(self):
        task = self.make_bbox_task([-180, -90, 180, 90], SRS(4326), [0, 1, 2])
        seeder = TileWalker(task, self.seed_pool, handle_uncached=True)
        seeder.walk()

        eq_(len(self.seed_pool.seeded_tiles), 3)
        eq_(self.seed_pool.seeded_tiles[0], set([(0, 0)]))
        eq_(self.seed_pool.seeded_tiles[1], set([(0, 0), (1, 0)]))
        eq_(self.seed_pool.seeded_tiles[2], set([(0, 0), (1, 0), (2, 0), (3, 0),
                                                 (0, 1), (1, 1), (2, 1), (3, 1)]))

    def test_seed_small_bbox(self):
        task = self.make_bbox_task([-45, 0, 180, 90], SRS(4326), [0, 1, 2])
        seeder = TileWalker(task, self.seed_pool, handle_uncached=True)
        seeder.walk()

        eq_(len(self.seed_pool.seeded_tiles), 3)
        eq_(self.seed_pool.seeded_tiles[0], set([(0, 0)]))
        eq_(self.seed_pool.seeded_tiles[1], set([(0, 0), (1, 0)]))
        eq_(self.seed_pool.seeded_tiles[2], set([(1, 1), (2, 1), (3, 1)]))

    def test_seed_small_bbox_iregular_levels(self):
        task = self.make_bbox_task([-45, 0, 180, 90], SRS(4326), [0, 2])
        seeder = TileWalker(task, self.seed_pool, handle_uncached=True)
        seeder.walk()

        eq_(len(self.seed_pool.seeded_tiles), 2)
        eq_(self.seed_pool.seeded_tiles[0], set([(0, 0)]))
        eq_(self.seed_pool.seeded_tiles[2], set([(1, 1), (2, 1), (3, 1)]))

    def test_seed_small_bbox_transformed(self):
        bbox = SRS(4326).transform_bbox_to(SRS(900913), [-45, 0, 179, 80])
        task = self.make_bbox_task(bbox, SRS(900913), [0, 1, 2])
        seeder = TileWalker(task, self.seed_pool, handle_uncached=True)
        seeder.walk()

        eq_(len(self.seed_pool.seeded_tiles), 3)
        eq_(self.seed_pool.seeded_tiles[0], set([(0, 0)]))
        eq_(self.seed_pool.seeded_tiles[1], set([(0, 0), (1, 0)]))
        eq_(self.seed_pool.seeded_tiles[2], set([(1, 1), (2, 1), (3, 1)]))

    def test_seed_with_geom(self):
        if not load_wkt: raise SkipTest('no shapely installed')
        # box from 10 10 to 80 80 with small spike/corner to -10 60 (upper left)
        geom = load_wkt("POLYGON((10 10, 10 50, -10 60, 10 80, 80 80, 80 10, 10 10))")
        task = self.make_geom_task(geom, SRS(4326), [0, 1, 2, 3, 4])
        seeder = TileWalker(task, self.seed_pool, handle_uncached=True)
        seeder.walk()

        eq_(len(self.seed_pool.seeded_tiles), 5)
        eq_(self.seed_pool.seeded_tiles[0], set([(0, 0)]))
        eq_(self.seed_pool.seeded_tiles[1], set([(0, 0), (1, 0)]))
        eq_(self.seed_pool.seeded_tiles[2], set([(1, 1), (2, 1)]))
        eq_(self.seed_pool.seeded_tiles[3], set([(4, 2), (5, 2), (4, 3), (5, 3), (3, 3)]))
        eq_(len(self.seed_pool.seeded_tiles[4]), 4*4+2)

    def test_seed_with_res_list(self):
        if not load_wkt: raise SkipTest('no shapely installed')
        # box from 10 10 to 80 80 with small spike/corner to -10 60 (upper left)
        geom = load_wkt("POLYGON((10 10, 10 50, -10 60, 10 80, 80 80, 80 10, 10 10))")

        self.grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90],
                             res=[360/256, 360/720, 360/2000, 360/5000, 360/8000])
        self.tile_mgr = TileManager(self.grid, MockCache(), [self.source], 'png',
            locker=DummyLocker())
        task = self.make_geom_task(geom, SRS(4326), [0, 1, 2, 3, 4])
        seeder = TileWalker(task, self.seed_pool, handle_uncached=True)
        seeder.walk()

        eq_(len(self.seed_pool.seeded_tiles), 5)
        eq_(self.seed_pool.seeded_tiles[0], set([(0, 0)]))
        eq_(self.grid.grid_sizes[1], (3, 2))
        eq_(self.seed_pool.seeded_tiles[1], set([(1, 0), (1, 1), (2, 0), (2, 1)]))
        eq_(self.grid.grid_sizes[2], (8, 4))
        eq_(self.seed_pool.seeded_tiles[2], set([(4, 2), (5, 2), (4, 3), (5, 3), (3, 3)]))
        eq_(self.grid.grid_sizes[3], (20, 10))
        eq_(len(self.seed_pool.seeded_tiles[3]), 5*5+2)

    def test_seed_full_bbox_continue(self):
        task = self.make_bbox_task([-180, -90, 180, 90], SRS(4326), [0, 1, 2])
        seed_progress = SeedProgress([(0, 1), (1, 2)])
        seeder = TileWalker(task, self.seed_pool, handle_uncached=True, seed_progress=seed_progress)
        seeder.walk()

        eq_(len(self.seed_pool.seeded_tiles), 3)
        eq_(self.seed_pool.seeded_tiles[0], set([(0, 0)]))
        eq_(self.seed_pool.seeded_tiles[1], set([(0, 0), (1, 0)]))
        eq_(self.seed_pool.seeded_tiles[2], set([(2, 0), (3, 0),
                                                 (2, 1), (3, 1)]))

class TestLevels(object):
    def test_level_list(self):
        levels = LevelsList([-10, 3, 1, 3, 5, 7, 50])
        eq_(levels.for_grid(tile_grid_for_epsg(4326)),
            [1, 3, 5, 7])

    def test_level_range(self):
        levels = LevelsRange([1, 5])
        eq_(levels.for_grid(tile_grid_for_epsg(4326)),
            [1, 2, 3, 4, 5])

    def test_level_range_open_from(self):
        levels = LevelsRange([None, 5])
        eq_(levels.for_grid(tile_grid_for_epsg(4326)),
            [0, 1, 2, 3, 4, 5])

    def test_level_range_open_to(self):
        levels = LevelsRange([13, None])
        eq_(levels.for_grid(tile_grid_for_epsg(4326)),
            [13, 14, 15, 16, 17, 18, 19])

    def test_level_range_open_tos_range(self):
        levels = LevelsResolutionRange([1000, 100])
        eq_(levels.for_grid(tile_grid_for_epsg(900913)),
            [8, 9, 10, 11])

    def test_res_range_open_from(self):
        levels = LevelsResolutionRange([None, 100])
        eq_(levels.for_grid(tile_grid_for_epsg(900913)),
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])

    def test_res_range_open_to(self):
        levels = LevelsResolutionRange([1000, None])
        eq_(levels.for_grid(tile_grid_for_epsg(900913)),
            [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19])

    def test_resolution_list(self):
        levels = LevelsResolutionList([1000, 100, 500])
        eq_(levels.for_grid(tile_grid_for_epsg(900913)),
            [8, 9, 11])


class TestProgressStore(object):
    def test_load_empty(self):
        store = ProgressStore('doesnotexist.no_realy.txt')
        store.load()
        assert store.get(('foo', 'bar', 'baz')) == None

    def test_load_store(self):
        with TempFile(no_create=True) as tmp:
            with open(tmp, 'wb') as f:
                f.write(pickle.dumps({("view", "cache", "grid"): [(0, 1), (2, 4)]}))
            store = ProgressStore(tmp)
            assert store.get(('view', 'cache', 'grid')) == [(0, 1), (2, 4)]
            assert store.get(('view', 'cache', 'grid2')) == None
            store.add(('view', 'cache', 'grid'), [])
            store.add(('view', 'cache', 'grid2'), [(0, 1)])
            store.write()

            store = ProgressStore(tmp)
            assert store.get(('view', 'cache', 'grid')) == []
            assert store.get(('view', 'cache', 'grid2')) == [(0, 1)]

    def test_load_broken(self):
        with TempFile(no_create=True) as tmp:
            with open(tmp, 'wb') as f:
                f.write(b'##invaliddata')
                f.write(pickle.dumps({("view", "cache", "grid"): [(0, 1), (2, 4)]}))

            store = ProgressStore(tmp)
            assert store.status == {}


class TestRemovebreforeTimetamp(object):
    def test_from_time(self):
        ts = before_timestamp_from_options({'time': '2010-12-01T20:12:00'})
        # we don't know the timezone this test will run
        assert (1291230720.0 - 14 * 3600) < ts < (1291230720.0 + 14 * 3600)

    def test_from_mtime(self):
        with TempFile() as tmp:
            os.utime(tmp, (12376512, 12376512))
            eq_(before_timestamp_from_options({'mtime': tmp}), 12376512)

    @raises(SeedConfigurationError)
    def test_from_mtime_missing_file(self):
        before_timestamp_from_options({'mtime': '/tmp/does-not-exist-at-all,really'})

    def test_from_empty(self):
        assert_almost_equal(
            before_timestamp_from_options({}),
            time.time(), -1
        )

    def test_from_delta(self):
        assert_almost_equal(
            before_timestamp_from_options({'minutes': 15}) + 60 * 15,
            time.time(), -1
        )

class TestSeedProgress(object):
    def test_progress_identifier(self):
        old = SeedProgress()
        with old.step_down(0, 2):
            with old.step_down(0, 4):
                eq_(old.current_progress_identifier(), [(0, 2), (0, 4)])
            # previous leafs are still present
            eq_(old.current_progress_identifier(), [(0, 2), (0, 4)])
            with old.step_down(1, 4):
                eq_(old.current_progress_identifier(), [(0, 2), (1, 4)])
            eq_(old.current_progress_identifier(), [(0, 2), (1, 4)])

        eq_(old.current_progress_identifier(), []) # empty list after seed

        with old.step_down(1, 2):
            eq_(old.current_progress_identifier(), [(1, 2)])
            with old.step_down(0, 4):
                with old.step_down(1, 4):
                    eq_(old.current_progress_identifier(), [(1, 2), (0, 4), (1, 4)])

    def test_already_processed(self):
        new = SeedProgress([(0, 2)])
        with new.step_down(0, 2):
            assert not new.already_processed()
            with new.step_down(0, 2):
                assert not new.already_processed()

        new = SeedProgress([(1, 2)])
        with new.step_down(0, 2):
            assert new.already_processed()
            with new.step_down(0, 2):
                assert new.already_processed()


        new = SeedProgress([(0, 2), (1, 4), (2, 4)])
        with new.step_down(0, 2):
            assert not new.already_processed()
            with new.step_down(0, 4):
                assert new.already_processed()
            with new.step_down(1, 4):
                assert not new.already_processed()
                with new.step_down(1, 4):
                    assert new.already_processed()
                with new.step_down(2, 4):
                    assert not new.already_processed()
                with new.step_down(3, 4):
                    assert not new.already_processed()
            with new.step_down(2, 4):
                assert not new.already_processed()
