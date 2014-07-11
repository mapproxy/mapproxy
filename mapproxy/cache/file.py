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

from __future__ import with_statement
import os
import errno
import hashlib

from mapproxy.util.fs import ensure_directory, write_atomic
from mapproxy.image import ImageSource, is_single_color_image
from mapproxy.cache.base import TileCacheBase, tile_buffer
from mapproxy.compat import string_type

import logging
log = logging.getLogger('mapproxy.cache.file')

class FileCache(TileCacheBase):
    """
    This class is responsible to store and load the actual tile data.
    """
    def __init__(self, cache_dir, file_ext, lock_dir=None, directory_layout='tc',
                 link_single_color_images=False, lock_timeout=60.0):
        """
        :param cache_dir: the path where the tile will be stored
        :param file_ext: the file extension that will be appended to
            each tile (e.g. 'png')
        """
        super(FileCache, self).__init__()
        self.lock_cache_id = hashlib.md5(cache_dir.encode('utf-8')).hexdigest()
        self.cache_dir = cache_dir
        self.file_ext = file_ext
        self.link_single_color_images = link_single_color_images

        if directory_layout == 'tc':
            self.tile_location = self._tile_location_tc
        elif directory_layout == 'tms':
            self.tile_location = self._tile_location_tms
        elif directory_layout == 'quadkey':
            self.tile_location = self._tile_location_quadkey
        else:
            raise ValueError('unknown directory_layout "%s"' % directory_layout)

    def level_location(self, level):
        """
        Return the path where all tiles for `level` will be stored.

        >>> c = FileCache(cache_dir='/tmp/cache/', file_ext='png')
        >>> c.level_location(2)
        '/tmp/cache/02'
        """
        if isinstance(level, string_type):
            return os.path.join(self.cache_dir, level)
        else:
            return os.path.join(self.cache_dir, "%02d" % level)

    def _tile_location_tc(self, tile, create_dir=False):
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
            ensure_directory(tile.location)
        return tile.location

    def _tile_location_tms(self, tile, create_dir=False):
        """
        Return the location of the `tile`. Caches the result as ``location``
        property of the `tile`.

        :param tile: the tile object
        :param create_dir: if True, create all necessary directories
        :return: the full filename of the tile

        >>> from mapproxy.cache.tile import Tile
        >>> c = FileCache(cache_dir='/tmp/cache/', file_ext='png', directory_layout='tms')
        >>> c.tile_location(Tile((3, 4, 2))).replace('\\\\', '/')
        '/tmp/cache/2/3/4.png'
        """
        if tile.location is None:
            x, y, z = tile.coord
            tile.location = os.path.join(
                self.level_location(str(z)),
                str(x), str(y) + '.' + self.file_ext
            )
        if create_dir:
            ensure_directory(tile.location)
        return tile.location

    def _tile_location_quadkey(self, tile, create_dir=False):
        """
        Return the location of the `tile`. Caches the result as ``location``
        property of the `tile`.

        :param tile: the tile object
        :param create_dir: if True, create all necessary directories
        :return: the full filename of the tile

        >>> from mapproxy.cache.tile import Tile
        >>> from mapproxy.cache.file import FileCache
        >>> c = FileCache(cache_dir='/tmp/cache/', file_ext='png', directory_layout='quadkey')
        >>> c.tile_location(Tile((3, 4, 2))).replace('\\\\', '/')
        '/tmp/cache/11.png'
        """
        if tile.location is None:
            x, y, z = tile.coord
            quadKey = ""
            for i in range(z,0,-1):
                digit = 0
                mask = 1 << (i-1)
                if (x & mask) != 0:
                    digit += 1
                if (y & mask) != 0:
                    digit += 2
                quadKey += str(digit)
            tile.location = os.path.join(
                self.cache_dir, quadKey + '.' + self.file_ext
            )
        if create_dir:
            ensure_directory(tile.location)
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
            ensure_directory(location)
        return location

    def load_tile_metadata(self, tile):
        location = self.tile_location(tile)
        try:
            stats = os.lstat(location)
            tile.timestamp = stats.st_mtime
            tile.size = stats.st_size
        except OSError as ex:
            if ex.errno != errno.ENOENT: raise
            tile.timestamp = 0
            tile.size = 0

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

    def load_tile(self, tile, with_metadata=False):
        """
        Fills the `Tile.source` of the `tile` if it is cached.
        If it is not cached or if the ``.coord`` is ``None``, nothing happens.
        """
        if not tile.is_missing():
            return True

        location = self.tile_location(tile)

        if os.path.exists(location):
            if with_metadata:
                self.load_tile_metadata(tile)
            tile.source = ImageSource(location)
            return True
        return False

    def remove_tile(self, tile):
        location = self.tile_location(tile)
        try:
            os.remove(location)
        except OSError as ex:
            if ex.errno != errno.ENOENT: raise

    def store_tile(self, tile):
        """
        Add the given `tile` to the file cache. Stores the `Tile.source` to
        `FileCache.tile_location`.
        """
        if tile.stored:
            return

        tile_loc = self.tile_location(tile, create_dir=True)

        if self.link_single_color_images:
            color = is_single_color_image(tile.source.as_image())
            if color:
                self._store_single_color_tile(tile, tile_loc, color)
            else:
                self._store(tile, tile_loc)
        else:
            self._store(tile, tile_loc)

    def _store(self, tile, location):
        if os.path.islink(location):
            os.unlink(location)

        with tile_buffer(tile) as buf:
            log.debug('writing %r to %s' % (tile.coord, location))
            write_atomic(location, buf.read())

    def _store_single_color_tile(self, tile, tile_loc, color):
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

        # Use relative path for the symlink if os.path.relpath is available
        # (only supported with >= Python 2.6)
        if hasattr(os.path, 'relpath'):
            real_tile_loc = os.path.relpath(real_tile_loc,
                                            os.path.dirname(tile_loc))

        try:
            os.symlink(real_tile_loc, tile_loc)
        except OSError as e:
            # ignore error if link was created by other process
            if e.errno != errno.EEXIST:
                raise e

        return

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.cache_dir, self.file_ext)

