# -:- encoding: utf-8 -:-
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
Layers that can get maps/infos from different sources/caches.
"""

from __future__ import division

from mapproxy.extent import map_extent_from_grid, MapExtent
from mapproxy.grid import NoTiles, GridError
from mapproxy.grid.resolutions import merge_resolution_range
from mapproxy.image import sub_image_source, bbox_position_in_image
from mapproxy.image.opts import ImageOptions
from mapproxy.image.tile import TiledImage
from mapproxy.proj import ProjError
from mapproxy.srs import SupportedSRS
from mapproxy.util.bbox import bbox_equals
from mapproxy.query import MapQuery

import logging
from functools import reduce


log = logging.getLogger(__name__)


class BlankImage(Exception):
    pass


class MapError(Exception):
    pass


class MapBBOXError(Exception):
    pass


class MapLayer(object):
    supports_meta_tiles = False

    res_range = None

    coverage = None

    def __init__(self, image_opts=None):
        self.image_opts = image_opts or ImageOptions()

    def _get_opacity(self):
        return self.image_opts.opacity

    def _set_opacity(self, value):
        self.image_opts.opacity = value

    opacity = property(_get_opacity, _set_opacity)

    def is_opaque(self, query):
        """
        Whether the query result is opaque.

        This method is used for optimizations: layers below an opaque
        layer can be skipped. As sources with `transparent: false`
        still can return transparent images (min_res/max_res/coverages),
        implementations of this method need to be certain that the image
        is indeed opaque. is_opaque should return False if in doubt.
        """
        return False

    def check_res_range(self, query):
        if (self.res_range and
                not self.res_range.contains(query.bbox, query.size, query.srs)):
            raise BlankImage()

    def get_map(self, query):
        raise NotImplementedError

    def combined_layer(self, other, query):
        return None


class LimitedLayer(object):
    """
    Wraps an existing layer temporary and stores additional
    attributes for geographical limits.
    """

    def __init__(self, layer, coverage):
        self._layer = layer
        self.coverage = coverage

    def __getattr__(self, name):
        return getattr(self._layer, name)

    def combined_layer(self, other, query):
        if self.coverage == other.coverage:
            combined = self._layer.combined_layer(other, query)
            if combined:
                return LimitedLayer(combined, self.coverage)
        return None

    def get_info(self, query):
        if self.coverage:
            if not self.coverage.contains(query.coord, query.srs):
                return None
        return self._layer.get_info(query)


class InfoLayer(object):
    def get_info(self, query):
        raise NotImplementedError


class Dimension(list):
    def __init__(self, identifier, values, default=None):
        self.identifier = identifier
        if not default and values:
            default = values[0]
        self.default = default
        list.__init__(self, values)


class ResolutionConditional(MapLayer):
    supports_meta_tiles = True

    def __init__(self, one, two, resolution, srs, extent, opacity=None):
        MapLayer.__init__(self)
        self.one = one
        self.two = two
        self.res_range = merge_layer_res_ranges([one, two])
        self.resolution = resolution
        self.srs = srs

        self.opacity = opacity
        self.extent = extent

    def get_map(self, query):
        self.check_res_range(query)
        bbox = query.bbox
        if query.srs != self.srs:
            bbox = query.srs.transform_bbox_to(self.srs, bbox)

        xres = (bbox[2] - bbox[0]) / query.size[0]
        yres = (bbox[3] - bbox[1]) / query.size[1]
        res = min(xres, yres)
        log.debug('actual res: %s, threshold res: %s', res, self.resolution)

        if res > self.resolution:
            return self.one.get_map(query)
        else:
            return self.two.get_map(query)


class SRSConditional(MapLayer):
    supports_meta_tiles = True

    def __init__(self, layers, extent, opacity=None, preferred_srs=None):
        MapLayer.__init__(self)
        self.srs_map = {}
        self.res_range = merge_layer_res_ranges([x[0] for x in layers])

        supported_srs = []
        for layer, srs in layers:
            supported_srs.append(srs)
            self.srs_map[srs] = layer
        self.supported_srs = SupportedSRS(supported_srs, preferred_srs)
        self.extent = extent
        self.opacity = opacity

    def get_map(self, query):
        self.check_res_range(query)
        layer = self._select_layer(query.srs)
        return layer.get_map(query)

    def _select_layer(self, query_srs):
        srs = self.supported_srs.best_srs(query_srs)
        return self.srs_map[srs]


class DirectMapLayer(MapLayer):
    supports_meta_tiles = True

    def __init__(self, source, extent):
        MapLayer.__init__(self)
        self.source = source
        self.res_range = getattr(source, 'res_range', None)
        self.extent = extent

    def get_map(self, query):
        self.check_res_range(query)
        return self.source.get_map(query)


def merge_layer_res_ranges(layers):
    ranges = [s.res_range for s in layers
              if hasattr(s, 'res_range')]

    if ranges:
        ranges = reduce(merge_resolution_range, ranges)

    return ranges


class CacheMapLayer(MapLayer):
    supports_meta_tiles = True

    def __init__(self, tile_manager, extent=None, image_opts=None,
                 max_tile_limit=None):
        MapLayer.__init__(self, image_opts=image_opts)
        self.tile_manager = tile_manager
        self.grid = tile_manager.grid
        self.extent = extent or map_extent_from_grid(self.grid)
        self.res_range = []
        if not self.tile_manager.rescale_tiles:
            self.res_range = merge_layer_res_ranges(self.tile_manager.sources)
        self.max_tile_limit = max_tile_limit

    def get_map(self, query):
        self.check_res_range(query)

        if query.tiled_only:
            self._check_tiled(query)

        query_extent = MapExtent(query.bbox, query.srs)
        if not query.tiled_only and self.extent and not self.extent.contains(query_extent):
            if not self.extent.intersects(query_extent):
                raise BlankImage()
            size, offset, bbox = bbox_position_in_image(query.bbox, query.size, self.extent.bbox_for(query.srs))
            if size[0] == 0 or size[1] == 0:
                raise BlankImage()
            src_query = MapQuery(bbox, size, query.srs, query.format, dimensions=query.dimensions)
            resp = self._image(src_query)
            result = sub_image_source(resp, size=query.size, offset=offset, image_opts=self.image_opts,
                                      cacheable=resp.cacheable)
        else:
            result = self._image(query)
        return result

    def _check_tiled(self, query):
        if query.format != self.tile_manager.format:
            raise MapError("invalid tile format, use %s" % self.tile_manager.format)
        if query.size != self.grid.tile_size:
            raise MapError("invalid tile size (use %dx%d)" % self.grid.tile_size)

    def _image(self, query):
        try:
            src_bbox, tile_grid, affected_tile_coords = \
                self.grid.get_affected_tiles(query.bbox, query.size,
                                             req_srs=query.srs)
        except NoTiles:
            raise BlankImage()
        except GridError as ex:
            raise MapBBOXError(ex.args[0])

        num_tiles = tile_grid[0] * tile_grid[1]

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
            raise BlankImage()

        if query.tiled_only:
            tile = tile_collection[0].source
            tile.image_opts = self.tile_manager.image_opts
            tile.cacheable = tile_collection[0].cacheable
            return tile

        tile_sources = [tile.source for tile in tile_collection]
        tiled_image = TiledImage(tile_sources, src_bbox=src_bbox, src_srs=self.grid.srs,
                                 tile_grid=tile_grid, tile_size=self.grid.tile_size)
        try:
            return tiled_image.transform(query.bbox, query.srs, query.size,
                                         self.tile_manager.image_opts)
        except ProjError:
            raise MapBBOXError("could not transform query BBOX")
        except IOError as ex:
            from mapproxy.source import SourceError
            raise SourceError("unable to transform image: %s" % ex)
