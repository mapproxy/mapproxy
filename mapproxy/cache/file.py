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
import errno
import hashlib

from mapproxy.cache.tile import Tile
from mapproxy.util.fs import ensure_directory, write_atomic
from mapproxy.image import ImageSource, is_single_color_image
from mapproxy.cache import path
from mapproxy.cache.base import TileCacheBase, tile_buffer

import logging
log = logging.getLogger('mapproxy.cache.file')


class FileCache(TileCacheBase):
    """
    This class is responsible to store and load the actual tile data.
    """
    supports_dimensions = True

    def __init__(self, cache_dir, file_ext, directory_layout='tc',
                 link_single_color_images=False, coverage=None, image_opts=None,
                 directory_permissions=None, file_permissions=None):
        """
        :param cache_dir: the path where the tile will be stored
        :param file_ext: the file extension that will be appended to
            each tile (e.g. 'png')
        """
        super(FileCache, self).__init__(coverage)
        md5 = hashlib.new('md5', cache_dir.encode('utf-8'), usedforsecurity=False)
        self.lock_cache_id = md5.hexdigest()
        self.cache_dir = cache_dir
        self.file_ext = file_ext
        self.image_opts = image_opts
        self.link_single_color_images = link_single_color_images
        self.directory_permissions = directory_permissions
        self.file_permissions = file_permissions
        self._tile_location, self._level_location = path.location_funcs(layout=directory_layout)
        if self._level_location is None:
            self.level_location = None  # disable level based clean-ups

    def tile_location(self, tile, create_dir=False, dimensions=None):
        if dimensions is not None and len(dimensions) > 0:
            items = list(dimensions.keys())
            items.sort()
            dimensions_str = ['{key}-{value}'.format(key=i, value=dimensions[i].replace('/', '_')) for i in items]
            # todo: cache_dir is not used. should it get returned or removed?
            cache_dir = os.path.join(self.cache_dir, '_'.join(dimensions_str))  # noqa
        return self._tile_location(tile, self.cache_dir, self.file_ext, create_dir=create_dir, dimensions=dimensions,
                                   directory_permissions=self.directory_permissions)

    def level_location(self, level, dimensions=None):
        """
        Return the path where all tiles for `level` will be stored.

        >>> c = FileCache(cache_dir='/tmp/cache/', file_ext='png')
        >>> c.level_location(2)
        '/tmp/cache/02'
        """
        return self._level_location(level, self.cache_dir, dimensions)

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
            ensure_directory(location, self.directory_permissions)
        return location

    def load_tile_metadata(self, tile, dimensions=None):
        location = self.tile_location(tile, dimensions=dimensions)
        try:
            stats = os.lstat(location)
            tile.timestamp = stats.st_mtime
            tile.size = stats.st_size
        except OSError as ex:
            if ex.errno != errno.ENOENT:
                raise
            tile.timestamp = 0
            tile.size = 0

    def is_cached(self, tile, dimensions=None):
        """
        Returns ``True`` if the tile data is present.
        """
        if tile.is_missing():
            location = self.tile_location(tile, dimensions=dimensions)
            if os.path.exists(location):
                return True
            else:
                return False
        else:
            return True

    def load_tile(self, tile: Tile, with_metadata=False, dimensions=None) -> bool:
        """
        Fills the `Tile.source` of the `tile` if it is cached.
        If it is not cached or if the ``.coord`` is ``None``, nothing happens.
        """
        if not tile.is_missing():
            return True

        location = self.tile_location(tile, dimensions=dimensions)

        if os.path.exists(location):
            if with_metadata:
                self.load_tile_metadata(tile, dimensions=dimensions)
            tile.source = ImageSource(location, image_opts=self.image_opts)
            return True
        return False

    def remove_tile(self, tile: Tile, dimensions=None):
        location = self.tile_location(tile, dimensions=dimensions)
        try:
            os.remove(location)
        except OSError as ex:
            if ex.errno != errno.ENOENT:
                raise

    def store_tile(self, tile: Tile, dimensions=None):
        """
        Add the given `tile` to the file cache. Stores the `Tile.source` to
        `FileCache.tile_location`.
        """
        if tile.stored:
            return

        tile_loc = self.tile_location(tile, create_dir=True, dimensions=dimensions)

        if self.link_single_color_images:
            assert tile.source is not None
            color = is_single_color_image(tile.source.as_image())
            if color:
                self._store_single_color_tile(tile, tile_loc, color)
            else:
                self._store(tile, tile_loc)
        else:
            self._store(tile, tile_loc)

    def _store(self, tile: Tile, location):
        if os.path.islink(location):
            os.unlink(location)

        with tile_buffer(tile) as buf:
            log.debug('writing %r to %s' % (tile.coord, location))
            write_atomic(location, buf.read())
            if self.file_permissions:
                permission = int(self.file_permissions, base=8)
                os.chmod(location, permission)

    def _store_single_color_tile(self, tile: Tile, tile_loc, color):
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

        if self.link_single_color_images == 'hardlink':
            try:
                os.link(real_tile_loc, tile_loc)
            except OSError as e:
                # ignore error if link was created by other process
                if e.errno != errno.EEXIST:
                    raise e
        else:
            # Use relative path for the symlink
            real_tile_loc = os.path.relpath(real_tile_loc, os.path.dirname(tile_loc))

            try:
                os.symlink(real_tile_loc, tile_loc)
            except OSError as e:
                # ignore error if link was created by other process
                if e.errno != errno.EEXIST:
                    raise e

        return

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.cache_dir, self.file_ext)
