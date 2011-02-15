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

import os
from mapproxy.seed.util import format_cleanup_task
from mapproxy.util import cleanup_directory
from mapproxy.seed.seeder import TileWorkerPool, TileWalker, TileCleanupWorker

def cleanup(tasks, concurrency=2, dry_run=False, skip_geoms_for_last_levels=0,
               verbose=True):
    for task in tasks:
        print format_cleanup_task(task)
        
        if not task.coverage:
            simple_cleanup(task, dry_run=dry_run)
        else:
            coverage_cleanup(task, dry_run=dry_run, concurrency=concurrency,
                             skip_geoms_for_last_levels=skip_geoms_for_last_levels)

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

def normpath(path):
    # only supported with >= Python 2.6
    if hasattr(os.path, 'relpath'):
        path = os.path.relpath(path)
    
    if path.startswith('../../'):
        path = os.path.abspath(path)
    return path

def coverage_cleanup(task, dry_run, concurrency, skip_geoms_for_last_levels):
    """
    Cleanup tiles with tile traversal.
    """
    task.tile_manager._expire_timestamp = task.remove_timestamp
    task.tile_manager.minimize_meta_requests = False
    tile_worker_pool = TileWorkerPool(task, TileCleanupWorker,
                                      dry_run=dry_run, size=concurrency)
    tile_walker = TileWalker(task, tile_worker_pool, handle_stale=True,
                             work_on_metatiles=False,
                             skip_geoms_for_last_levels=skip_geoms_for_last_levels)
    tile_walker.walk()
    tile_worker_pool.stop()
