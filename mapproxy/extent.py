from __future__ import division

from mapproxy.srs import SRS
from mapproxy.util.bbox import merge_bbox, bbox_contains, bbox_intersects


def map_extent_from_grid(grid):
    """
    >>> from mapproxy.grid.tile_grid import tile_grid_for_epsg
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
            self._llbbox = self.srs.transform_bbox_to(self.srs.get_geographic_srs(), self.bbox)
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
            raise NotImplementedError
        return not self.__eq__(other)

    def __add__(self, other):
        if not isinstance(other, MapExtent):
            raise NotImplementedError
        if other.is_default:
            return self
        if self.is_default:
            return other
        return MapExtent(merge_bbox(self.llbbox, other.llbbox), self.srs.get_geographic_srs())

    def contains(self, other):
        if not isinstance(other, MapExtent):
            raise NotImplementedError
        if self.is_default:
            # DefaultMapExtent contains everything
            return True
        return bbox_contains(self.bbox, other.bbox_for(self.srs))

    def intersects(self, other):
        if not isinstance(other, MapExtent):
            raise NotImplementedError
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

    def transform(self, srs):
        return MapExtent(self.bbox_for(srs), srs)


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
