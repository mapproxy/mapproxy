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

from __future__ import with_statement

import operator
import threading

from mapproxy.grid import bbox_intersects, bbox_contains
from mapproxy.util.py import cached_property
from mapproxy.util.geom import (
    require_geom_support,
    load_polygon_lines,
    transform_geometry,
    bbox_polygon,
    EmptyGeometryError,
)
from mapproxy.srs import SRS

import logging
from functools import reduce
log_config = logging.getLogger('mapproxy.config.coverage')

try:
    import shapely.geometry
    import shapely.prepared
except ImportError:
    # missing Shapely is handled by require_geom_support
    pass

def coverage(geom, srs, clip=False):
    if isinstance(geom, (list, tuple)):
        return BBOXCoverage(geom, srs, clip=clip)
    else:
        return GeomCoverage(geom, srs, clip=clip)

def load_limited_to(limited_to):
    require_geom_support()
    srs = SRS(limited_to['srs'])
    geom = limited_to['geometry']

    if not hasattr(geom, 'type'): # not a Shapely geometry
        if isinstance(geom, (list, tuple)):
            geom = bbox_polygon(geom)
        else:
            polygons = load_polygon_lines(geom.split('\n'))
            if len(polygons) == 1:
                geom = polygons[0]
            else:
                geom = shapely.geometry.MultiPolygon(polygons)

    return GeomCoverage(geom, srs, clip=True)

class MultiCoverage(object):
    clip = False
    """Aggregates multiple coverages"""
    def __init__(self, coverages):
        self.coverages = coverages
        self.bbox = self.extent.bbox

    @cached_property
    def extent(self):
        return reduce(operator.add, [c.extent for c in self.coverages])

    def intersects(self, bbox, srs):
        return any(c.intersects(bbox, srs) for c in self.coverages)

    def contains(self, bbox, srs):
        return any(c.contains(bbox, srs) for c in self.coverages)

    def transform_to(self, srs):
        return MultiCoverage([c.transform_to(srs) for c in self.coverages])

    def __eq__(self, other):
        if not isinstance(other, MultiCoverage):
            return NotImplemented

        if self.bbox != other.bbox:
            return False

        if len(self.coverages) != len(other.coverages):
            return False

        for a, b in zip(self.coverages, other.coverages):
            if a != b:
                return False

        return True

    def __ne__(self, other):
        if not isinstance(other, MultiCoverage):
            return NotImplemented
        return not self.__eq__(other)

    def __repr__(self):
        return '<MultiCoverage %r: %r>' % (self.extent.llbbox, self.coverages)

class BBOXCoverage(object):
    def __init__(self, bbox, srs, clip=False):
        self.bbox = bbox
        self.srs = srs
        self.geom = None
        self.clip = clip

    @property
    def extent(self):
        from mapproxy.layer import MapExtent

        return MapExtent(self.bbox, self.srs)

    def _bbox_in_coverage_srs(self, bbox, srs):
        if srs != self.srs:
            bbox = srs.transform_bbox_to(self.srs, bbox)
        return bbox

    def intersects(self, bbox, srs):
        bbox = self._bbox_in_coverage_srs(bbox, srs)
        return bbox_intersects(self.bbox, bbox)

    def intersection(self, bbox, srs):
        bbox = self._bbox_in_coverage_srs(bbox, srs)
        intersection = (
            max(self.bbox[0], bbox[0]),
            max(self.bbox[1], bbox[1]),
            min(self.bbox[2], bbox[2]),
            min(self.bbox[3], bbox[3]),
        )

        if intersection[0] >= intersection[2] or intersection[1] >= intersection[3]:
            return None
        return BBOXCoverage(intersection, self.srs, clip=self.clip)

    def contains(self, bbox, srs):
        bbox = self._bbox_in_coverage_srs(bbox, srs)
        return bbox_contains(self.bbox, bbox)

    def transform_to(self, srs):
        if srs == self.srs:
            return self

        bbox = self.srs.transform_bbox_to(srs, self.bbox)
        return BBOXCoverage(bbox, srs, clip=self.clip)

    def __eq__(self, other):
        if not isinstance(other, BBOXCoverage):
            return NotImplemented

        if self.srs != other.srs:
            return False

        if self.bbox != other.bbox:
            return False

        return True

    def __ne__(self, other):
        if not isinstance(other, BBOXCoverage):
            return NotImplemented
        return not self.__eq__(other)

    def __repr__(self):
        return '<BBOXCoverage %r/%r>' % (self.extent.llbbox, self.bbox)


