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
from mapproxy.compat.itertools import izip_longest
from mapproxy.seed.util import format_cleanup_task
from mapproxy.util.fs import cleanup_directory
from mapproxy.seed.seeder import (
    TileWorkerPool, TileWalker, TileCleanupWorker,
    SeedProgress,
)
from mapproxy.seed.util import ProgressLog

def cleanup(tasks, concurrency=2, dry_run=False, skip_geoms_for_last_levels=0,
               verbose=True, progress_logger=None):
    for task in tasks:
        print(format_cleanup_task(task))

        if task.coverage is False:
            continue

        # seed_progress for tilewalker cleanup
        seed_progress = None
        # cleanup_progress for os.walk based cleanup
        cleanup_progress = None
        if progress_logger and progress_logger.progress_store:
            progress_logger.current_task_id = task.id
            start_progress = progress_logger.progress_store.get(task.id)
            seed_progress = SeedProgress(old_progress_identifier=start_progress)
            cleanup_progress = DirectoryCleanupProgress(old_dir=start_progress)

        if task.complete_extent:
            if callable(getattr(task.tile_manager.cache, 'level_location', None)):
                simple_cleanup(task, dry_run=dry_run, progress_logger=progress_logger,
                    cleanup_progress=cleanup_progress)
                task.tile_manager.cleanup()
                continue
            elif callable(getattr(task.tile_manager.cache, 'remove_level_tiles_before', None)):
                cache_cleanup(task, dry_run=dry_run, progress_logger=progress_logger)
                task.tile_manager.cleanup()
                continue

        tilewalker_cleanup(task, dry_run=dry_run, concurrency=concurrency,
                         skip_geoms_for_last_levels=skip_geoms_for_last_levels,
                         progress_logger=progress_logger,
                         seed_progress=seed_progress,
        )
        task.tile_manager.cleanup()


def simple_cleanup(task, dry_run, progress_logger=None, cleanup_progress=None):
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
            if progress_logger.progress_store:
                cleanup_progress.step_dir(level_dir)
                if cleanup_progress.already_processed():
                    continue
                progress_logger.progress_store.add(
                    task.id,
                    cleanup_progress.current_progress_identifier(),
                )
                progress_logger.progress_store.write()

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

    path = os.path.relpath(path)

    if path.startswith('../../'):
        path = os.path.abspath(path)
    return path

def tilewalker_cleanup(task, dry_run, concurrency, skip_geoms_for_last_levels,
    progress_logger=None, seed_progress=None):
    """
    Cleanup tiles with tile traversal.
    """
    task.tile_manager._expire_timestamp = task.remove_timestamp
    task.tile_manager.minimize_meta_requests = False
    tile_worker_pool = TileWorkerPool(task, TileCleanupWorker, progress_logger=progress_logger,
                                      dry_run=dry_run, size=concurrency)
    tile_walker = TileWalker(task, tile_worker_pool, handle_stale=True,
                             work_on_metatiles=False, progress_logger=progress_logger,
                             skip_geoms_for_last_levels=skip_geoms_for_last_levels,
                             seed_progress=seed_progress)
    try:
        tile_walker.walk()
    except KeyboardInterrupt:
        tile_worker_pool.stop(force=True)
        raise
    finally:
        tile_worker_pool.stop()


class DirectoryCleanupProgress(object):
    def __init__(self, old_dir=None):
        self.old_dir = old_dir
        self.current_dir = None

    def step_dir(self, dir):
        self.current_dir = dir

    def already_processed(self):
        return self.can_skip(self.old_dir, self.current_dir)

    def current_progress_identifier(self):
        if self.already_processed() or self.current_dir is None:
            return self.old_dir
        return self.current_dir

    @staticmethod
    def can_skip(old_dir, current_dir):
        """
        Return True if the `current_dir` is before `old_dir` when compared
        lexicographic.

        >>> DirectoryCleanupProgress.can_skip(None, '/00')
        False
        >>> DirectoryCleanupProgress.can_skip(None, '/00/000/000')
        False

        >>> DirectoryCleanupProgress.can_skip('/01/000/001', '/00')
        True
        >>> DirectoryCleanupProgress.can_skip('/01/000/001', '/01/000/000')
        True
        >>> DirectoryCleanupProgress.can_skip('/01/000/001', '/01/000/000/000')
        True
        >>> DirectoryCleanupProgress.can_skip('/01/000/001', '/01/000/001')
        False
        >>> DirectoryCleanupProgress.can_skip('/01/000/001', '/01/000/001/000')
        False
        """
        if old_dir is None:
            return False
        if current_dir is None:
            return False
        for old, current in izip_longest(old_dir.split(os.path.sep), current_dir.split(os.path.sep), fillvalue=None):
            if old is None:
                return False
            if current is None:
                return False
            if old < current:
                return False
            if old > current:
                return True
        return False

    def running(self):
        return True
