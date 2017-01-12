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

from __future__ import division, with_statement
from mapproxy.grid import NoTiles, GridError, merge_resolution_range, bbox_intersects, bbox_contains
from mapproxy.image import SubImageSource, bbox_position_in_image
from mapproxy.image.opts import ImageOptions
from mapproxy.image.tile import TiledImage
from mapproxy.srs import SRS, bbox_equals, merge_bbox, make_lin_transf
from mapproxy.proj import ProjError
from mapproxy.compat import iteritems

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

    def _get_transparent(self):
        return self.image_opts.transparent

    def _set_transparent(self, value):
        self.image_opts.transparent = value

    transparent = property(_get_transparent, _set_transparent)

    def _get_opacity(self):
        return self.image_opts.opacity

    def _set_opacity(self, value):
        self.image_opts.opacity = value

    opacity = property(_get_opacity, _set_opacity)

    def is_opaque(self):
        if self.opacity is None:
            return not self.transparent
        return self.opacity >= 0.99

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

class MapQuery(object):
    """
    Internal query for a map with a specific extent, size, srs, etc.
    """
    def __init__(self, bbox, size, srs, format='image/png', transparent=False,
                 tiled_only=False, dimensions=None):
        self.bbox = bbox
        self.size = size
        self.srs = srs
        self.format = format
        self.transparent = transparent
        self.tiled_only = tiled_only
        self.dimensions = dimensions or {}

    def dimensions_for_params(self, params):
        """
        Return subset of the dimensions.

        >>> mq = MapQuery(None, None, None, dimensions={'Foo': 1, 'bar': 2})
        >>> mq.dimensions_for_params(set(['FOO', 'baz']))
        {'Foo': 1}
        """
        params = [p.lower() for p in params]
        return dict((k, v) for k, v in iteritems(self.dimensions) if k.lower() in params)

    def __repr__(self):
        return "MapQuery(bbox=%(bbox)s, size=%(size)s, srs=%(srs)r, format=%(format)s)" % self.__dict__

class InfoQuery(object):
    def __init__(self, bbox, size, srs, pos, info_format, format=None,
        feature_count=None):
        self.bbox = bbox
        self.size = size
        self.srs = srs
        self.pos = pos
        self.info_format = info_format
        self.format = format
        self.feature_count = feature_count

    @property
    def coord(self):
        return make_lin_transf((0, 0, self.size[0], self.size[1]), self.bbox)(self.pos)

class LegendQuery(object):
    def __init__(self, format, scale):
        self.format = format
        self.scale = scale

class Dimension(list):
    def __init__(self, identifier, values, default=None):
        self.identifier = identifier
        if not default and values:
            default = values[0]
        self.default = default
        list.__init__(self, values)


def map_extent_from_grid(grid):
    """
    >>> from mapproxy.grid import tile_grid_for_epsg
    >>> map_extent_from_grid(tile_grid_for_epsg('EPSG:900913'))
    ... #doctest: +NORMALIZE_WHITESPACE
    MapExtent((-20037508.342789244, -20037508.342789244,
               20037508.342789244, 20037508.342789244), SRS('EPSG:900913'))
    """
    return MapExtent(grid.bbox, grid.srs)

