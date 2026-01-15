from __future__ import division

from typing import Optional

from mapproxy.cache.tile_manager import TileManager
from mapproxy.extent import map_extent_from_grid, MapExtent
from mapproxy.grid import NoTiles, GridError
from mapproxy.image import bbox_position_in_image, sub_image_result, BaseImageResult
from mapproxy.image.tile import TiledImage
from mapproxy.layer import merge_layer_res_ranges, BlankImageError, MapError, MapBBOXError
from mapproxy.layer.map_layer import MapLayer
from mapproxy.proj import ProjError
from mapproxy.query import MapQuery
from mapproxy.util.bbox import bbox_equals


class CacheMapLayer(MapLayer):
    supports_meta_tiles = True

    def __init__(self, tile_manager: TileManager, extent: Optional[MapExtent] = None, image_opts=None,
                 max_tile_limit=None):
        super().__init__(image_opts=image_opts)
        self.tile_manager = tile_manager
        self.grid = tile_manager.grid
        self.extent = extent or map_extent_from_grid(self.grid)
        self.res_range = None
        if not self.tile_manager.rescale_tiles:
            self.res_range = merge_layer_res_ranges(self.tile_manager.sources)
        self.max_tile_limit = max_tile_limit

    def get_map(self, query: MapQuery) -> BaseImageResult:
        self.check_res_range(query)

        if query.tiled_only:
            self._check_tiled(query)

        query_extent = MapExtent(query.bbox, query.srs)
        if not query.tiled_only and self.extent and not self.extent.contains(query_extent):
            if not self.extent.intersects(query_extent):
                raise BlankImageError()
            size, offset, bbox = bbox_position_in_image(query.bbox, query.size, self.extent.bbox_for(query.srs))
            if size[0] == 0 or size[1] == 0:
                raise BlankImageError()
            src_query = MapQuery(bbox, size, query.srs, query.format, dimensions=query.dimensions)
            resp = self._image(src_query)
            return sub_image_result(resp, size=query.size, offset=offset, image_opts=self.image_opts,
                                    cacheable=resp.cacheable)
        else:
            return self._image(query)

    def _check_tiled(self, query):
        if query.format != self.tile_manager.format:
            raise MapError("invalid tile format, use %s" % self.tile_manager.format)
        if query.size != self.grid.tile_size:
            raise MapError("invalid tile size (use %dx%d)" % self.grid.tile_size)

    def _image(self, query: MapQuery) -> BaseImageResult:
        try:
            src_bbox, tile_grid_size, affected_tile_coords = \
                self.grid.get_affected_tiles(query.bbox, query.size,
                                             req_srs=query.srs)
        except NoTiles:
            raise BlankImageError()
        except GridError as ex:
            raise MapBBOXError(ex.args[0])

        num_tiles = tile_grid_size[0] * tile_grid_size[1]

        if self.max_tile_limit and num_tiles >= self.max_tile_limit:
            raise MapBBOXError("too many tiles, max_tile_limit: %s, num_tiles: %s" % (self.max_tile_limit, num_tiles))

        if query.tiled_only:
            if num_tiles > 1:
                raise MapBBOXError("not a single tile")
            bbox = query.bbox
            if not bbox_equals(bbox, src_bbox, abs((bbox[2]-bbox[0])/query.size[0]/10),
                               abs((bbox[3]-bbox[1])/query.size[1]/10)):
                raise MapBBOXError("query does not align to tile boundaries")

        with self.tile_manager.session():
            tile_collection = self.tile_manager.load_tile_coords(
                affected_tile_coords, with_metadata=query.tiled_only, dimensions=query.dimensions)

        if tile_collection.empty:
            raise BlankImageError()

        if query.tiled_only:
            tile = tile_collection[0].image_result
            tile.image_opts = self.tile_manager.image_opts
            tile.cacheable = tile_collection[0].cacheable
            return tile

        tile_image_results = [tile.image_result for tile in tile_collection]
        tiled_image = TiledImage(tile_image_results, src_bbox=src_bbox, src_srs=self.grid.srs,
                                 tile_grid_size=tile_grid_size, tile_size=self.grid.tile_size)
        try:
            return tiled_image.transform(query.bbox, query.srs, query.size,
                                         self.tile_manager.image_opts)
        except ProjError:
            raise MapBBOXError("could not transform query BBOX")
        except IOError as ex:
            from mapproxy.source import SourceError
            raise SourceError("unable to transform image: %s" % ex)
