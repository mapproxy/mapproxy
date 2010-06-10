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

.. digraph:: Schematic Call Graph
    
    ranksep = 0.1;
    node [shape="box", height="0", width="0"] 
    
    cl  [label="CacheMapLayer" href="<mapproxy.core.layer.CacheMapLayer>"]
    tm  [label="TileManager",  href="<TileManager>"];
    fc      [label="FileCache", href="<FileCache>"];
    s       [label="Source", href="<mapproxy.core.source.Source>"];

    {
        cl -> tm [label="load_tile_coords"];
        tm -> fc [label="load\\nstore\\nis_cached"];
        tm -> s  [label="get_map"]
    }
    

"""

from __future__ import with_statement
import os
import sys
import time
import errno
import hashlib

from mapproxy.core.utils import FileLock
from mapproxy.core.image import ImageSource, is_single_color_image, TileSplitter
from mapproxy.core.config import base_config
from mapproxy.core.srs import SRS
from mapproxy.core.grid import MetaGrid


import logging
log = logging.getLogger(__name__)

class BlankImage(Exception):
    pass
class TileCacheError(Exception):
    pass

#TODO rename to something like SourceError
class TileSourceError(TileCacheError):
    pass
class TooManyTilesError(TileCacheError):
    pass

class TileCollection(object):
    def __init__(self, tile_coords):
        self.tiles = [Tile(coord) for coord in tile_coords]
        self.tiles_dict = {}
        for tile in self.tiles:
            self.tiles_dict[tile.coord] = tile
    
    def __getitem__(self, idx_or_coord):
        if isinstance(idx_or_coord, int):
            return self.tiles[idx_or_coord]
        if idx_or_coord in self.tiles_dict:
            return self.tiles_dict[idx_or_coord]
        return Tile(idx_or_coord)
    
    def __contains__(self, tile_or_coord):
        if isinstance(tile_or_coord, tuple):
            return tile_or_coord in self.tiles_dict
        if hasattr(tile_or_coord, 'coord'):
            return tile_or_coord.coord in self.tiles_dict
        return False
    
    def __len__(self):
        return len(self.tiles)
    
    def __iter__(self):
        return iter(self.tiles)

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
        data = tile.source.as_buffer()
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
        return FileLock(lock_filename, timeout=base_config().http_client_timeout)
    
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
    

class TileManager(object):
    def __init__(self, grid, cache, sources, format,
        meta_buffer=None, meta_size=None):
        self.grid = grid
        self.cache = cache
        self.meta_grid = None
        self.format = format
        assert len(sources) == 1
        self.sources = sources
        self._expire_timestamp = None
        self.transparent = self.sources[0].transparent
        
        if meta_buffer is not None and meta_size and \
            any(source.supports_meta_tiles for source in sources):
            self.meta_grid = MetaGrid(grid, meta_size=meta_size, meta_buffer=meta_buffer)
    
    def load_tile_coord(self, tile_coord, with_metadata=False):
        return self.load_tile_coords([tile_coord], with_metadata)[0]
    
    def load_tile_coords(self, tile_coords, with_metadata=False):
        tiles = TileCollection(tile_coords)
        uncached_tiles = []
        
        for tile in tiles:
            # TODO cache eviction
            if self.cache.is_cached(tile):
                self.cache.load(tile, with_metadata)
            else:
                uncached_tiles.append(tile)
        
        if uncached_tiles:
            created_tiles = self._create_tiles(uncached_tiles)
            for created_tile in created_tiles:
                if created_tile.coord in tiles:
                    tiles[created_tile.coord].source = created_tile.source
        
        return tiles
    
    def lock(self, tile):
        if self.meta_grid:
            tile = Tile(self.meta_grid.tiles(tile.coord).next()[0])
        return self.cache.lock(tile)
    
    def is_cached(self, tile):
        """
        Return True if the tile is cached.
        """
        if isinstance(tile, tuple):
            tile = Tile(tile)
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
        
        :note: Returns _expire_timestamp by default.
        """
        return self._expire_timestamp
    
    def _create_tiles(self, tiles):
        created_tiles = []
        if not self.meta_grid:
            for tile in tiles:
                created_tiles.append(self._create_tile(tile))
        else:
            meta_tiles = []
            meta_bboxes = set()
            for tile in tiles:
                meta_bbox = self.meta_grid.meta_bbox(tile.coord)
                if meta_bbox not in meta_bboxes:
                    meta_tiles.append((tile, meta_bbox))
                    meta_bboxes.add(meta_bbox)
            
            created_tiles = self._create_meta_tiles(meta_tiles)
        
        return created_tiles
            
    def _create_tile(self, tile):
        assert len(self.sources) == 1
        tile_bbox = self.grid.tile_bbox(tile.coord)
        query = MapQuery(tile_bbox, self.grid.tile_size, self.grid.srs, self.format)
        with self.lock(tile):
            if not self.cache.is_cached(tile):
                tile.source = self.sources[0].get_map(query)
                self.cache.store(tile)
            else:
                self.cache.load(tile)
        return tile
    
    def _create_meta_tiles(self, meta_tiles):
        assert len(self.sources) == 1
        created_tiles = []
        for tile, meta_bbox in meta_tiles:
            tiles = list(self.meta_grid.tiles(tile.coord))
            created_tiles.extend(self._create_meta_tile(tile, meta_bbox, tiles))
        return created_tiles
    
    def _create_meta_tile(self, main_tile, meta_bbox, tiles):
        meta_tile_size = self.meta_grid.tile_size(main_tile.coord[2])
        tile_size = self.grid.tile_size
        query = MapQuery(meta_bbox, meta_tile_size, self.grid.srs, self.format)
        with self.lock(main_tile):
            if not self.cache.is_cached(main_tile):
                meta_tile = self.sources[0].get_map(query)
                splitted_tiles = split_meta_tiles(meta_tile, tiles, tile_size)
                for splitted_tile in splitted_tiles:
                    self.cache.store(splitted_tile)
                return splitted_tiles
        # else
        tiles = [Tile(coord) for coord, pos in tiles]
        for tile in tiles:
            self.cache.load(tile)
        return tiles
        
