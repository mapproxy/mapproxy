from contextlib import contextmanager
from functools import partial
from typing import Any, cast

from mapproxy.cache.tile import TileCollection, Tile
from mapproxy.cache.tile_creator import RESCALE_TILE_MISSING, TileCreator
from mapproxy.grid.meta_grid import MetaGrid
from mapproxy.image.mask import mask_image_source_from_coverage
from mapproxy.image.opts import ImageOptions
from mapproxy.image.tile import TiledImage
from mapproxy.layer.map_layer import MapLayer
from mapproxy.source import DummySource


class TileManager:
    """
    Manages tiles for a single grid.
    Loads tiles from the cache, creates new tiles from sources and stores them
    into the cache, or removes tiles.

    :param pre_store_filter: a list with filter. each filter will be called
        with a tile before it will be stored to disc. the filter should
        return this or a new tile object.
    """

    def __init__(self, grid, cache, sources: list[MapLayer], format, locker, image_opts=None, request_format=None,
                 meta_buffer=None, meta_size=None, minimize_meta_requests=False, identifier=None,
                 pre_store_filter=None, concurrent_tile_creators=1, tile_creator_class=None,
                 bulk_meta_tiles=False,
                 rescale_tiles=0,
                 cache_rescaled_tiles=False,
                 dimensions=None
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
        self._refresh_before: dict[str, Any] = {}
        self.pre_store_filter = pre_store_filter or []
        self.concurrent_tile_creators = concurrent_tile_creators
        self.tile_creator_class = tile_creator_class or TileCreator
        self.dimensions = dimensions

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

        # Remove tiles that are not in the cache coverage
        if self.cache.coverage:
            for t in tiles.tiles:
                if t.coord:
                    tile_bbox = self.grid.tile_bbox(t.coord)
                    if not self.cache.coverage.intersects(tile_bbox, self.grid.srs):
                        t.coord = None

        tiles = self._load_tile_coords(
            tiles, dimensions=dimensions, with_metadata=with_metadata,
            rescale_till_zoom=rescale_till_zoom, rescaled_tiles={},
        )

        for t in tiles.tiles:
            # Clip tiles if clipping is enabled for coverage
            if t.coord and self.cache.coverage and self.cache.coverage.clip and t.source:
                tile_bbox = self.grid.tile_bbox(t.coord)
                coverage = self.cache.coverage

                if coverage.intersects(tile_bbox, self.grid.srs):
                    t.source = mask_image_source_from_coverage(
                        t.source, tile_bbox, self.grid.srs, coverage, ImageOptions(transparent=True, format='png'))

            # Remove our internal marker source, for missing tiles.
            if t.source is RESCALE_TILE_MISSING:
                t.source = None
        return tiles

    def _is_tile_missing(self, tile, cache_only, dimensions=None):
        if tile.coord is None:
            return False
        if cache_only:
            # in cache_only mode, we already fetched the tile from cache
            return tile.is_missing()
        else:
            # missing or staled
            return not self.is_cached(tile, dimensions=dimensions)

    def _load_tile_coords(self, tiles, dimensions=None, with_metadata=False,
                          rescale_till_zoom=None, rescaled_tiles=None
                          ):
        uncached_tiles = []

        if rescaled_tiles:
            for t in tiles:
                if t.coord in rescaled_tiles:
                    t.source = rescaled_tiles[t.coord].source

        # load all in batch
        self.cache.load_tiles(tiles, with_metadata, dimensions=dimensions)

        # if no real source, we are running in cache_only mode
        cache_only = self.sources == [] or (len(self.sources) == 1 and isinstance(self.sources[0], DummySource))
        # if no rescale_tiles and cache_only, we dont have any additional processing to do
        if (self.rescale_tiles == 0 and cache_only):
            return tiles

        for tile in tiles:
            if self._is_tile_missing(tile, cache_only, dimensions=dimensions):
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

    def is_cached(self, tile: 'Tile', dimensions=None) -> bool:
        """
        Return True if the tile is cached.
        """
        if isinstance(tile, tuple):
            tile = Tile(cast(tuple[int, int, int], tile))
        if tile.coord is None:
            return True
        cached = self.cache.is_cached(tile, dimensions=dimensions)
        max_mtime = self.expire_timestamp(tile)
        if cached and max_mtime is not None:
            self.cache.load_tile_metadata(tile, dimensions=self.dimensions)
            # file time stamp must be rounded to integer since time conversion functions
            # mktime and timetuple strip decimals from seconds
            assert tile.timestamp is not None
            stale = int(tile.timestamp) <= max_mtime
            if stale:
                cached = False
        return cached

    def is_stale(self, tile, dimensions=None):
        """
        Return True if tile exists _and_ is expired.
        """
        if isinstance(tile, tuple):
            tile = Tile(cast(tuple[int, int, int], tile))
        if self.cache.is_cached(tile, dimensions=dimensions):
            # tile exists
            if not self.is_cached(tile, dimensions=dimensions):
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
        if self._refresh_before:
            from mapproxy.seed.config import before_timestamp_from_options
            return before_timestamp_from_options(self._refresh_before)
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
