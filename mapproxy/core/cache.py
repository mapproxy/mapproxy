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
import sys
import time
import errno
import hashlib
from functools import partial

from mapproxy.core.utils import FileLock, cleanup_lockdir, ThreadedExecutor, reraise_exception
from mapproxy.core.image import TiledImage, ImageSource, is_single_color_image
from mapproxy.core.config import base_config, abspath
from mapproxy.core.grid import NoTiles
from mapproxy.core.srs import SRS

from mapproxy.core.grid import MetaGrid
from mapproxy.core.image import TileSplitter, ImageTransformer, message_image
from mapproxy.core.client import HTTPClient, HTTPClientError


import logging
log = logging.getLogger(__name__)

class BlankImage(Exception):
    pass
class TileCacheError(Exception):
    pass
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
    
    def __call__(self, coord):
        return self[coord]

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
    def __init__(self, grid, file_cache, sources, format,
        meta_buffer=None, meta_size=None):
        self.grid = grid
        self.file_cache = file_cache
        self.meta_grid = None
        self.format = format
        assert len(sources) == 1
        self.sources = sources
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
            if self.file_cache.is_cached(tile):
                self.file_cache.load(tile, with_metadata)
            else:
                uncached_tiles.append(tile)
        
        if uncached_tiles:
            created_tiles = self._create_tiles(uncached_tiles)
            for created_tile in created_tiles:
                if created_tile.coord in tiles:
                    tiles[created_tile.coord].source = created_tile.source
        
        return tiles
    
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
        with self.file_cache.lock(tile):
            if not self.file_cache.is_cached(tile):
                tile.source = self.sources[0].get_map(query)
                self.file_cache.store(tile)
            else:
                self.file_cache.load(tile)
        return tile
    
    def _create_meta_tiles(self, meta_tiles):
        assert len(self.sources) == 1
        created_tiles = []
        for tile, meta_bbox in meta_tiles:
            tiles = list(self.meta_grid.tiles(tile.coord))
            main_tile = Tile(tiles[0][0]) # use first tile of meta grid
            created_tiles.extend(self._create_meta_tile(main_tile, meta_bbox, tiles))
        return created_tiles
    
    def _create_meta_tile(self, main_tile, meta_bbox, tiles):
        tile_size = self.meta_grid.tile_size(main_tile.coord[2])
        query = MapQuery(meta_bbox, tile_size, self.grid.srs, self.format)
        with self.file_cache.lock(main_tile):
            if not self.file_cache.is_cached(main_tile):
                meta_tile = self.sources[0].get_map(query)
                splitted_tiles = split_meta_tiles(meta_tile, tiles, tile_size)
                for splitted_tile in splitted_tiles:
                    self.file_cache.store(splitted_tile)
                return splitted_tiles
        # else
        tiles = [Tile(coord) for coord, pos in tiles]
        for tile in tiles:
            self.file_cache.load(tile)
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
        self._bbox = bbox
        self._srs = srs
    
    def bbox_for(self, srs):
        if srs == self._srs:
            return self._bbox
        
        return self._srs.transform_bbox_to(srs, self._bbox)
    
    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self._bbox, self._srs)

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

class InfoLayer(object):
    def get_info(self, query):
        raise NotImplementedError

class MapLayer(object):
    def get_map(self, query):
        raise NotImplementedError

class ResolutionConditional(MapLayer):
    def __init__(self, one, two, resolution, srs, extend):
        self.one = one
        self.two = two
        self.resolution = resolution
        self.srs = srs
        
        #TODO
        self.transparent = self.one.transparent
        self.extend = extend
    
    def get_map(self, query):
        bbox = query.bbox
        if query.srs != self.srs:
            bbox = query.srs.transform_bbox_to(self.srs, bbox)
        
        xres = (bbox[2] - bbox[0]) / query.size[0]
        yres = (bbox[3] - bbox[1]) / query.size[1]
        res = min(xres, yres)
        print res, self.resolution
        
        if res > self.resolution:
            return self.one.get_map(query)
        else:
            return self.two.get_map(query)

