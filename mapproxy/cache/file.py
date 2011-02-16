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

from __future__ import with_statement
import os
import sys
import time
import errno
import hashlib

from mapproxy.util.lock import FileLock, DummyLock, cleanup_lockdir
from mapproxy.image import ImageSource, is_single_color_image
from mapproxy.config import base_config

import logging
log = logging.getLogger(__name__)

class FileCache(object):
    """
    This class is responsible to store and load the actual tile data.
    """
    def __init__(self, cache_dir, file_ext, lock_dir=None, pre_store_filter=None,
                 link_single_color_images=False):
        """
        :param cache_dir: the path where the tile will be stored
        :param file_ext: the file extension that will be appended to
            each tile (e.g. 'png')
        :param pre_store_filter: a list with filter. each filter will be called
            with a tile before it will be stored to disc. the filter should 
            return this or a new tile object.
        """
        self.cache_dir = cache_dir
        if lock_dir is None:
            lock_dir = os.path.join(cache_dir, 'tile_locks')
        self.lock_dir = lock_dir
        self.file_ext = file_ext
        self._lock_cache_id = None
        if pre_store_filter is None:
            pre_store_filter = []
        self.pre_store_filter = pre_store_filter
        if link_single_color_images and sys.platform == 'win32':
            log.warn('link_single_color_images not supported on windows')
            link_single_color_images = False
        self.link_single_color_images = link_single_color_images
    
    def level_location(self, level):
        """
        Return the path where all tiles for `level` will be stored.
        
        >>> c = FileCache(cache_dir='/tmp/cache/', file_ext='png')
        >>> c.level_location(2)
        '/tmp/cache/02'
        """
        return os.path.join(self.cache_dir, "%02d" % level)
    
    def tile_location(self, tile, create_dir=False):
        """
        Return the location of the `tile`. Caches the result as ``location``
        property of the `tile`.
        
        :param tile: the tile object
        :param create_dir: if True, create all necessary directories
        :return: the full filename of the tile
        
        >>> from mapproxy.cache.tile import Tile
        >>> c = FileCache(cache_dir='/tmp/cache/', file_ext='png')
        >>> c.tile_location(Tile((3, 4, 2))).replace('\\\\', '/')
        '/tmp/cache/02/000/000/003/000/000/004.png'
        """
        if tile.location is None:
            x, y, z = tile.coord
            parts = (self.level_location(z),
                     "%03d" % int(x / 1000000),
                     "%03d" % (int(x / 1000) % 1000),
                     "%03d" % (int(x) % 1000),
                     "%03d" % int(y / 1000000),
                     "%03d" % (int(y / 1000) % 1000),
                     "%03d.%s" % (int(y) % 1000, self.file_ext))
            tile.location = os.path.join(*parts)
        if create_dir:
            _create_dir(tile.location)
        return tile.location
    
    def _single_color_tile_location(self, color, create_dir=False):
        """
        >>> c = FileCache(cache_dir='/tmp/cache/', file_ext='png')
        >>> c._single_color_tile_location((254, 0, 4)).replace('\\\\', '/')
        '/tmp/cache/single_color_tiles/fe0004.png'
        """
        parts = (
            self.cache_dir,
            'single_color_tiles',
            ''.join('%02x' % v for v in color) + '.' + self.file_ext
        )
        location = os.path.join(*parts)
        if create_dir:
            _create_dir(location)
        return location
    
    def timestamp_created(self, tile):
        """
        Return the timestamp of the last modification of the tile.
        """
        self._update_tile_metadata(tile)
        return tile.timestamp
    
    def _update_tile_metadata(self, tile):
        location = self.tile_location(tile)
        stats = os.lstat(location)
        tile.timestamp = stats.st_mtime
        tile.size = stats.st_size
    
    def is_cached(self, tile):
        """
        Returns ``True`` if the tile data is present.
        """
        if tile.is_missing():
            location = self.tile_location(tile)
            if os.path.exists(location):
                return True
            else:
                return False
        else:
            return True
    
    def load(self, tile, with_metadata=False):
        """
        Fills the `Tile.source` of the `tile` if it is cached.
        If it is not cached or if the ``.coord`` is ``None``, nothing happens.
        """
        if not tile.is_missing():
            return True
        
        location = self.tile_location(tile)
        
        if os.path.exists(location):
            if with_metadata:
                self._update_tile_metadata(tile)
            tile.source = ImageSource(location)
            return True
        return False
    
    def remove(self, tile):
        location = self.tile_location(tile)
        try:
            os.remove(location)
        except OSError, ex:
            if ex.errno != errno.ENOENT: raise
    
    def store(self, tile):
        """
        Add the given `tile` to the file cache. Stores the `Tile.source` to
        `FileCache.tile_location`.
        
        All ``pre_store_filter`` will be called with the tile, before
        it will be stored.
        """
        if tile.stored:
            return
        
        tile_loc = self.tile_location(tile, create_dir=True)
        
        if self.link_single_color_images:
            color = is_single_color_image(tile.source.as_image())
            if color:
                real_tile_loc = self._single_color_tile_location(color, create_dir=True)
                if not os.path.exists(real_tile_loc):
                    self._store(tile, real_tile_loc)
                
                log.debug('linking %r from %s to %s',
                          tile.coord, real_tile_loc, tile_loc)
                
                # remove any file before symlinking.
                # exists() returns False if it links to non-
                # existing file, islink() test to check that
                if os.path.exists(tile_loc) or os.path.islink(tile_loc):
                    os.unlink(tile_loc)
                
                os.symlink(real_tile_loc, tile_loc)
                return
        
        self._store(tile, tile_loc)
    
    def _store(self, tile, location):
        if os.path.islink(location):
            os.unlink(location)
        
        for img_filter in self.pre_store_filter:
            tile = img_filter(tile)
        data = tile.source.as_buffer(format=self.file_ext, seekable=True)
        data.seek(0)
        with open(location, 'wb') as f:
            log.debug('writing %r to %s' % (tile.coord, location))
            f.write(data.read())
        tile.size = data.tell()
        tile.timestamp = time.time()
        data.seek(0)
        # tile.source = ImageSource(data)
        tile.stored = True
    
    def lock_filename(self, tile):
        if self._lock_cache_id is None:
            md5 = hashlib.md5()
            md5.update(self.cache_dir)
            self._lock_cache_id = md5.hexdigest()
        return os.path.join(self.lock_dir, self._lock_cache_id + '-' +
                            '-'.join(map(str, tile.coord)) + '.lck')
        
    def lock(self, tile):
        """
        Returns a lock object for this tile.
        """
        lock_filename = self.lock_filename(tile)
        cleanup_lockdir(self.lock_dir, force=False)
        return FileLock(lock_filename, timeout=base_config().http.client_timeout,
            remove_on_unlock=True)
    
    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.cache_dir, self.file_ext)


class DummyCache(object):
    def is_cached(self, tile):
        return False
    
    def lock(self, tile):
        return DummyLock()
    
    def store(self, tile):
        pass

def _create_dir(file_name):
    dir_name = os.path.dirname(file_name)
    if not os.path.exists(dir_name):
        try:
            os.makedirs(dir_name)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise e
