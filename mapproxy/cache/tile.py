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

from mapproxy.grid import MetaGrid
from mapproxy.image import merge_images
from mapproxy.image.tile import TileSplitter
from mapproxy.layer import MapQuery
from mapproxy.util import ThreadedExecutor
from mapproxy.config import base_config

import logging
log = logging.getLogger(__name__)


class TileManager(object):
    def __init__(self, grid, cache, sources, format, request_format=None,
        meta_buffer=None, meta_size=None):
        self.grid = grid
        self.cache = cache
        self.meta_grid = None
        self.format = format
        self.request_format = request_format or format
        self.sources = sources
        self._expire_timestamp = None
        self.transparent = self.sources[0].transparent
        self.thread_pool_size = base_config().cache.concurrent_tile_creators
        
        if meta_buffer is not None and meta_size:
            if all(source.supports_meta_tiles for source in sources):
                self.meta_grid = MetaGrid(grid, meta_size=meta_size, meta_buffer=meta_buffer)
            elif any(source.supports_meta_tiles for source in sources):
                raise ValueError('meta tiling configured but not supported by all sources')
    
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
        if not self.meta_grid:
            created_tiles = self._create_single_tiles(tiles)
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

    def _create_single_tiles(self, tiles):
        if self.thread_pool_size and len(tiles) > 1:
            return self._create_threaded(self._create_single_tile, tiles)
        
        created_tiles = []
        for tile in tiles:
            created_tiles.extend(self._create_single_tile(tile))
        return created_tiles
    
    def _create_threaded(self, create_func, tiles):
        pool = ThreadedExecutor(create_func, pool_size=self.thread_pool_size)
        result = []
        for new_tiles in pool.execute(tiles):
            result.extend(new_tiles)
        return result
    
    def _create_single_tile(self, tile):
        tile_bbox = self.grid.tile_bbox(tile.coord)
        query = MapQuery(tile_bbox, self.grid.tile_size, self.grid.srs,
                         self.request_format)
        with self.lock(tile):
            if not self.cache.is_cached(tile):
                tile.source = self._query_sources(query)
                self.cache.store(tile)
            else:
                self.cache.load(tile)
        return [tile]
    
    def _query_sources(self, query):
        """
        Query all sources and return the results as a single ImageSource.
        Multiple sources will be merged into a single image.
        """
        if len(self.sources) == 1:
            return self.sources[0].get_map(query)
        
        imgs = []
        for source in self.sources:
            imgs.append(source.get_map(query))
        
        return merge_images(imgs)
        
    
    def _create_meta_tiles(self, meta_tiles):
        if self.thread_pool_size and len(meta_tiles) > 1:
            args = []
            for tile, meta_bbox in meta_tiles:
                tiles = list(self.meta_grid.tiles(tile.coord))
                args.append((tile, meta_bbox, tiles))
            def create_func(args): # wrapper that unpacks args
                return self._create_meta_tile(*args)
            return self._create_threaded(create_func, args)
        
        created_tiles = []
        for tile, meta_bbox in meta_tiles:
            tiles = list(self.meta_grid.tiles(tile.coord))
            created_tiles.extend(self._create_meta_tile(tile, meta_bbox, tiles))
        return created_tiles
    
    def _create_meta_tile(self, main_tile, meta_bbox, tiles):
        meta_tile_size = self.meta_grid.tile_size(main_tile.coord[2])
        tile_size = self.grid.tile_size
        query = MapQuery(meta_bbox, meta_tile_size, self.grid.srs, self.request_format)
        with self.lock(main_tile):
            if not self.cache.is_cached(main_tile):
                meta_tile = self._query_sources(query)
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
