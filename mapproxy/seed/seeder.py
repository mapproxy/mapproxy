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

from __future__ import with_statement, division
import sys
import time

from contextlib import contextmanager

from mapproxy.config import base_config
from mapproxy.grid import MetaGrid
from mapproxy.source import SourceError
from mapproxy.util import local_base_config
from mapproxy.seed.util import format_seed_task

from mapproxy.seed.util import (exp_backoff, ETA, limit_sub_bbox,
    status_symbol, format_bbox)

NONE = 0
CONTAINS = -1
INTERSECTS = 1

# do not use multiprocessing on windows, it blows
# no lambdas, no anonymous functions/classes, no base_config(), etc.
if sys.platform == 'win32':
    import Queue
    import threading
    proc_class = threading.Thread
    queue_class = Queue.Queue
else:
    import multiprocessing
    proc_class = multiprocessing.Process
    queue_class = multiprocessing.Queue


class TileWorkerPool(object):
    """
    Manages multiple TileWorker.
    """
    def __init__(self, task, worker_class, size=2, dry_run=False, progress_logger=None):
        self.tiles_queue = queue_class(size)
        self.task = task
        self.dry_run = dry_run
        self.procs = []
        self.progress_logger = progress_logger
        conf = base_config()
        for _ in xrange(size):
            worker = worker_class(self.task, self.tiles_queue, conf)
            worker.start()
            self.procs.append(worker)
    
    def process(self, tiles, progress):
        if not self.dry_run:
            self.tiles_queue.put(tiles)
        
        if self.progress_logger:
            self.progress_logger.log_step(progress)
    
    def stop(self):
        for _ in xrange(len(self.procs)):
            self.tiles_queue.put(None)
        
        for proc in self.procs:
            proc.join()


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

class TileSeedWorker(TileWorker):
    def work_loop(self):
        while True:
            tiles = self.tiles_queue.get()
            if tiles is None:
                return
            with self.tile_mgr.session():
                exp_backoff(self.tile_mgr.load_tile_coords, args=(tiles,),
                        exceptions=(SourceError, IOError))

class TileCleanupWorker(TileWorker):
    def work_loop(self):
        while True:
            tiles = self.tiles_queue.get()
            if tiles is None:
                return
            with self.tile_mgr.session():
                self.tile_mgr.remove_tile_coords(tiles)
                
class TileWalker(object):
    def __init__(self, task, worker_pool, handle_stale=False, handle_uncached=False,
                 work_on_metatiles=True, skip_geoms_for_last_levels=0, progress_logger=None):
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
        self.progress = 0.0
        self.eta = ETA()
        self.count = 0
    
    def walk(self):
        assert self.handle_stale or self.handle_uncached
        bbox = self.task.coverage.extent.bbox_for(self.tile_mgr.grid.srs)
        self._walk(bbox, self.task.levels)
        self.report_progress(self.task.levels[0], self.task.coverage.bbox)

    def _walk(self, cur_bbox, levels, progess_str='', progress=1.0, all_subtiles=False):
        """
        :param cur_bbox: the bbox to seed in this call
        :param levels: list of levels to seed
        :param all_subtiles: seed all subtiles and do not check for
                             intersections with bbox/geom
        """
        current_level, levels = levels[0], levels[1:]
        bbox_, tiles, subtiles = self.grid.get_affected_level_tiles(cur_bbox, current_level)
        total_subtiles = tiles[0] * tiles[1]
        
        if len(levels) < self.skip_geoms_for_last_levels:
            # do not filter in last levels
            all_subtiles = True
        subtiles = self._filter_subtiles(subtiles, all_subtiles)
        
        if current_level <= self.report_till_level:
            self.report_progress(current_level, cur_bbox)
        
        progress = progress / total_subtiles
        for i, (subtile, sub_bbox, intersection) in enumerate(subtiles):
            if subtile is None: # no intersection
                self.progress += progress
                continue
            if levels: # recurse to next level
                sub_bbox = limit_sub_bbox(cur_bbox, sub_bbox)
                cur_progess_str = progess_str + status_symbol(i, total_subtiles)
                if intersection == CONTAINS:
                    all_subtiles = True
                else:
                    all_subtiles = False
                self._walk(sub_bbox, levels, cur_progess_str,
                           all_subtiles=all_subtiles, progress=progress)
            
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
                self.worker_pool.process(handle_tiles,
                    (progess_str, self.progress, self.eta))
                
            if not levels:
                self.progress += progress
        
        if len(levels) >= 4:
            # call cleanup to close open caches
            # for connection based caches
            self.tile_mgr.cleanup()
        self.eta.update(self.progress)
    
    def report_progress(self, level, bbox):
        if self.progress_logger:
            self.progress_logger.log_progress(self.progress, level, bbox,
                self.count * self.tiles_per_metatile, self.eta)

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
    progress_logger=None):
    for task in tasks:
        print format_seed_task(task)
        if task.refresh_timestamp is not None:
            task.tile_manager._expire_timestamp = task.refresh_timestamp
        task.tile_manager.minimize_meta_requests = False
        tile_worker_pool = TileWorkerPool(task, TileSeedWorker, dry_run=dry_run,
            size=concurrency, progress_logger=progress_logger)
        tile_walker = TileWalker(task, tile_worker_pool, handle_uncached=True,
            skip_geoms_for_last_levels=skip_geoms_for_last_levels, progress_logger=progress_logger)
        tile_walker.walk()
        tile_worker_pool.stop()

# class CacheSeeder(object):
#     """
#     Seed multiple caches with the same option set.
#     """
#     def __init__(self, caches, remove_before, dry_run=False, concurrency=2,
#                  skip_geoms_for_last_levels=0):
#         self.remove_before = remove_before
#         self.dry_run = dry_run
#         self.caches = caches
#         self.concurrency = concurrency
#         self.seeded_caches = []
#         self.skip_geoms_for_last_levels = skip_geoms_for_last_levels
#     
#     def seed_view(self, bbox, level, bbox_srs, cache_srs, geom=None):
#         for srs, tile_mgr in self.caches.iteritems():
#             if not cache_srs or srs in cache_srs:
#                 print "[%s] ... srs '%s'" % (timestamp(), srs.srs_code)
#                 self.seeded_caches.append(tile_mgr)
#                 if self.remove_before:
#                     tile_mgr._expire_timestamp = self.remove_before
#                 tile_mgr.minimize_meta_requests = False
#                 seed_pool = TileWorkerPool(tile_mgr, dry_run=self.dry_run, size=self.concurrency)
#                 seed_task = SeedTask(bbox, level, bbox_srs, srs, geom)
#                 seeder = TileWalker(tile_mgr, seed_task, seed_pool, self.skip_geoms_for_last_levels)
#                 seeder.seed()
#                 seed_pool.stop()
#     
#     def cleanup(self):
#         for tile_mgr in self.seeded_caches:
#             for i in range(tile_mgr.grid.levels):
#                 level_dir = tile_mgr.cache.level_location(i)
#                 if self.dry_run:
#                     def file_handler(filename):
#                         print 'removing ' + filename
#                 else:
#                     file_handler = None
#                 print 'removing oldfiles in ' + level_dir
#                 cleanup_directory(level_dir, self.remove_before,
#                     file_handler=file_handler)