class SRSConditional(MapLayer):
    PROJECTED = 'PROJECTED'
    GEOGRAPHIC = 'GEOGRAPHIC'
    
    def __init__(self, layers, extend, transparent=False):
        self.transparent = transparent
        # TODO geographic/projected fallback
        self.srs_map = {}
        for layer, srss in layers:
            for srs in srss:
                self.srs_map[srs] = layer
        
        self.extend = extend
    
    def get_map(self, query):
        layer = self._select_layer(query.srs)
        return layer.get_map(query)
    
    def _select_layer(self, query_srs):
        # srs exists
        if query_srs in self.srs_map:
            return self.srs_map[query_srs]
        
        # srs_type exists
        srs_type = self.GEOGRAPHIC if query_srs.is_latlong else self.PROJECTED
        if srs_type in self.srs_map:
            return self.srs_map[srs_type]
        
        # first with same type
        is_latlong = query_srs.is_latlong
        for srs in self.srs_map:
            if hasattr(srs, 'is_latlong') and srs.is_latlong == is_latlong:
                return self.srs_map[srs]
        
        # return first
        return self.srs_map.itervalues().next()
        

class DirectMapLayer(MapLayer):
    def __init__(self, source, extend):
        self.source = source
    
    def get_map(self, query):
        return self.source.get_map(query)


class DirectInfoLayer(InfoLayer):
    def __init__(self, source):
        self.source = source
    
    def get_info(self, query):
        return self.source.get_info(query)

class CacheMapLayer(MapLayer):
    def __init__(self, tile_manager, transparent=False):
        self.tile_manager = tile_manager
        self.grid = tile_manager.grid
        self.extend = map_extend_from_grid(self.grid)
        self.transparent = transparent
    
    def get_map(self, query):
        tiled_image = self._tiled_image(query.bbox, query.size, query.srs)
        return tiled_image.transform(query.bbox, query.srs, query.size)
    
    def _tiled_image(self, bbox, size, srs):
        try:
            src_bbox, tile_grid, affected_tile_coords = \
                self.grid.get_affected_tiles(bbox, size, req_srs=srs)
        except IndexError:
            raise TileCacheError('Invalid BBOX')
        except NoTiles:
            raise BlankImage()
        
        num_tiles = tile_grid[0] * tile_grid[1]
        if num_tiles >= base_config().cache.max_tile_limit:
            raise TooManyTilesError()
        
        tile_sources = [tile.source for tile in self.tile_manager.load_tile_coords(affected_tile_coords)]
        return TiledImage(tile_sources, src_bbox=src_bbox, src_srs=self.grid.srs,
                          tile_grid=tile_grid, tile_size=self.grid.tile_size,
                          transparent=self.transparent)
    

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

class Source(object):
    supports_meta_tiles = False
    transparent = False
    def get_map(self, query):
        raise NotImplementedError

class WMSClient(object):
    def __init__(self, request_template, supported_srs=None, http_client=None):
        self.request_template = request_template
        self.http_client = http_client or HTTPClient()
        self.supported_srs = set(supported_srs or [])
    
    def get_map(self, query):
        if self.supported_srs and query.srs not in self.supported_srs:
            return self._get_transformed(query)
        resp = self._retrieve(query)
        return ImageSource(resp, self.request_template.params.format)
    
    def _get_transformed(self, query):
        dst_srs = query.srs
        src_srs = self._best_supported_srs(dst_srs)
        dst_bbox = query.bbox
        src_bbox = dst_srs.transform_bbox_to(src_srs, dst_bbox)
        
        src_query = MapQuery(src_bbox, query.size, src_srs)
        resp = self._retrieve(src_query)
        
        img = ImageSource(resp, self.request_template.params.format, size=src_query.size)
        
        img = ImageTransformer(src_srs, dst_srs).transform(img, src_bbox, 
            query.size, dst_bbox)
        
        img.format = self.request_template.params.format
        return img
    
    def _best_supported_srs(self, srs):
        latlong = srs.is_latlong
        
        for srs in self.supported_srs:
            if srs.is_latlong == latlong:
                return srs
        
        return iter(self.supported_srs).next()
    def _retrieve(self, query):
        url = self._query_url(query)
        return self.http_client.open(url)
    
    def _query_url(self, query):
        req = self.request_template.copy()
        req.params.bbox = query.bbox
        req.params.size = query.size
        req.params.srs = query.srs.srs_code
        
        return req.complete_url


