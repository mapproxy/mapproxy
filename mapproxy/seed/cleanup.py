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

import os
from mapproxy.seed.util import format_cleanup_task
from mapproxy.util import cleanup_directory
from mapproxy.seed.seeder import TileWorkerPool, TileWalker, TileCleanupWorker

def cleanup(tasks, concurrency=2, dry_run=False, skip_geoms_for_last_levels=0,
               verbose=True, progress_logger=None):
    for task in tasks:
        print format_cleanup_task(task)
        
        if task.complete_extent:
            if hasattr(task.tile_manager.cache, 'level_location'):
                simple_cleanup(task, dry_run=dry_run)
                continue
            elif hasattr(task.tile_manager.cache, 'remove_tiles_before'):
                cache_cleanup(task, dry_run=dry_run)
                continue

        tilewalker_cleanup(task, dry_run=dry_run, concurrency=concurrency,
                         skip_geoms_for_last_levels=skip_geoms_for_last_levels,
                         progress_logger=progress_logger)

def simple_cleanup(task, dry_run):
    """
    Cleanup cache level on file system level.
    """
    for level in task.levels:
        level_dir = task.tile_manager.cache.level_location(level)
        if dry_run:
            def file_handler(filename):
                print 'removing ' + filename
        else:
            file_handler = None
        print 'removing old tiles in ' + normpath(level_dir)
        cleanup_directory(level_dir, task.remove_timestamp,
            file_handler=file_handler, remove_empty_dirs=True)

def cache_cleanup(task, dry_run):
    for level in task.levels:
        print 'removing old tiles for level %s' % level
        if not dry_run:
            task.tile_manager.cache.remove_tiles_before(task.remove_timestamp)
            task.tile_manager.cleanup()

def normpath(path):
    # only supported with >= Python 2.6
    if hasattr(os.path, 'relpath'):
        path = os.path.relpath(path)
    
    if path.startswith('../../'):
        path = os.path.abspath(path)
    return path

def tilewalker_cleanup(task, dry_run, concurrency, skip_geoms_for_last_levels,
    progress_logger=None):
    """
    Cleanup tiles with tile traversal.
    """
    task.tile_manager._expire_timestamp = task.remove_timestamp
    task.tile_manager.minimize_meta_requests = False
    tile_worker_pool = TileWorkerPool(task, TileCleanupWorker, progress_logger=progress_logger,
                                      dry_run=dry_run, size=concurrency)
    tile_walker = TileWalker(task, tile_worker_pool, handle_stale=True,
                             work_on_metatiles=False,
                             skip_geoms_for_last_levels=skip_geoms_for_last_levels)
    tile_walker.walk()
    tile_worker_pool.stop()