class Tile(object):
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
        
        >>> Tile((1, 2, 3)).is_missing()
        True
        >>> Tile((1, 2, 3), './tmp/foo').is_missing()
        False
        >>> Tile(None).is_missing()
        False
        """
        if self.coord is None:
            return False
        return self.source is None
    
    def __eq__(self, other):
        """
        >>> Tile((0, 0, 1)) == Tile((0, 0, 1))
        True
        >>> Tile((0, 0, 1)) == Tile((1, 0, 1))
        False
        >>> Tile((0, 0, 1)) == None
        False
        """
        if isinstance(other, Tile):
            return  (self.coord == other.coord and
                     self.source == other.source)
        else:
            return NotImplemented
    def __ne__(self, other):
        """
        >>> Tile((0, 0, 1)) != Tile((0, 0, 1))
        False
        >>> Tile((0, 0, 1)) != Tile((1, 0, 1))
        True
        >>> Tile((0, 0, 1)) != None
        True
        """
        equal_result = self.__eq__(other)
        if equal_result is NotImplemented:
            return NotImplemented
        else:
            return not equal_result
    
    def __repr__(self):
        return 'Tile(%r, source=%r)' % (self.coord, self.source)

def map_extend_from_grid(grid):
    """
    >>> from mapproxy.core.grid import tile_grid_for_epsg
    >>> map_extend_from_grid(tile_grid_for_epsg('EPSG:900913')) 
    ... #doctest: +NORMALIZE_WHITESPACE
    MapExtend((-20037508.342789244, -20037508.342789244,
               20037508.342789244, 20037508.342789244), SRS('EPSG:900913'))
    """
    return MapExtend(grid.bbox, grid.srs)

class MapExtend(object):
    """
    >>> me = MapExtend((5, 45, 15, 55), SRS(4326))
    >>> me.llbbox
    (5, 45, 15, 55)
    >>> map(int, me.bbox_for(SRS(900913)))
    [556597, 5621521, 1669792, 7361866]
    >>> map(int, me.bbox_for(SRS(4326)))
    [5, 45, 15, 55]
    """
    def __init__(self, bbox, srs):
        self.llbbox = srs.transform_bbox_to(SRS(4326), bbox)
        self.bbox = bbox
        self.srs = srs
    
    def bbox_for(self, srs):
        if srs == self.srs:
            return self.bbox
        
        return self.srs.transform_bbox_to(srs, self.bbox)
    
    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.bbox, self.srs)

class MapQuery(object):
    """
    Internal query for a map with a specific extend, size, srs, etc.
    """
    def __init__(self, bbox, size, srs, format=None, transparent=False):
        self.bbox = bbox
        self.size = size
        self.srs = srs
        self.format = format
        self.transparent = transparent
        

class InfoQuery(object):
    def __init__(self, bbox, size, srs, pos, info_format):
        self.bbox = bbox
        self.size = size
        self.srs = srs
        self.pos = pos
        self.info_format = info_format


def split_meta_tiles(meta_tile, tiles, tile_size):
    try:
        # TODO png8
        # if not self.transparent and format == 'png':
        #     format = 'png8'
        splitter = TileSplitter(meta_tile)
    except IOError:
        # TODO
        raise
    split_tiles = []
    for tile in tiles:
        tile_coord, crop_coord = tile
        data = splitter.get_tile(crop_coord, tile_size)
        new_tile = Tile(tile_coord)
        new_tile.source = data
        split_tiles.append(new_tile)
    return split_tiles

class InvalidSourceQuery(ValueError):
    pass