class WMSInfoClient(object):
    def __init__(self, request_template, supported_srs=None, http_client=None):
        self.request_template = request_template
        self.http_client = http_client or HTTPClient()
        self.supported_srs = set(supported_srs or [])
    
    def get_info(self, query):
        if self.supported_srs and query.srs not in self.supported_srs:
            return self._get_transformed(query)
        resp = self._retrieve(query)
        return resp
    
    def _get_transformed(self, query):
        req_srs = query.srs
        req_bbox = query.bbox
        info_srs = self._best_supported_srs(dst_srs)
        info_bbox = req_srs.transform_bbox_to(info_srs, req_bbox)
        
        req_coord = make_lin_transf((0, 0) + query.size, req_bbox)(query.pos)
        
        info_coord = req_srs.transform_to(info_srs, req_coord)
        info_pos = make_lin_transf((info_bbox), (0, 0) + params.size)(info_coord)
        
        info_query = InfoQuery(info_bbox, query.size, info_srs, info_pos, query.info_format)
        
        return self._retrieve(info_query)
    
    def _best_supported_srs(self, srs):
        return iter(self.supported_srs).next()
    
    def _retrieve(self, query):
        url = self._query_url(query)
        return self.http_client.open(url)
    
    def _query_url(self, query):
        req = self.request_template.copy()
        req.params.bbox = query.bbox
        req.params.size = query.size
        req.params.pos = query.pos
        # del req.params['info_format']
        req.params['query_layers'] = req.params['layers']
        if query.info_format:
            req.params['info_format'] = query.info_format
        req.params.srs = query.srs.srs_code
        
        return req.complete_url

class WMSSource(Source):
    supports_meta_tiles = True
    def __init__(self, client):
        Source.__init__(self)
        self.client = client
        #TODO extend
        self.extend = MapExtend((-180, -90, 180, 90), SRS(4326))
    
    def get_map(self, query):
        try:
            return self.client.get_map(query)
        except HTTPClientError, e:
            reraise_exception(TileSourceError(e.args[0]), sys.exc_info())
        

class DebugSource(Source):
    extend = MapExtend((-180, -90, 180, 90), SRS(4326))
    def get_map(self, query):
        bbox = query.bbox
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        res_x = w/query.size[0]
        res_y = h/query.size[1]
        debug_info = "bbox: %r\nres: %.8f(%.8f)" % (bbox, res_x, res_y)
        return message_image(debug_info, size=query.size, transparent=True)


class InfoSource(object):
    def get_info(self, query):
        raise NotImplementedError

class WMSInfoSource(InfoSource):
    def __init__(self, client):
        self.client = client
    def get_info(self, query):
        return self.client.get_info(query).read()

class TiledSource(Source):
    def __init__(self, grid, client, inverse=False):
        self.grid = grid
        self.client = client
        self.inverse = inverse
    
    def get_map(self, query):
        if self.grid.tile_size != query.size:
            raise InvalidSourceQuery()
        if self.grid.srs != query.srs:
            raise InvalidSourceQuery()
        
        _bbox, grid, tiles = self.grid.get_affected_tiles(query.bbox, query.size)
        
        if grid != (1, 1):
            raise InvalidSourceQuery('bbox does not align to tile')

        tile_coord = tiles.next()
        
        if self.inverse:
            tile_coord = self.grid.flip_tile_coord(tile_coord)
        try:
            return self.client.get_tile(tile_coord)
        except HTTPClientError, e:
            reraise_exception(TileSourceError(e.args[0]), sys.exc_info())
        

