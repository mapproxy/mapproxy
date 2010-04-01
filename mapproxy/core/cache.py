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

"""
Tile caching (creation, caching and retrieval of tiles).

.. classtree:: mapproxy.core.cache.CacheManager
.. classtree:: mapproxy.core.cache._TileCreator
.. classtree:: mapproxy.core.cache.TileSource

.. digraph:: Schematic Call Graph
    
    ranksep = 0.1;
    node [shape="box", height="0", width="0"] 

    tcache  [label="Cache",         href="<Cache>"];
    cm      [label="CacheManager",  href="<CacheManager>"];
    tc      [label="tile_creator_func", href="<_TileCreator>"];
    ts      [label="TileSource",    href="<TileSource>"];
    c       [label="Cache",         href="<Cache>"];

    {
        tcache -> cm [label="load_tile_coords"];
        cm -> tc [label="call"];
        tc -> cm  [label="is_cached"];
        cm -> c  [label="load\\nstore\\nis_cached"];
        tc -> ts [label="create_tiles"];
    }
    

"""

from __future__ import with_statement
import os
import time
import errno
import hashlib
from functools import partial

from mapproxy.core.utils import FileLock, cleanup_lockdir, ThreadedExecutor
from mapproxy.core.image import TiledImage, ImageSource
from mapproxy.core.config import base_config, abspath

import logging
log = logging.getLogger(__name__)



class TileCacheError(Exception):
    pass
class TileSourceError(TileCacheError):
    pass
class TooManyTilesError(TileCacheError):
    pass

class Cache(object):
    """
    Easy access to images from cached tiles.
    """
    def __init__(self, cache_mgr, grid, transparent=False):
        """
        :param cache_mgr: the cache manager
        :param grid: the grid of the tile cache
        """
        self.cache_mgr = cache_mgr
        self.grid = grid
        self.transparent = transparent
    
    def tile(self, tile_coord):
        """
        Return a single tile.
        
        :return: loaded tile or ``None``
        :rtype: `ImageSource` or ``None``
        """
        tiles = self.cache_mgr.load_tile_coords([tile_coord], with_metadata=True)
        if len(tiles) < 1:
            return None
        else:
            return tiles[0]
    
    def _tiles(self, tile_coords):
        return self.cache_mgr.load_tile_coords(tile_coords)
        
    
    def _tiled_image(self, req_bbox, req_srs, out_size):
        """
        Return a `TiledImage` with all tiles that are within the requested bbox,
        for the given out_size.
        
        :note: The parameters are just hints for the tile cache to load the right
               tiles. Usually the bbox and the size of the result is larger.
               The result will always be in the native srs of the cache.
               See `Cache.image`.
        
        :param req_bbox: the requested bbox
        :param req_srs: the srs of the req_bbox
        :param out_size: the target output size
        :rtype: `ImageSource`
        """
        src_bbox, tile_grid, affected_tile_coords = \
            self.grid.get_affected_tiles(req_bbox, out_size, req_srs=req_srs)
        
        num_tiles = tile_grid[0] * tile_grid[1]
        if num_tiles >= base_config().cache.max_tile_limit:
            raise TooManyTilesError()

        tile_sources = [tile.source for tile in self._tiles(affected_tile_coords)]
        return TiledImage(tile_sources, src_bbox=src_bbox, src_srs=self.grid.srs,
                          tile_grid=tile_grid, tile_size=self.grid.tile_size,
                          transparent=self.transparent)
    
    def image(self, req_bbox, req_srs, out_size):
        """
        Return an image with the given bbox and size.
        The result will be cropped/transformed if needed.
        
        :param req_bbox: the requested bbox
        :param req_srs: the srs of the req_bbox
        :param out_size: the output size
        :rtype: `ImageSource`
        """
        tiled_image = self._tiled_image(req_bbox, req_srs, out_size)
        return tiled_image.transform(req_bbox, req_srs, out_size)
    
    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.cache_mgr, self.grid)