class MapExtent(object):
    """
    >>> me = MapExtent((5, 45, 15, 55), SRS(4326))
    >>> me.llbbox
    (5, 45, 15, 55)
    >>> [int(x) for x in me.bbox_for(SRS(900913))]
    [556597, 5621521, 1669792, 7361866]
    >>> [int(x) for x in me.bbox_for(SRS(4326))]
    [5, 45, 15, 55]
    """
    is_default = False
    def __init__(self, bbox, srs):
        self._llbbox = None
        self.bbox = bbox
        self.srs = srs

    @property
    def llbbox(self):
        if not self._llbbox:
            self._llbbox = self.srs.transform_bbox_to(SRS(4326), self.bbox)
        return self._llbbox

    def bbox_for(self, srs):
        if srs == self.srs:
            return self.bbox

        return self.srs.transform_bbox_to(srs, self.bbox)

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.bbox, self.srs)

    def __eq__(self, other):
        if not isinstance(other, MapExtent):
            return NotImplemented

        if self.srs != other.srs:
            return False

        if self.bbox != other.bbox:
            return False

        return True

    def __ne__(self, other):
        if not isinstance(other, MapExtent):
            return NotImplemented
        return not self.__eq__(other)

    def __add__(self, other):
        if not isinstance(other, MapExtent):
            raise NotImplemented
        if other.is_default:
            return self
        if self.is_default:
            return other
        return MapExtent(merge_bbox(self.llbbox, other.llbbox), SRS(4326))

    def contains(self, other):
        if not isinstance(other, MapExtent):
            raise NotImplemented
        if self.is_default:
            # DefaultMapExtent contains everything
            return True
        return bbox_contains(self.bbox, other.bbox_for(self.srs))

    def intersects(self, other):
        if not isinstance(other, MapExtent):
            raise NotImplemented
        return bbox_intersects(self.bbox, other.bbox_for(self.srs))

    def intersection(self, other):
        """
        Returns the intersection of `self` and `other`.

        >>> e = DefaultMapExtent().intersection(MapExtent((0, 0, 10, 10), SRS(4326)))
        >>> e.bbox, e.srs
        ((0, 0, 10, 10), SRS('EPSG:4326'))
        """
        if not self.intersects(other):
            return None

        source = self.bbox
        sub = other.bbox_for(self.srs)

        return MapExtent((
            max(source[0], sub[0]),
            max(source[1], sub[1]),
            min(source[2], sub[2]),
            min(source[3], sub[3])),
            self.srs)

class DefaultMapExtent(MapExtent):
    """
    Default extent that covers the whole world.
    Will not affect other extents when added.

    >>> m1 = MapExtent((0, 0, 10, 10), SRS(4326))
    >>> m2 = MapExtent((10, 0, 20, 10), SRS(4326))
    >>> m3 = DefaultMapExtent()
    >>> (m1 + m2).bbox
    (0, 0, 20, 10)
    >>> (m1 + m3).bbox
    (0, 0, 10, 10)
    """
    is_default = True
    def __init__(self):
        MapExtent.__init__(self, (-180, -90, 180, 90), SRS(4326))

def merge_layer_extents(layers):
    if not layers:
        return DefaultMapExtent()
    layers = layers[:]
    extent = layers.pop().extent
    for layer in layers:
        extent = extent + layer.extent
    return extent

class ResolutionConditional(MapLayer):
    supports_meta_tiles = True
    def __init__(self, one, two, resolution, srs, extent, opacity=None):
        MapLayer.__init__(self)
        self.one = one
        self.two = two
        self.res_range = merge_layer_res_ranges([one, two])
        self.resolution = resolution
        self.srs = srs

        #TODO
        self.transparent = self.one.transparent
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
    PROJECTED = 'PROJECTED'
    GEOGRAPHIC = 'GEOGRAPHIC'

    def __init__(self, layers, extent, transparent=False, opacity=None):
        MapLayer.__init__(self)
        self.transparent = transparent
        # TODO geographic/projected fallback
        self.srs_map = {}
        self.res_range = merge_layer_res_ranges([l[0] for l in layers])
        for layer, srss in layers:
            for srs in srss:
                self.srs_map[srs] = layer

        self.extent = extent
        self.opacity = opacity

    def get_map(self, query):
        self.check_res_range(query)
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
        self.res_range = merge_layer_res_ranges(self.tile_manager.sources)
        self.transparent = tile_manager.transparent
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
            src_query = MapQuery(bbox, size, query.srs, query.format)
            resp = self._image(src_query)
            result = SubImageSource(resp, size=query.size, offset=offset, image_opts=self.image_opts,
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
            raise MapBBOXError("too many tiles")

        if query.tiled_only:
            if num_tiles > 1:
                raise MapBBOXError("not a single tile")
            bbox = query.bbox
            if not bbox_equals(bbox, src_bbox, abs((bbox[2]-bbox[0])/query.size[0]/10),
                                               abs((bbox[3]-bbox[1])/query.size[1]/10)):
                raise MapBBOXError("query does not align to tile boundaries")

        with self.tile_manager.session():
            tile_collection = self.tile_manager.load_tile_coords(affected_tile_coords, with_metadata=query.tiled_only)

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


