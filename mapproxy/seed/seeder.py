# This file is part of the MapProxy project.
# Copyright (C) 2010, 2011 Omniscale <http://omniscale.de>
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

from __future__ import print_function, division

import sys
from contextlib import contextmanager
import time
try:
    import Queue
except ImportError:
    import queue as Queue

from mapproxy.config import base_config
from mapproxy.grid import MetaGrid
from mapproxy.source import SourceError
from mapproxy.config import local_base_config
from mapproxy.compat.itertools import izip_longest
from mapproxy.util.lock import LockTimeout
from mapproxy.seed.util import format_seed_task, timestamp
from mapproxy.seed.cachelock import DummyCacheLocker, CacheLockedError

from mapproxy.seed.util import (exp_backoff, ETA, limit_sub_bbox,
    status_symbol, BackoffError)

import logging
log = logging.getLogger(__name__)

NONE = 0
CONTAINS = -1
INTERSECTS = 1

# do not use multiprocessing on windows, it blows
# no lambdas, no anonymous functions/classes, no base_config(), etc.
if sys.platform == 'win32':
    import threading
    proc_class = threading.Thread
    queue_class = Queue.Queue
else:
    import multiprocessing
    proc_class = multiprocessing.Process
    queue_class = multiprocessing.Queue


class TileProcessor(object):
    def __init__(self, dry_run=False):
        self._lastlog = time.time()
        self.dry_run = dry_run

    def log_progress(self, progress):
        if (self._lastlog + .1) < time.time():
            # log progress at most every 100ms
            print('[%s] %6.2f%% %s \tETA: %s\r' % (
                timestamp(), progress[1]*100, progress[0],
                progress[2]
            ), end=' ')
            sys.stdout.flush()
            self._lastlog = time.time()

    def process(self, tiles, progress):
        if not self.dry_run:
            self.process_tiles(tiles)

        self.log_progress(progress)

    def stop(self):
        raise NotImplementedError()

    def process_tiles(self, tiles):
        raise NotImplementedError()


class TileWorkerPool(TileProcessor):
    """
    Manages multiple TileWorker.
    """
    def __init__(self, task, worker_class, size=2, dry_run=False, progress_logger=None):
        TileProcessor.__init__(self, dry_run=dry_run)
        self.tiles_queue = queue_class(size)
        self.task = task
        self.dry_run = dry_run
        self.procs = []
        self.progress_logger = progress_logger
        conf = base_config()
        for _ in range(size):
            worker = worker_class(self.task, self.tiles_queue, conf)
            worker.start()
            self.procs.append(worker)

    def process(self, tiles, progress):
        if not self.dry_run:
            while True:
                try:
                    self.tiles_queue.put(tiles, timeout=5)
                except Queue.Full:
                    alive = False
                    for proc in self.procs:
                        if proc.is_alive():
                            alive = True
                            break
                    if not alive:
                        log.warn('no workers left, stopping')
                        raise SeedInterrupted
                    continue
                else:
                    break

            if self.progress_logger:
                self.progress_logger.log_step(progress)

    def stop(self, force=False):
        """
        Stop seed workers by sending None-sentinel and joining the workers.

        :param force: Skip sending None-sentinel and join with a timeout.
                      For use when workers might be shutdown already by KeyboardInterrupt.
        """
        if not force:
            alives = 0
            for proc in self.procs:
                if proc.is_alive():
                    alives += 1

            while alives:
                # put None-sentinels to queue as long as we have workers alive
                try:
                    self.tiles_queue.put(None, timeout=1)
                    alives -= 1
                except Queue.Full:
                    alives = 0
                    for proc in self.procs:
                        if proc.is_alive():
                            alives += 1

        if force:
            timeout = 1.0
        else:
            timeout = None
        for proc in self.procs:
            proc.join(timeout)


class TileWorker(proc_class):
    def __init__(self, task, tiles_queue, conf):
        proc_class.__init__(self)
        proc_class.daemon = True
        self.task = task
        self.tile_mgr = task.tile_manager
        self.tiles_queue = tiles_queue
        self.conf = conf

    def run(self):
        with local_base_config(self.conf):
            try:
                self.work_loop()
            except KeyboardInterrupt:
                return
            except BackoffError:
                return

class TileSeedWorker(TileWorker):
    def work_loop(self):
        while True:
            tiles = self.tiles_queue.get()
            if tiles is None:
                return
            with self.tile_mgr.session():
                exp_backoff(self.tile_mgr.load_tile_coords, args=(tiles,),
                    max_repeat=100, max_backoff=600,
                    exceptions=(SourceError, IOError), ignore_exceptions=(LockTimeout, ))

class TileCleanupWorker(TileWorker):
    def work_loop(self):
        while True:
            tiles = self.tiles_queue.get()
            if tiles is None:
                return
            with self.tile_mgr.session():
                self.tile_mgr.remove_tile_coords(tiles)

