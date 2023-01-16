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


from functools import partial
from contextlib import contextmanager
from mapproxy.grid import MetaGrid
from mapproxy.image import BlankImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.image.merge import merge_images
from mapproxy.image.tile import TileSplitter, TiledImage
from mapproxy.layer import MapQuery, BlankImage
from mapproxy.util import async_
from mapproxy.util.py import reraise


class TileManager(object):
    """
    Manages tiles for a single grid.
    Loads tiles from the cache, creates new tiles from sources and stores them
    into the cache, or removes tiles.

    :param pre_store_filter: a list with filter. each filter will be called
        with a tile before it will be stored to disc. the filter should
        return this or a new tile object.
    """
    def __init__(self, grid, cache, sources, format, locker, image_opts=None, request_format=None,
            meta_buffer=None, meta_size=None, minimize_meta_requests=False, identifier=None,
            pre_store_filter=None, concurrent_tile_creators=1, tile_creator_class=None,
            bulk_meta_tiles=False,
            rescale_tiles=0,
            cache_rescaled_tiles=False,
        ):
        self.grid = grid
        self.cache = cache
        self.locker = locker
        self.identifier = identifier
        self.meta_grid = None
        self.format = format
        self.image_opts = image_opts
        self.request_format = request_format or format
        self.sources = sources
        self.minimize_meta_requests = minimize_meta_requests
        self._expire_timestamp = None
        self.pre_store_filter = pre_store_filter or []
        self.concurrent_tile_creators = concurrent_tile_creators
        self.tile_creator_class = tile_creator_class or TileCreator

        self.rescale_tiles = rescale_tiles
        self.cache_rescaled_tiles = cache_rescaled_tiles

        if meta_buffer or (meta_size and not meta_size == [1, 1]):
            if all(source.supports_meta_tiles for source in sources):
                self.meta_grid = MetaGrid(grid, meta_size=meta_size, meta_buffer=meta_buffer)
            elif any(source.supports_meta_tiles for source in sources):
                raise ValueError('meta tiling configured but not supported by all sources')
            elif meta_size and not meta_size == [1, 1] and bulk_meta_tiles:
                # meta tiles configured but all sources are tiled
                # use bulk_meta_tile mode that download tiles in parallel
                self.meta_grid = MetaGrid(grid, meta_size=meta_size, meta_buffer=0)
                self.tile_creator_class = partial(self.tile_creator_class, bulk_meta_tiles=True)

    @contextmanager
    def session(self):
        """
        Context manager for access to the cache. Cleans up after usage
        for connection based caches.

        >>> with tile_manager.session(): #doctest: +SKIP
        ...    tile_manager.load_tile_coords(tile_coords)

        """
        yield
        self.cleanup()

    def cleanup(self):
        if hasattr(self.cache, 'cleanup'):
            self.cache.cleanup()

    def load_tile_coord(self, tile_coord, dimensions=None, with_metadata=False):
        return self.load_tile_coords(
            [tile_coord], dimensions=dimensions, with_metadata=with_metadata,
        )[0]


    def load_tile_coords(self, tile_coords, dimensions=None, with_metadata=False):
        tiles = TileCollection(tile_coords)
        rescale_till_zoom = 0
        if self.rescale_tiles:
            rescaled_tiles = {}

            for t in tiles.tiles:
                # Use zoom level from first None tile.
                if t.coord is not None:
                    rescale_till_zoom = t.coord[2] + self.rescale_tiles
                    break
            else:
                return tiles

            if rescale_till_zoom < 0:
                rescale_till_zoom = 0
            if rescale_till_zoom > self.grid.levels:
                rescale_till_zoom = self.grid.levels

        tiles = self._load_tile_coords(
            tiles, dimensions=dimensions, with_metadata=with_metadata,
            rescale_till_zoom=rescale_till_zoom, rescaled_tiles={},
        )

        for t in tiles.tiles:
            # Remove our internal marker source, for missing tiles.
            if t.source is RESCALE_TILE_MISSING:
                t.source = None

        return tiles

    def _load_tile_coords(self, tiles, dimensions=None, with_metadata=False,
                          rescale_till_zoom=None, rescaled_tiles=None,
        ):
        uncached_tiles = []

        if rescaled_tiles:
            for t in tiles:
                if t.coord in rescaled_tiles:
                    t.source = rescaled_tiles[t.coord].source

        # load all in batch
        self.cache.load_tiles(tiles, with_metadata)

        for tile in tiles:
            if tile.coord is not None and not self.is_cached(tile, dimensions=dimensions):
                # missing or staled
                uncached_tiles.append(tile)

        if uncached_tiles:
            creator = self.creator(dimensions=dimensions)
            created_tiles = creator.create_tiles(uncached_tiles)
            if not created_tiles and self.rescale_tiles:
                created_tiles = [self._scaled_tile(t, rescale_till_zoom, rescaled_tiles) for t in uncached_tiles]

            for created_tile in created_tiles:
                if created_tile.coord in tiles:
                    tiles[created_tile.coord].source = created_tile.source

        return tiles

    def remove_tile_coords(self, tile_coords, dimensions=None):
        tiles = TileCollection(tile_coords)
        self.cache.remove_tiles(tiles)

    def creator(self, dimensions=None):
        return self.tile_creator_class(self, dimensions=dimensions)

    def lock(self, tile):
        if self.meta_grid:
            tile = Tile(self.meta_grid.main_tile(tile.coord))
        return self.locker.lock(tile)

    def is_cached(self, tile, dimensions=None):
        """
        Return True if the tile is cached.
        """
        if isinstance(tile, tuple):
            tile = Tile(tile)
        if tile.coord is None:
            return True
        cached = self.cache.is_cached(tile)
        max_mtime = self.expire_timestamp(tile)
        if cached and max_mtime is not None:
            self.cache.load_tile_metadata(tile)
            stale = tile.timestamp < max_mtime
            if stale:
                cached = False
        return cached

    def is_stale(self, tile, dimensions=None):
        """
        Return True if tile exists _and_ is expired.
        """
        if isinstance(tile, tuple):
            tile = Tile(tile)
        if self.cache.is_cached(tile):
            # tile exists
            if not self.is_cached(tile):
                # expired
                return True
            return False
        return False

    def expire_timestamp(self, tile=None):
        """
        Return the timestamp until which a tile should be accepted as up-to-date,
        or ``None`` if the tiles should not expire.

        :note: Returns _expire_timestamp by default.
        """
        return self._expire_timestamp

    def apply_tile_filter(self, tile):
        """
        Apply all `pre_store_filter` to this tile.
        Returns filtered tile.
        """
        if tile.stored:
            return tile

        for img_filter in self.pre_store_filter:
            tile = img_filter(tile)
        return tile

    def _scaled_tile(self, tile, stop_zoom, rescaled_tiles):
        """
        Try to load tile by loading, scaling and clipping tiles from zoom levels above or
        below. stop_zoom determines if tiles from above should be scaled up, or if tiles
        from below should be scaled down.
        Returns an empty Tile if tile zoom level is stop_zoom.
        """
        if tile.coord in rescaled_tiles:
            return rescaled_tiles[tile.coord]

        # Cache tile in rescaled_tiles. We initially set source to a fixed
        # BlankImageSource and overwrite it if we actually rescaled the tile.
        tile.source = RESCALE_TILE_MISSING
        rescaled_tiles[tile.coord] = tile

        tile_bbox = self.grid.tile_bbox(tile.coord)
        current_zoom = tile.coord[2]
        if stop_zoom == current_zoom:
            return tile
        if stop_zoom > current_zoom:
            src_level = current_zoom + 1
        else:
            src_level = current_zoom - 1

        src_bbox, src_tile_grid, affected_tile_coords = self.grid.get_affected_level_tiles(tile_bbox, src_level)

        affected_tiles = TileCollection(affected_tile_coords)
        for t in affected_tiles:
            # Add sources of cached tiles, to avoid loading same tile multiple times
            # loading recursive.
            if t.coord in rescaled_tiles:
                t.source = rescaled_tiles[t.coord].source

        tile_collection = self._load_tile_coords(
            affected_tiles,
            rescale_till_zoom=stop_zoom,
            rescaled_tiles=rescaled_tiles,
        )

        if tile_collection.blank:
            return tile

        tile_sources = []
        for t in tile_collection:
            # Replace RESCALE_TILE_MISSING with None, before transforming tiles.
            tile_sources.append(t.source if t.source is not RESCALE_TILE_MISSING else None)

        tiled_image = TiledImage(tile_sources, src_bbox=src_bbox, src_srs=self.grid.srs,
                            tile_grid=src_tile_grid, tile_size=self.grid.tile_size)
        tile.source = tiled_image.transform(tile_bbox, self.grid.srs, self.grid.tile_size, self.image_opts)

        if self.cache_rescaled_tiles:
            self.cache.store_tile(tile)
        return tile