class TileCollection(object):
    def __init__(self, tile_coords):
        self.tiles = [_Tile(coord) for coord in tile_coords]
        self.tiles_dict = {}
        for tile in self.tiles:
            self.tiles_dict[tile.coord] = tile
    
    def __getitem__(self, idx_or_coord):
        if isinstance(idx_or_coord, int):
            return self.tiles[idx_or_coord]
        if idx_or_coord in self.tiles_dict:
            return self.tiles_dict[idx_or_coord]
        return _Tile(idx_or_coord)
    
    def __len__(self):
        return len(self.tiles)
    
    def __iter__(self):
        return iter(self.tiles)
    
    def __call__(self, coord):
        return self[coord]

class CacheManager(object):
    """
    Manages tile cache and tile creation.
    """
    def __init__(self, cache, tile_source, tile_creator):
        self.cache = cache
        self.tile_source = tile_source
        self.tile_creator = tile_creator
        
    def is_cached(self, tile):
        """
        Return True if the tile is cached.
        """
        max_mtime = self.expire_timestamp(tile)
        cached = self.cache.is_cached(tile)
        if cached and max_mtime is not None:
            stale = self.cache.timestamp_created(tile) < max_mtime
            if stale:
                cached = False
        return cached
    
    def expire_timestamp(self, tile=None):
        """
        Return the timestamp until which a tile should be accepted as up-to-date,
        or ``None`` if the tiles should not expire.
        
        :note: Returns ``None`` by default. Overwrite/change method to enable
            expiration.
        """
        return None
    
    def load_tile_coords(self, tile_coords, with_metadata=False):
        """
        Load all given tiles from cache. If they are not present, load them.
        
        :param tile_coords: list with tile coordinates (``None`` for out of bounds tiles)
        :return: list with `ImageSource` for all tiles (``None`` for out of bounds tiles)
        """
        tiles = TileCollection(tile_coords)
        self._load_tiles(tiles, with_metadata=with_metadata)
        
        return tiles
    
    def _load_tiles(self, tiles, with_metadata=False):
        """
        Return the given `tiles` with the `_Tile.source` set. If a tile is not cached,
        it will be created.
        """
        self._load_cached_tiles(tiles, with_metadata=with_metadata)
        self._create_tiles(tiles, with_metadata=with_metadata)
    
    def _create_tiles(self, tiles, with_metadata=False):
        """
        Create the tile data for all missing tiles. All created tiles will be added
        to the cache.
        
        :return: True if new tiles were created.
        """
        new_tiles = [tile for tile in tiles if tile.is_missing()]
        if new_tiles:
            created_tiles = self.tile_creator(new_tiles, tiles,
                                              self.tile_source, self)
            
            # load tile that were not created (e.g tiles created by another process)
            not_created = set(new_tiles).difference(created_tiles)
            if not_created:
                self._load_cached_tiles(not_created, with_metadata=with_metadata)
    
    def _load_cached_tiles(self, tiles, with_metadata=False):
        """
        Set the `_Tile.source` for all cached tiles.
        """
        for tile in tiles:
            if tile.is_missing() and self.is_cached(tile):
                self.cache.load(tile, with_metadata=with_metadata)
    def store_tiles(self, tiles):
        """
        Store the given tiles in the underlying cache.
        """
        for tile in tiles:
            self.cache.store(tile)
    
    def __repr__(self):
        return '%s(%r, %r, %r)' % (self.__class__.__name__, self.cache, self.tile_source,
                                   self.tile_creator)
    