class SeedProgress(object):
    def __init__(self, old_progress_identifier=None):
        self.progress = 0.0
        self.eta = ETA()
        self.level_progress_percentages = [1.0]
        self.level_progresses = []
        self.progress_str_parts = []
        self.old_level_progresses = None
        if old_progress_identifier is not None:
            self.old_level_progresses = old_progress_identifier

    def step_forward(self, subtiles=1):
        self.progress += self.level_progress_percentages[-1] / subtiles
        self.eta.update(self.progress)

    @property
    def progress_str(self):
        return ''.join(self.progress_str_parts)

    @contextmanager
    def step_down(self, i, subtiles):
        self.level_progresses.append((i, subtiles))
        self.progress_str_parts.append(status_symbol(i, subtiles))
        self.level_progress_percentages.append(self.level_progress_percentages[-1] / subtiles)
        yield
        self.level_progress_percentages.pop()
        self.progress_str_parts.pop()
        self.level_progresses.pop()

    def already_processed(self):
        if self.old_level_progresses == []:
            return True

        if self.old_level_progresses is None:
            return False

        if self.progress_is_behind(self.old_level_progresses, self.level_progresses):
            return True
        else:
            return False

    def current_progress_identifier(self):
        return self.level_progresses

    @staticmethod
    def progress_is_behind(old_progress, current_progress):
        """
        Return True if the `current_progress` is behind the `old_progress` -
        when it isn't as far as the old progress.

        >>> SeedProgress.progress_is_behind([], [(0, 1)])
        True
        >>> SeedProgress.progress_is_behind([(0, 1), (1, 4)], [(0, 1)])
        False
        >>> SeedProgress.progress_is_behind([(0, 1), (1, 4)], [(0, 1), (0, 4)])
        True
        >>> SeedProgress.progress_is_behind([(0, 1), (1, 4)], [(0, 1), (1, 4)])
        True
        >>> SeedProgress.progress_is_behind([(0, 1), (1, 4)], [(0, 1), (3, 4)])
        False

        """
        for old, current in izip_longest(old_progress, current_progress, fillvalue=(9e15, 9e15)):
            if old < current:
                return False
            if old > current:
                return True
        return True

    def running(self):
        return True

class StopProcess(Exception):
    pass

class SeedInterrupted(Exception):
    pass


class TileWalker(object):
    def __init__(self, task, worker_pool, handle_stale=False, handle_uncached=False,
                 work_on_metatiles=True, skip_geoms_for_last_levels=0, progress_logger=None,
                 seed_progress=None):
        self.tile_mgr = task.tile_manager
        self.task = task
        self.worker_pool = worker_pool
        self.handle_stale = handle_stale
        self.handle_uncached = handle_uncached
        self.work_on_metatiles = work_on_metatiles
        self.skip_geoms_for_last_levels = skip_geoms_for_last_levels
        self.progress_logger = progress_logger

        num_seed_levels = len(task.levels)
        self.report_till_level = task.levels[int(num_seed_levels * 0.8)]
        meta_size = self.tile_mgr.meta_grid.meta_size if self.tile_mgr.meta_grid else (1, 1)
        self.tiles_per_metatile = meta_size[0] * meta_size[1]
        self.grid = MetaGrid(self.tile_mgr.grid, meta_size=meta_size, meta_buffer=0)
        self.count = 0
        self.seed_progress = seed_progress or SeedProgress()

    def walk(self):
        assert self.handle_stale or self.handle_uncached
        bbox = self.task.coverage.extent.bbox_for(self.tile_mgr.grid.srs)
        if self.seed_progress.already_processed():
            # nothing to seed
            self.seed_progress.step_forward()
        else:
            try:
                self._walk(bbox, self.task.levels)
            except StopProcess:
                pass
        self.report_progress(self.task.levels[0], self.task.coverage.bbox)

    def _walk(self, cur_bbox, levels, current_level=0, all_subtiles=False):
        """
        :param cur_bbox: the bbox to seed in this call
        :param levels: list of levels to seed
        :param all_subtiles: seed all subtiles and do not check for
                             intersections with bbox/geom
        """
        bbox_, tiles, subtiles = self.grid.get_affected_level_tiles(cur_bbox, current_level)
        total_subtiles = tiles[0] * tiles[1]
        if len(levels) < self.skip_geoms_for_last_levels:
            # do not filter in last levels
            all_subtiles = True
        subtiles = self._filter_subtiles(subtiles, all_subtiles)

        if current_level in levels and current_level <= self.report_till_level:
            self.report_progress(current_level, cur_bbox)

        if not self.seed_progress.running():
            if current_level in levels:
                self.report_progress(current_level, cur_bbox)
            self.tile_mgr.cleanup()
            raise StopProcess()

        process = False;
        if current_level in levels:
            levels = levels[1:]
            process = True
        current_level += 1

        for i, (subtile, sub_bbox, intersection) in enumerate(subtiles):
            if subtile is None: # no intersection
                self.seed_progress.step_forward(total_subtiles)
                continue
            if levels: # recurse to next level
                sub_bbox = limit_sub_bbox(cur_bbox, sub_bbox)
                if intersection == CONTAINS:
                    all_subtiles = True
                else:
                    all_subtiles = False

                with self.seed_progress.step_down(i, total_subtiles):
                    if self.seed_progress.already_processed():
                        self.seed_progress.step_forward()
                    else:
                        self._walk(sub_bbox, levels, current_level=current_level,
                            all_subtiles=all_subtiles)

            if not process:
                continue

            if not self.work_on_metatiles:
                # collect actual tiles
                handle_tiles = self.grid.tile_list(subtile)
            else:
                handle_tiles = [subtile]

            if self.handle_uncached:
                handle_tiles = [t for t in handle_tiles if
                                    t is not None and
                                    not self.tile_mgr.is_cached(t)]
            elif self.handle_stale:
                handle_tiles = [t for t in handle_tiles if
                                    t is not None and
                                    self.tile_mgr.is_stale(t)]
            if handle_tiles:
                self.count += 1
                self.worker_pool.process(handle_tiles, self.seed_progress)

            if not levels:
                self.seed_progress.step_forward(total_subtiles)

        if len(levels) >= 4:
            # call cleanup to close open caches
            # for connection based caches
            self.tile_mgr.cleanup()

    def report_progress(self, level, bbox):
        if self.progress_logger:
            self.progress_logger.log_progress(self.seed_progress, level, bbox,
                self.count * self.tiles_per_metatile)

    def _filter_subtiles(self, subtiles, all_subtiles):
        """
        Return an iterator with all sub tiles.
        Yields (None, None, None) for non-intersecting tiles,
        otherwise (subtile, subtile_bbox, intersection).
        """
        for subtile in subtiles:
            if subtile is None:
                yield None, None, None
            else:
                sub_bbox = self.grid.meta_tile(subtile).bbox
                if all_subtiles:
                    intersection = CONTAINS
                else:
                    intersection = self.task.intersects(sub_bbox)
                if intersection:
                    yield subtile, sub_bbox, intersection
                else:
                    yield None, None, None

