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

from __future__ import division, with_statement

import os
import json
import codecs
from functools import partial
from contextlib import closing

from mapproxy.grid import tile_grid
from mapproxy.compat import string_type, text_type

import logging
log_config = logging.getLogger('mapproxy.config.coverage')

try:
    import shapely.wkt
    import shapely.geometry
    import shapely.ops
    import shapely.prepared
    from shapely.geos import ReadingError
    geom_support = True
except ImportError:
    geom_support = False

class GeometryError(Exception):
    pass

class EmptyGeometryError(Exception):
    pass

class CoverageReadError(Exception):
    pass

def require_geom_support():
    if not geom_support:
        raise ImportError('Shapely required for geometry support')


def load_datasource(datasource, where=None):
    """
    Loads polygons from WKT text files or OGR datasources.

    Returns a list of Shapely Polygons.
    """
    # check if it is a  wkt or geojson file
    if os.path.exists(os.path.abspath(datasource)):
        with open(os.path.abspath(datasource), 'rb') as fp:
            data = fp.read(50)
        if data.lower().lstrip().startswith((b'polygon', b'multipolygon')):
            return load_polygons(datasource)
        # only load geojson directly if we don't have a filter
        if where is None and data and data.startswith(b'{'):
            return load_geojson(datasource)
    # otherwise pass to OGR
    return load_ogr_datasource(datasource, where=where)

def load_ogr_datasource(datasource, where=None):
    """
    Loads polygons from any OGR datasource.

    Returns a list of Shapely Polygons.
    """
    from mapproxy.util.ogr import OGRShapeReader, OGRShapeReaderError

    polygons = []
    try:
        with closing(OGRShapeReader(datasource)) as reader:
            for wkt in reader.wkts(where):
                if not isinstance(wkt, text_type):
                    wkt = wkt.decode()
                try:
                    geom = shapely.wkt.loads(wkt)
                except ReadingError as ex:
                    raise GeometryError(ex)
                if geom.type == 'Polygon':
                    polygons.append(geom)
                elif geom.type == 'MultiPolygon':
                    for p in geom:
                        polygons.append(p)
                else:
                    log_config.warn('skipping %s geometry from %s: not a Polygon/MultiPolygon',
                        geom.type, datasource)
    except OGRShapeReaderError as ex:
        raise CoverageReadError(ex)

    return polygons

def load_polygons(geom_files):
    """
    Loads WKT polygons from one or more text files.

    Returns a list of Shapely Polygons.
    """
    polygons = []
    if isinstance(geom_files, string_type):
        geom_files = [geom_files]

    for geom_file in geom_files:
        # open with utf-8-sig encoding to get rid of UTF8 BOM from MS Notepad
        with codecs.open(geom_file, encoding='utf-8-sig') as f:
            polygons.extend(load_polygon_lines(f, source=geom_files))

    return polygons

def load_geojson(datasource):
    with open(datasource) as f:
        geojson = json.load(f)
        t = geojson.get('type')
        if not t:
            raise CoverageReadError("not a GeoJSON")
        geometries = []
        if t == 'FeatureCollection':
            for f in geojson.get('features'):
                geom = f.get('geometry')
                if geom:
                    geometries.append(geom)
        elif t == 'Feature':
            if 'geometry' in geojson:
                geometries.append(geojson['geometry'])
        elif t in ('Polygon', 'MultiPolygon'):
            geometries.append(geojson)
        else:
            log_config.warn('skipping feature of type %s from %s: not a Polygon/MultiPolygon',
                        t, datasource)

    polygons = []
    for geom in geometries:
        geom = shapely.geometry.asShape(geom)
        if geom.type == 'Polygon':
            polygons.append(geom)
        elif geom.type == 'MultiPolygon':
            for p in geom:
                polygons.append(p)
        else:
            log_config.warn('ignoring non-polygon geometry (%s) from %s',
                geom.type, datasource)

    return polygons

def load_polygon_lines(line_iter, source='<string>'):
    polygons = []
    for line in line_iter:
        if not line.strip():
            continue
        geom = shapely.wkt.loads(line)
        if geom.type == 'Polygon':
            polygons.append(geom)
        elif geom.type == 'MultiPolygon':
            for p in geom:
                polygons.append(p)
        else:
            log_config.warn('ignoring non-polygon geometry (%s) from %s',
                geom.type, source)

    return polygons

def build_multipolygon(polygons, simplify=False):
    if not polygons:
        p = shapely.geometry.Polygon()
        return p.bounds, p

    if len(polygons) == 1:
        geom = polygons[0]
        if simplify:
            geom = simplify_geom(geom)
        return geom.bounds, geom

    if simplify:
        polygons = [simplify_geom(g) for g in polygons]

    # eliminate any self-overlaps
    mp = shapely.ops.cascaded_union(polygons)

    return mp.bounds, mp

def simplify_geom(geom):
    bounds = geom.bounds
    if not bounds:
        raise EmptyGeometryError('Empty geometry given')
    w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
    tolerance = min((w/1e6, h/1e6))
    geom = geom.simplify(tolerance, preserve_topology=True)
    if not geom.is_valid:
        geom = geom.buffer(0)
    return geom

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
        result = transform_polygon(transf, geometry)
    elif geometry.type == 'MultiPolygon':
        result = transform_multipolygon(transf, geometry)
    else:
        raise ValueError('cannot transform %s' % geometry.type)

    if not result.is_valid:
        result = result.buffer(0)
    return result

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
    return list(from_srs.transform_to(to_srs, list(zip(*xy))))

def flatten_to_polygons(geometry):
    """
    Return a list of all polygons of this (multi)`geometry`.
    """
    if geometry.type == 'Polygon':
        return [geometry]

    if geometry.type == 'MultiPolygon':
        return list(geometry)

    if hasattr(geometry, 'geoms'):
        # GeometryCollection or MultiLineString? return list of all polygons
        geoms = []
        for part in geometry.geoms:
            if part.type == 'Polygon':
                geoms.append(part)

        if geoms:
            return geoms

    return []

def load_expire_tiles(expire_dir, grid=None):
    if grid is None:
        grid = tile_grid(3857, origin='nw')
    tiles = set()

    def parse(filename):
        with open(filename) as f:
            try:
                for line in f:
                    if not line:
                        continue
                    tile = tuple(map(int, line.split('/')))
                    tiles.add(tile)
            except:
                log_config.warn('found error in %s, skipping rest of file', filename)

    if os.path.isdir(expire_dir):
        for root, dirs, files in os.walk(expire_dir):
            for name in files:
                filename = os.path.join(root, name)
                parse(filename)
    else:
        parse(expire_dir)

    boxes = []
    for tile in tiles:
        z, x, y = tile
        boxes.append(shapely.geometry.box(*grid.tile_bbox((x, y, z))))

    return boxes