class FileCache(object):
    """
    This class is responsible to store and load the actual tile data.
    """
    def __init__(self, cache_dir, file_ext, pre_store_filter=None):
        """
        :param cache_dir: the path where the tile will be stored
        :param file_ext: the file extension that will be appended to
            each tile (e.g. 'png')
        :param pre_store_filter: a list with filter. each filter will be called
            with a tile before it will be stored to disc. the filter should 
            return this or a new tile object.
        """
        self.cache_dir = cache_dir
        self.file_ext = file_ext
        if pre_store_filter is None:
            pre_store_filter = []
        self.pre_store_filter = pre_store_filter
    
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
         
        >>> c = FileCache(cache_dir='/tmp/cache/', file_ext='png')
        >>> c.tile_location(_Tile((3, 4, 2))).replace('\\\\', '/')
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
    
    def timestamp_created(self, tile):
        """
        Return the timestamp of the last modification of the tile.
        """
        self._update_tile_metadata(tile)
        return tile.timestamp
    
    def _update_tile_metadata(self, tile):
        location = self.tile_location(tile)
        stats = os.stat(tile.location)
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
        Fills the `_Tile.source` of the `tile` if it is cached.
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
        
    def store(self, tile):
        """
        Add the given `tile` to the file cache. Stores the `_Tile.source` to
        `FileCache.tile_location`.
        
        All ``pre_store_filter`` will be called with the tile, before
        it will be stored.
        """
        if tile.stored:
            return
        tile_loc = self.tile_location(tile, create_dir=True)
        for img_filter in self.pre_store_filter:
            tile = img_filter(tile)
        data = tile.source.as_buffer()
        with open(tile_loc, 'wb') as f:
            log.debug('writing %r to %s' % (tile.coord, tile_loc))
            f.write(data.read())
        tile.size = data.tell()
        tile.timestamp = time.time()
        data.seek(0)
        tile.stored = True

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.cache_dir, self.file_ext)

def _create_dir(file_name):
    dir_name = os.path.dirname(file_name)
    if not os.path.exists(dir_name):
        try:
            os.makedirs(dir_name)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise e            
    

class _TileCreator(object):
    """
    Base class for the creation of new tiles.
    Subclasses can implement different strategies how multiple tiles should
    be created (e.g. threaded).
    """
    def __init__(self, tile_source, cache):
        self.tile_source = tile_source
        self.cache = cache
    def create_tiles(self, tiles):
        """
        Create the given tiles (`_Tile.source` will be set). Returns a list with all
        created tiles.
        
        :note: The returned list may contain more tiles than requested. This allows
               the `TileSource` to create multiple tiles in one pass. 
        """
        raise NotImplementedError()
    
    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.tile_source, self.cache)


class _SequentialTileCreator(_TileCreator):
    """
    This `_TileCreator` creates one requested tile after the other.
    """
    def create_tiles(self, tiles, tile_collection):
        created_tiles = []
        for tile in tiles:
            with self.tile_source.tile_lock(tile):
                if not self.cache.is_cached(tile):
                    new_tiles = self.tile_source.create_tile(tile, tile_collection)
                    self.cache.store_tiles(new_tiles)
                    created_tiles.extend(new_tiles)
        cleanup_lockdir(self.tile_source.lock_dir)
        return created_tiles

def sequential_tile_creator(tiles, tile_collection, tile_source, cache):
    """
    This tile creator creates a thread pool to create multiple tiles in parallel.
    """
    return _SequentialTileCreator(tile_source, cache).create_tiles(tiles, tile_collection)

class _ThreadedTileCreator(_TileCreator):
    """
    This `_TileCreator` creates one requested tile after the other.
    """
    def create_tiles(self, tiles, tile_collection):
        unique_meta_tiles, _ = self._sort_tiles(tiles)
        if len(unique_meta_tiles) == 1: # don't start thread pool for one tile
            new_tiles = self._create_tile(unique_meta_tiles[0], tile_collection)
            if new_tiles is None:
                return []
            return new_tiles
        else:
            return self._create_multiple_tiles(unique_meta_tiles, tile_collection)
    
    def _create_multiple_tiles(self, tiles, tile_collection):
        pool_size = base_config().tile_creator_pool_size
        pool = ThreadedExecutor(partial(self._create_tile, 
                                        tile_collection=tile_collection), 
                                pool_size=pool_size)
        new_tiles = pool.execute(tiles)
        result = []
        for value in new_tiles:
            if value is not None:
                result.extend(value)
        
        cleanup_lockdir(self.tile_source.lock_dir)
        return result
    
    def _create_tile(self, tile, tile_collection):
        with self.tile_source.tile_lock(tile):
            if not self.cache.is_cached(tile):
                new_tiles = self.tile_source.create_tile(tile, tile_collection)
                self.cache.store_tiles(new_tiles)
                return new_tiles
    
    def _sort_tiles(self, tiles):
        unique_meta_tiles = {}
        other_tiles = []
    
        for tile in tiles:
            lock_name = self.tile_source.lock_filename(tile)
            if lock_name in unique_meta_tiles:
                other_tiles.append(tile)
            else:
                unique_meta_tiles[lock_name] = tile
        
        return unique_meta_tiles.values(), other_tiles
    
