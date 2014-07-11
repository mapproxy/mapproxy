# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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
import sys
import time

from contextlib import contextmanager

from mapproxy.util.lock import FileLock, cleanup_lockdir, DummyLock

class CacheBackendError(Exception):
    pass

@contextmanager
def tile_buffer(tile):
    data = tile.source.as_buffer(seekable=True)
    data.seek(0)
    yield data
    tile.size = data.tell()
    if not tile.timestamp:
        tile.timestamp = time.time()
    data.seek(0)
    tile.stored = True

class TileCacheBase(object):
    """
    Base implementation of a tile cache.
    """

    supports_timestamp = True

    def load_tile(self, tile, with_metadata=False):
        raise NotImplementedError()

    def load_tiles(self, tiles, with_metadata=False):
        all_succeed = True
        for tile in tiles:
            if not self.load_tile(tile, with_metadata=with_metadata):
                all_succeed = False
        return all_succeed

    def store_tile(self, tile):
        raise NotImplementedError()

    def store_tiles(self, tiles):
        all_succeed = True
        for tile in tiles:
            if not self.store_tile(tile):
                all_succeed = False
        return all_succeed

    def remove_tile(self, tile):
        raise NotImplementedError()

    def remove_tiles(self, tiles):
        for tile in tiles:
            self.remove_tile(tile)

    def is_cached(self, tile):
        """
        Return ``True`` if the tile is cached.
        """
        raise NotImplementedError()

    def load_tile_metadata(self, tile):
        """
        Fill the metadata attributes of `tile`.
        Sets ``.timestamp`` and ``.size``.
        """
        raise NotImplementedError()

# whether we immediately remove lock files or not
REMOVE_ON_UNLOCK = True
if sys.platform == 'win32':
    # windows does not handle this well
    REMOVE_ON_UNLOCK = False

class TileLocker(object):
    def __init__(self, lock_dir, lock_timeout, lock_cache_id):
        self.lock_dir = lock_dir
        self.lock_timeout = lock_timeout
        self.lock_cache_id = lock_cache_id

    def lock_filename(self, tile):
        return os.path.join(self.lock_dir, self.lock_cache_id + '-' +
                            '-'.join(map(str, tile.coord)) + '.lck')

    def lock(self, tile):
        """
        Returns a lock object for this tile.
        """
        if getattr(self, 'locking_disabled', False):
            return DummyLock()
        lock_filename = self.lock_filename(tile)
        cleanup_lockdir(self.lock_dir, max_lock_time=self.lock_timeout + 10,
            force=False)
        return FileLock(lock_filename, timeout=self.lock_timeout,
            remove_on_unlock=REMOVE_ON_UNLOCK)