# RESCALE_TILE_MISSING is a dummy source to prevent a tile cache from loading
# a tile that we already found out is missing.
RESCALE_TILE_MISSING = BlankImageSource((256, 256), ImageOptions())

class TileCreator(object):
    def __init__(self, tile_mgr, dimensions=None, image_merger=None, bulk_meta_tiles=False):
        self.cache = tile_mgr.cache
        self.sources = tile_mgr.sources
        self.grid = tile_mgr.grid
        self.meta_grid = tile_mgr.meta_grid
        self.bulk_meta_tiles = bulk_meta_tiles
        self.tile_mgr = tile_mgr
        self.dimensions = dimensions
        self.image_merger = image_merger

    def is_cached(self, tile):
        """
        Return True if the tile is cached.
        """
        return self.tile_mgr.is_cached(tile)

    def create_tiles(self, tiles):
        if not self.sources:
            return []
        if not self.meta_grid:
            created_tiles = self._create_single_tiles(tiles)
        elif self.tile_mgr.minimize_meta_requests and len(tiles) > 1:
            # use minimal requests only for mulitple tile requests (ie not for TMS)
            meta_tile = self.meta_grid.minimal_meta_tile([t.coord for t in tiles])
            created_tiles = self._create_meta_tile(meta_tile)
        else:
            meta_tiles = []
            meta_bboxes = set()
            for tile in tiles:
                meta_tile = self.meta_grid.meta_tile(tile.coord)
                if meta_tile.bbox not in meta_bboxes:
                    meta_tiles.append(meta_tile)
                    meta_bboxes.add(meta_tile.bbox)

            created_tiles = self._create_meta_tiles(meta_tiles)

        return created_tiles

    def _create_single_tiles(self, tiles):
        if self.tile_mgr.concurrent_tile_creators > 1 and len(tiles) > 1:
            return self._create_threaded(self._create_single_tile, tiles)

        created_tiles = []
        for tile in tiles:
            created_tiles.extend(self._create_single_tile(tile))
        return created_tiles

    def _create_threaded(self, create_func, tiles):
        result = []
        async_pool = async_.Pool(self.tile_mgr.concurrent_tile_creators)
        for new_tiles in async_pool.imap(create_func, tiles):
            result.extend(new_tiles)
        return result

    def _create_single_tile(self, tile):
        tile_bbox = self.grid.tile_bbox(tile.coord)
        query = MapQuery(tile_bbox, self.grid.tile_size, self.grid.srs,
                         self.tile_mgr.request_format, dimensions=self.dimensions)
        with self.tile_mgr.lock(tile):
            if not self.is_cached(tile):
                source = self._query_sources(query)
                if not source: return []
                if self.tile_mgr.image_opts != source.image_opts:
                    # call as_buffer to force conversion into cache format
                    source.as_buffer(self.tile_mgr.image_opts)
                source.image_opts = self.tile_mgr.image_opts
                tile.source = source
                tile.cacheable = source.cacheable
                tile = self.tile_mgr.apply_tile_filter(tile)
                if source.cacheable:
                    self.cache.store_tile(tile)
            else:
                self.cache.load_tile(tile)
        return [tile]

    def _query_sources(self, query):
        """
        Query all sources and return the results as a single ImageSource.
        Multiple sources will be merged into a single image.
        """

        # directly return get_map without merge if ...
        if (len(self.sources) == 1 and
            not self.image_merger and # no special image_merger (like BandMerger)
            not (self.sources[0].coverage and  # no clipping coverage
                 self.sources[0].coverage.clip and
                 self.sources[0].coverage.intersects(query.bbox, query.srs))
        ):
            try:
                return self.sources[0].get_map(query)
            except BlankImage:
                return None

        def get_map_from_source(source):
            try:
                img = source.get_map(query)
            except BlankImage:
                return None, None
            else:
                return (img, source.coverage)

        layers = []
        for layer in async_.imap(get_map_from_source, self.sources):
            if layer[0] is not None:
                layers.append(layer)

        return merge_images(layers, size=query.size, bbox=query.bbox, bbox_srs=query.srs,
                            image_opts=self.tile_mgr.image_opts, merger=self.image_merger)

    def _create_meta_tiles(self, meta_tiles):
        if self.bulk_meta_tiles:
            created_tiles = []
            for meta_tile in meta_tiles:
                    created_tiles.extend(self._create_bulk_meta_tile(meta_tile))
            return created_tiles

        if self.tile_mgr.concurrent_tile_creators > 1 and len(meta_tiles) > 1:
            return self._create_threaded(self._create_meta_tile, meta_tiles)

        created_tiles = []
        for meta_tile in meta_tiles:
            created_tiles.extend(self._create_meta_tile(meta_tile))
        return created_tiles

    def _create_meta_tile(self, meta_tile):
        """
        _create_meta_tile queries a single meta tile and splits it into
        tiles.
        """
        tile_size = self.grid.tile_size
        query = MapQuery(meta_tile.bbox, meta_tile.size, self.grid.srs, self.tile_mgr.request_format,
            dimensions=self.dimensions)
        main_tile = Tile(meta_tile.main_tile_coord)
        with self.tile_mgr.lock(main_tile):
            if not all(self.is_cached(t) for t in meta_tile.tiles if t is not None):
                meta_tile_image = self._query_sources(query)
                if not meta_tile_image: return []
                splitted_tiles = split_meta_tiles(meta_tile_image, meta_tile.tile_patterns,
                                                  tile_size, self.tile_mgr.image_opts)
                splitted_tiles = [self.tile_mgr.apply_tile_filter(t) for t in splitted_tiles]
                if meta_tile_image.cacheable:
                    self.cache.store_tiles(splitted_tiles)
                return splitted_tiles
            # else
        tiles = [Tile(coord) for coord in meta_tile.tiles]
        self.cache.load_tiles(tiles)
        return tiles

    def _create_bulk_meta_tile(self, meta_tile):
        """
        _create_bulk_meta_tile queries each tile of the meta tile in parallel
        (using concurrent_tile_creators).
        """
        tile_size = self.grid.tile_size
        main_tile = Tile(meta_tile.main_tile_coord)
        with self.tile_mgr.lock(main_tile):
            if not all(self.is_cached(t) for t in meta_tile.tiles if t is not None):
                async_pool = async_.Pool(self.tile_mgr.concurrent_tile_creators)
                def query_tile(coord):
                    try:
                        query = MapQuery(self.grid.tile_bbox(coord), tile_size, self.grid.srs, self.tile_mgr.request_format,
                            dimensions=self.dimensions)
                        tile_image = self._query_sources(query)
                        if tile_image is None:
                            return None

                        if self.tile_mgr.image_opts != tile_image.image_opts:
                            # call as_buffer to force conversion into cache format
                            tile_image.as_buffer(self.tile_mgr.image_opts)

                        tile = Tile(coord, cacheable=tile_image.cacheable)
                        tile.source = tile_image
                        tile = self.tile_mgr.apply_tile_filter(tile)
                    except BlankImage:
                        return None
                    else:
                        return tile

                tiles = []
                for tile_task in async_pool.imap(query_tile,
                    [t for t in meta_tile.tiles if t is not None],
                    use_result_objects=True,
                ):
                    if tile_task.exception is None:
                        tile = tile_task.result
                        if tile is not None:
                            tiles.append(tile)
                    else:
                        ex = tile_task.exception
                        async_pool.shutdown(True)
                        reraise(ex)

                self.cache.store_tiles([t for t in tiles if t.cacheable])
                return tiles

            # else
        tiles = [Tile(coord) for coord in meta_tile.tiles]
        self.cache.load_tiles(tiles)
        return tiles