def threaded_tile_creator(tiles, tile_collection, tile_source, cache):
    """
    This tile creator creates a thread pool to create multiple tiles in parallel.
    """
    return _ThreadedTileCreator(tile_source, cache).create_tiles(tiles, tile_collection)


class TileSource(object):
    """
    Base class for tile sources.
    A ``TileSource`` knows how to get the `_Tile.source` for a given tile.
    """
    def __init__(self, lock_dir=None):
        if lock_dir is None:
            lock_dir = abspath(base_config().cache.lock_dir)
        self.lock_dir = lock_dir
        self._id = None
        
    def id(self):
        """
        Returns a unique but constant id of this TileSource used for locking.
        """
        raise NotImplementedError
    
    def tile_lock(self, tile):
        """
        Returns a lock object for the given tile.
        """
        lock_file = self.lock_filename(tile)
        return FileLock(lock_file)
    
    def lock_filename(self, tile):
        if self._id is None:
            md5 = hashlib.md5()
            md5.update(str(self.id()))
            self._id = md5.hexdigest()
        return os.path.join(self.lock_dir, self._id + '-' +
                                           '-'.join(map(str, tile.coord)) + '.lck')
    
    def create_tile(self, tile, tile_map):
        """
        Create the given tile and set the `_Tile.source`. It doesn't store the data on
        disk (or else where), this is up to the cache manager.
        
        :note: This method may return multiple tiles, if it is more effective for the
               ``TileSource`` to create multiple tiles in one pass.
        :rtype: list of ``Tiles``
        
        """
        raise NotImplementedError()
    
    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__)


class _Tile(object):
    """
    Internal data object for all tiles. Stores the tile-``coord`` and the tile data.
    
    :ivar source: the data of this tile
    :type source: ImageSource
    """
    def __init__(self, coord, source=None):
        self.coord = coord
        self.source = source
        self.location = None
        self.stored = False
        self.size = None
        self.timestamp = None
    
    def source_buffer(self, *args, **kw):
        if self.source is not None:
            return self.source.as_buffer(*args, **kw)
        else:
            return None
    
    def source_image(self, *args, **kw):
        if self.source is not None:
            return self.source.as_image(*args, **kw)
        else:
            return None
    
    def is_missing(self):
        """
        Returns ``True`` when the tile has no ``data``, except when the ``coord``
        is ``None``. It doesn't check if the tile exists.
        
        >>> _Tile((1, 2, 3)).is_missing()
        True
        >>> _Tile((1, 2, 3), './tmp/foo').is_missing()
        False
        >>> _Tile(None).is_missing()
        False
        """
        if self.coord is None:
            return False
        return self.source is None
    
    def __eq__(self, other):
        """
        >>> _Tile((0, 0, 1)) == _Tile((0, 0, 1))
        True
        >>> _Tile((0, 0, 1)) == _Tile((1, 0, 1))
        False
        >>> _Tile((0, 0, 1)) == None
        False
        """
        if isinstance(other, _Tile):
            return  (self.coord == other.coord and
                     self.source == other.source)
        else:
            return NotImplemented
    def __ne__(self, other):
        """
        >>> _Tile((0, 0, 1)) != _Tile((0, 0, 1))
        False
        >>> _Tile((0, 0, 1)) != _Tile((1, 0, 1))
        True
        >>> _Tile((0, 0, 1)) != None
        True
        """
        equal_result = self.__eq__(other)
        if equal_result is NotImplemented:
            return NotImplemented
        else:
            return not equal_result
    
    def __repr__(self):
        return '_Tile(%r, source=%r)' % (self.coord, self.source)