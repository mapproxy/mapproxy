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

from __future__ import division, with_statement
from functools import partial
import operator

from mapproxy.layer import MapExtent

try:
    import shapely.wkt
    import shapely.geometry
    import shapely.ops
    import shapely.prepared
    geom_support = True
except ImportError:
    geom_support = False

def require_geom_support():
    if not geom_support:
        raise ImportError('Shapely required for geometry support')

from mapproxy.grid import bbox_intersects, bbox_contains
from mapproxy.util import cached_property

def load_datasource(datasource, where=None):
    """
    Loads polygons from any OGR datasource.
    
    Returns the bbox and a Shapely MultiPolygon with
    the loaded geometries.
    """
    from mapproxy.util.ogr import OGRShapeReader
    
    polygons = []
    for wkt in OGRShapeReader(datasource).wkts(where):
        polygons.append(shapely.wkt.loads(wkt))
        
    mp = shapely.geometry.MultiPolygon(polygons)
    mp = simplify_geom(mp)
    return mp.bounds, mp

def load_polygons(geom_files):
    """
    Loads WKT polygons from one or more text files.
    
    Returns the bbox and a Shapely MultiPolygon with
    the loaded geometries.
    """
    polygons = []
    if isinstance(geom_files, basestring):
        geom_files = [geom_files]
    
    for geom_file in geom_files:
        with open(geom_file) as f:
            for line in f:
                geom = shapely.wkt.loads(line)
                if geom.type != 'Polygon':
                    print 'ignoring non-polygon geometry (%s) from %s' % \
                        (geom.type, geom_file)
                else:
                    polygons.append(geom)
    
    mp = shapely.geometry.MultiPolygon(polygons)
    mp = simplify_geom(mp)
    return mp.bounds, mp

def simplify_geom(geom):
    bounds = geom.bounds
    w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
    tolerance = min((w/1e5, h/1e5))
    return geom.simplify(tolerance, preserve_topology=False)

def bbox_polygon(bbox):
    """
    Create Polygon that covers the given bbox.
    """
    return shapely.geometry.Polygon((
        (bbox[0], bbox[1]),
        (bbox[2], bbox[1]),
        (bbox[2], bbox[3]),
        (bbox[0], bbox[3]),
        ))

def transform_geometry(from_srs, to_srs, geometry):
    transf = partial(transform_xy, from_srs, to_srs)
    
    if geometry.type == 'Polygon':
        return transform_polygon(transf, geometry)
    
    if geometry.type == 'MultiPolygon':
        return transform_multipolygon(transf, geometry)
    
    raise ValueError('cannot transform %s' % geometry.type)

def transform_polygon(transf, polygon):
    ext = transf(polygon.exterior.xy)
    ints = [transf(ring.xy) for ring in polygon.interiors]
    return shapely.geometry.Polygon(ext, ints)

def transform_multipolygon(transf, multipolygon):
    transformed_polygons = []
    for polygon in multipolygon:
        transformed_polygons.append(transform_polygon(transf, polygon))
    return shapely.geometry.MultiPolygon(transformed_polygons)

def transform_xy(from_srs, to_srs, xy):
    return list(from_srs.transform_to(to_srs, zip(*xy)))


def coverage(geom, srs):
    if isinstance(geom, (list, tuple)):
        return BBOXCoverage(geom, srs)
    else:
        return GeomCoverage(geom, srs)

class MultiCoverage(object):
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
    
    def __repr__(self):
        return '<MultiCoverage %r: %r>' % (self.extent.llbbox, self.coverages)

class BBOXCoverage(object):
    def __init__(self, bbox, srs):
        self.bbox = bbox
        self.srs = srs
        self.geom = None
    
    @property
    def extent(self):
        return MapExtent(self.bbox, self.srs)
    
    def _bbox_in_coverage_srs(self, bbox, srs):
        if srs != self.srs:
            bbox = srs.transform_bbox_to(self.srs, bbox)
        return bbox
    
    def intersects(self, bbox, srs):
        bbox = self._bbox_in_coverage_srs(bbox, srs)
        return bbox_intersects(self.bbox, bbox)
    
    def contains(self, bbox, srs):
        bbox = self._bbox_in_coverage_srs(bbox, srs)
        return bbox_contains(self.bbox, bbox)
    
    def transform_to(self, srs):
        if srs == self.srs:
            return self
        
        bbox = self.srs.transform_bbox_to(srs, self.bbox)
        return BBOXCoverage(bbox, srs)
    
    def __repr__(self):
        return '<BBOXCoverage %r/%r>' % (self.extent.llbbox, self.bbox)


class GeomCoverage(object):
    def __init__(self, geom, srs):
        self.geom = geom
        self.bbox = geom.bounds
        self.srs = srs
        self._prepared_geom = shapely.prepared.prep(geom)
        self._prepared_counter = 0
        self._prepared_max = 10000
    
    @property
    def extent(self):
        return MapExtent(self.bbox, self.srs)
    
    @property
    def prepared_geom(self):
        # GEOS internal data structure for prepared geometries grows over time,
        # recreate to limit memory consumption
        if self._prepared_counter > self._prepared_max:
            self._prepared_geom = shapely.prepared.prep(self.geom)
            self._prepared_counter = 0
        self._prepared_counter += 1
        return self._prepared_geom
    
    def _bbox_poly_in_coverage_srs(self, bbox, srs):
        if isinstance(bbox, shapely.geometry.base.BaseGeometry):
            if srs != self.srs:
                bbox = transform_geometry(srs, self.srs, bbox)
        else:
            if srs != self.srs:
                bbox = srs.transform_bbox_to(self.srs, bbox)
            bbox = bbox_polygon(bbox)
        return bbox
    
    def transform_to(self, srs):
        if srs == self.srs:
            return self
        
        geom = transform_geometry(self.srs, srs, self.geom)
        return GeomCoverage(geom, srs)
    
    def intersects(self, bbox, srs):
        bbox = self._bbox_poly_in_coverage_srs(bbox, srs)
        return self.prepared_geom.intersects(bbox)
    
    def contains(self, bbox, srs):
        bbox = self._bbox_poly_in_coverage_srs(bbox, srs)
        return self.prepared_geom.contains(bbox)
    
    def __repr__(self):
        return '<GeomCoverage %r: %r>' % (self.extent.llbbox, self.geom)

    