class Tile(object):
    """
    Internal data object for all tiles. Stores the tile-``coord`` and the tile data.

    :ivar source: the data of this tile
    :type source: ImageSource
    """
    def __init__(self, coord, source=None, cacheable=True):
        self.coord = coord
        self.source = source
        self.location = None
        self.stored = False
        self._cacheable = cacheable
        self.size = None
        self.timestamp = None

    def _cacheable_get(self):
        return CacheInfo(cacheable=self._cacheable, timestamp=self.timestamp,
            size=self.size)

    def _cacheable_set(self, cacheable):
        if isinstance(cacheable, bool):
            self._cacheable = cacheable
        else: # assume cacheable is CacheInfo
            self._cacheable = cacheable.cacheable
            self.timestamp = cacheable.timestamp
            self.size = cacheable.size

    cacheable = property(_cacheable_get, _cacheable_set)

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

class CacheInfo(object):
    def __init__(self, cacheable=True, timestamp=None, size=None):
        self.cacheable = cacheable
        self.timestamp = timestamp
        self.size = size

    def __bool__(self):
        return self.cacheable

    # PY2 compat
    __nonzero__ = __bool__

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

    @property
    def empty(self):
        """
        Returns True if no tile in this collection contains a source.
        """
        return all((t.source is None for t in self.tiles))

    @property
    def blank(self):
        """
        Returns True if all sources collection are BlankImageSources or have not source at all.
        """
        return all((t.source is None or isinstance(t.source, BlankImageSource) for t in self.tiles))

    def __repr__(self):
        return 'TileCollection(%r)' % self.tiles


def split_meta_tiles(meta_tile, tiles, tile_size, image_opts):
    try:
        # TODO png8
        # if not self.transparent and format == 'png':
        #     format = 'png8'
        splitter = TileSplitter(meta_tile, image_opts)
    except IOError:
        # TODO
        raise
    split_tiles = []
    for tile in tiles:
        tile_coord, crop_coord = tile
        if tile_coord is None: continue
        data = splitter.get_tile(crop_coord, tile_size)
        new_tile = Tile(tile_coord, cacheable=meta_tile.cacheable)
        new_tile.source = data
        split_tiles.append(new_tile)
    return split_tiles