class GeomCoverage(object):
    def __init__(self, geom, srs, clip=False):
        self.geom = geom
        self.bbox = geom.bounds
        self.srs = srs
        self.clip = clip
        self._prep_lock = threading.Lock()
        self._prepared_geom = None
        self._prepared_counter = 0
        self._prepared_max = 10000

    @property
    def extent(self):
        from mapproxy.layer import MapExtent
        return MapExtent(self.bbox, self.srs)

    @property
    def prepared_geom(self):
        # GEOS internal data structure for prepared geometries grows over time,
        # recreate to limit memory consumption
        if not self._prepared_geom or self._prepared_counter > self._prepared_max:
            self._prepared_geom = shapely.prepared.prep(self.geom)
            self._prepared_counter = 0
        self._prepared_counter += 1
        return self._prepared_geom

    def _geom_in_coverage_srs(self, geom, srs):
        if isinstance(geom, shapely.geometry.base.BaseGeometry):
            if srs != self.srs:
                geom = transform_geometry(srs, self.srs, geom)
        elif len(geom) == 2:
            if srs != self.srs:
                geom = srs.transform_to(self.srs, geom)
            geom = shapely.geometry.Point(geom)
        else:
            if srs != self.srs:
                geom = srs.transform_bbox_to(self.srs, geom)
            geom = bbox_polygon(geom)
        return geom

    def transform_to(self, srs):
        if srs == self.srs:
            return self

        geom = transform_geometry(self.srs, srs, self.geom)
        return GeomCoverage(geom, srs, clip=self.clip)

    def intersects(self, bbox, srs):
        bbox = self._geom_in_coverage_srs(bbox, srs)
        with self._prep_lock:
            return self.prepared_geom.intersects(bbox)

    def intersection(self, bbox, srs):
        bbox = self._geom_in_coverage_srs(bbox, srs)
        return GeomCoverage(self.geom.intersection(bbox), self.srs, clip=self.clip)

    def contains(self, bbox, srs):
        bbox = self._geom_in_coverage_srs(bbox, srs)
        with self._prep_lock:
            return self.prepared_geom.contains(bbox)

    def __eq__(self, other):
        if not isinstance(other, GeomCoverage):
            return NotImplemented

        if self.srs != other.srs:
            return False

        if self.bbox != other.bbox:
            return False

        if not self.geom.equals(other.geom):
            return False

        return True

    def __ne__(self, other):
        if not isinstance(other, GeomCoverage):
            return NotImplemented
        return not self.__eq__(other)

    def __repr__(self):
        return '<GeomCoverage %r: %r>' % (self.extent.llbbox, self.geom)

def union_coverage(coverages, clip=None):
    """
    Create a coverage that is the union of all `coverages`.
    Resulting coverage is in the SRS of the first coverage.
    """
    srs = coverages[0].srs

    coverages = [c.transform_to(srs) for c in coverages]

    geoms = []
    for c in coverages:
        if isinstance(c, BBOXCoverage):
            geoms.append(bbox_polygon(c.bbox))
        else:
            geoms.append(c.geom)

    import shapely.ops
    union = shapely.ops.cascaded_union(geoms)

    return GeomCoverage(union, srs=srs, clip=clip)

def diff_coverage(coverages, clip=None):
    """
    Create a coverage by subtracting all `coverages` from the first one.
    Resulting coverage is in the SRS of the first coverage.
    """
    srs = coverages[0].srs

    coverages = [c.transform_to(srs) for c in coverages]

    geoms = []
    for c in coverages:
        if isinstance(c, BBOXCoverage):
            geoms.append(bbox_polygon(c.bbox))
        else:
            geoms.append(c.geom)

    sub = shapely.ops.cascaded_union(geoms[1:])
    diff = geoms[0].difference(sub)

    if diff.is_empty:
        raise EmptyGeometryError("diff did not return any geometry")

    return GeomCoverage(diff, srs=srs, clip=clip)

def intersection_coverage(coverages, clip=None):
    """
    Create a coverage by creating the intersection of all `coverages`.
    Resulting coverage is in the SRS of the first coverage.
    """
    srs = coverages[0].srs

    coverages = [c.transform_to(srs) for c in coverages]

    geoms = []
    for c in coverages:
        if isinstance(c, BBOXCoverage):
            geoms.append(bbox_polygon(c.bbox))
        else:
            geoms.append(c.geom)

    intersection = reduce(lambda a, b: a.intersection(b), geoms)

    if intersection.is_empty:
        raise EmptyGeometryError("intersection did not return any geometry")

    return GeomCoverage(intersection, srs=srs, clip=clip)