class SeedTask(object):
    def __init__(self, md, tile_manager, levels, refresh_timestamp, coverage):
        self.md = md
        self.tile_manager = tile_manager
        self.grid = tile_manager.grid
        self.levels = levels
        self.refresh_timestamp = refresh_timestamp
        self.coverage = coverage

    @property
    def id(self):
        return self.md['name'], self.md['cache_name'], self.md['grid_name']

    def intersects(self, bbox):
        if self.coverage.contains(bbox, self.grid.srs): return CONTAINS
        if self.coverage.intersects(bbox, self.grid.srs): return INTERSECTS
        return NONE

class CleanupTask(object):
    """
    :param coverage: area for the cleanup
    :param complete_extent: ``True`` if `coverage` equals the extent of the grid
    """
    def __init__(self, md, tile_manager, levels, remove_timestamp, coverage, complete_extent=False):
        self.md = md
        self.tile_manager = tile_manager
        self.grid = tile_manager.grid
        self.levels = levels
        self.remove_timestamp = remove_timestamp
        self.coverage = coverage
        self.complete_extent = complete_extent

    def intersects(self, bbox):
        if self.coverage.contains(bbox, self.grid.srs): return CONTAINS
        if self.coverage.intersects(bbox, self.grid.srs): return INTERSECTS
        return NONE

def seed(tasks, concurrency=2, dry_run=False, skip_geoms_for_last_levels=0,
    progress_logger=None, cache_locker=None):
    if cache_locker is None:
        cache_locker = DummyCacheLocker()

    active_tasks = tasks[::-1]
    while active_tasks:
        task = active_tasks[-1]
        print(format_seed_task(task))

        wait = len(active_tasks) == 1
        try:
            with cache_locker.lock(task.md['cache_name'], no_block=not wait):
                if progress_logger and progress_logger.progress_store:
                    progress_logger.current_task_id = task.id
                    start_progress = progress_logger.progress_store.get(task.id)
                else:
                    start_progress = None
                seed_progress = SeedProgress(old_progress_identifier=start_progress)
                seed_task(task, concurrency, dry_run, skip_geoms_for_last_levels, progress_logger,
                    seed_progress=seed_progress)
        except CacheLockedError:
            print('    ...cache is locked, skipping')
            active_tasks = [task] + active_tasks[:-1]
        else:
            active_tasks.pop()


def seed_task(task, concurrency=2, dry_run=False, skip_geoms_for_last_levels=0,
    progress_logger=None, seed_progress=None):
    if task.coverage is False:
        return
    if task.refresh_timestamp is not None:
        task.tile_manager._expire_timestamp = task.refresh_timestamp
    task.tile_manager.minimize_meta_requests = False
    tile_worker_pool = TileWorkerPool(task, TileSeedWorker, dry_run=dry_run,
        size=concurrency, progress_logger=progress_logger)
    tile_walker = TileWalker(task, tile_worker_pool, handle_uncached=True,
        skip_geoms_for_last_levels=skip_geoms_for_last_levels, progress_logger=progress_logger,
        seed_progress=seed_progress)
    try:
        tile_walker.walk()
    except KeyboardInterrupt:
        tile_worker_pool.stop(force=True)
        raise
    finally:
        tile_worker_pool.stop()


