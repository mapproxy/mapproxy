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

from __future__ import print_function

import os
from mapproxy.seed.util import format_cleanup_task
from mapproxy.util.fs import cleanup_directory
from mapproxy.seed.seeder import TileWorkerPool, TileWalker, TileCleanupWorker

def cleanup(tasks, concurrency=2, dry_run=False, skip_geoms_for_last_levels=0,
               verbose=True, progress_logger=None):
    for task in tasks:
        print(format_cleanup_task(task))

        if task.coverage is False:
            continue

        if task.complete_extent:
            if hasattr(task.tile_manager.cache, 'level_location'):
                simple_cleanup(task, dry_run=dry_run, progress_logger=progress_logger)
                continue
            elif hasattr(task.tile_manager.cache, 'remove_level_tiles_before'):
                cache_cleanup(task, dry_run=dry_run, progress_logger=progress_logger)
                continue

        tilewalker_cleanup(task, dry_run=dry_run, concurrency=concurrency,
                         skip_geoms_for_last_levels=skip_geoms_for_last_levels,
                         progress_logger=progress_logger)

def simple_cleanup(task, dry_run, progress_logger=None):
    """
    Cleanup cache level on file system level.
    """
    for level in task.levels:
        level_dir = task.tile_manager.cache.level_location(level)
        if dry_run:
            def file_handler(filename):
                print('removing ' + filename)
        else:
            file_handler = None
        if progress_logger:
            progress_logger.log_message('removing old tiles in ' + normpath(level_dir))
        cleanup_directory(level_dir, task.remove_timestamp,
            file_handler=file_handler, remove_empty_dirs=True)

def cache_cleanup(task, dry_run, progress_logger=None):
    for level in task.levels:
        if progress_logger:
            progress_logger.log_message('removing old tiles for level %s' % level)
        if not dry_run:
            task.tile_manager.cache.remove_level_tiles_before(level, task.remove_timestamp)
            task.tile_manager.cleanup()

def normpath(path):
    # relpath doesn't support UNC
    if path.startswith('\\'):
        return path

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
                             work_on_metatiles=False, progress_logger=progress_logger,
                             skip_geoms_for_last_levels=skip_geoms_for_last_levels)
    try:
        tile_walker.walk()
    except KeyboardInterrupt:
        tile_worker_pool.stop(force=True)
        raise
    finally:
        tile_worker_pool.stop()
