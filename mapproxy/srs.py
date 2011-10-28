# -*- coding: utf-8 -*-
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
Spatial reference systems and transformation of coordinates.
"""
from __future__ import division

import math
import threading
from itertools import izip
from mapproxy.proj import Proj, transform, set_datapath, ProjInitError
from mapproxy.config import base_config

import logging
log_system = logging.getLogger('mapproxy.system')
log_proj = logging.getLogger('mapproxy.proj')

def get_epsg_num(epsg_code):
    """
    >>> get_epsg_num('ePsG:4326')
    4326
    >>> get_epsg_num(4313)
    4313
    >>> get_epsg_num('31466')
    31466
    """
    if isinstance(epsg_code, basestring):
        if ':' in epsg_code:
            epsg_code = int(epsg_code.split(':')[1])
        else:
            epsg_code = int(epsg_code)
    return epsg_code

def _clean_srs_code(code):
    """
    >>> _clean_srs_code(4326)
    'EPSG:4326'
    >>> _clean_srs_code('31466')
    'EPSG:31466'
    >>> _clean_srs_code('crs:84')
    'CRS:84'
    """
    if isinstance(code, basestring) and ':' in code:
        return code.upper()
    else:
        return 'EPSG:' + str(code)

class TransformationError(Exception):
    pass

_proj_initalized = False
def _init_proj():
    global _proj_initalized
    if not _proj_initalized and 'proj_data_dir' in base_config().srs:
        proj_data_dir = base_config().srs['proj_data_dir']
        log_system.info('loading proj data from %s', proj_data_dir)
        set_datapath(proj_data_dir)
        _proj_initalized = True

_thread_local = threading.local()
def SRS(srs_code):
    _init_proj()
    if isinstance(srs_code, _SRS):
        return srs_code
    
    srs_code = _clean_srs_code(srs_code)
    
    if not hasattr(_thread_local, 'srs_cache'):
        _thread_local.srs_cache = {}
    
    if srs_code in _thread_local.srs_cache:
        return _thread_local.srs_cache[srs_code]
    else:
        srs = _SRS(srs_code)
        _thread_local.srs_cache[srs_code] = srs
        return srs

def epsg900913():
    try:
        return Proj(proj_def='''PROJCS["Google Mercator", 
       GEOGCS["WGS 84", 
         DATUM["World Geodetic System 1984", 
           SPHEROID["WGS 84", 6378137.0, 298.257223563, AUTHORITY["EPSG","7030"]], 
           AUTHORITY["EPSG","6326"]], 
         PRIMEM["Greenwich", 0.0, AUTHORITY["EPSG","8901"]], 
         UNIT["degree", 0.017453292519943295], 
         AXIS["Geodetic latitude", NORTH], 
         AXIS["Geodetic longitude", EAST], 
         AUTHORITY["EPSG","4326"]], 
       PROJECTION["Mercator (1SP)", AUTHORITY["EPSG","9804"]], 
       PARAMETER["semi_major", 6378137.0], 
       PARAMETER["semi_minor", 6378137.0], 
       PARAMETER["latitude_of_origin", 0.0], 
       PARAMETER["central_meridian", 0.0], 
       PARAMETER["scale_factor", 1.0], 
       PARAMETER["false_easting", 0.0], 
       PARAMETER["false_northing", 0.0], 
       UNIT["m", 1.0], 
       AXIS["Easting", EAST], 
       AXIS["Northing", NORTH], 
       AUTHORITY["EPSG","900913"]]''')
    except RuntimeError:
        return Proj('+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 '
                '+lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m '
                '+nadgrids=@null +no_defs')

WEBMERCATOR_EPSG = set(('EPSG:900913', 'EPSG:3857',
    'EPSG:102100', 'EPSG:102113'))

class _SRS(object):
    # http://trac.openlayers.org/wiki/SphericalMercator
    # TODO jproj/libproj
    proj_init = {
                 'CRS:84': lambda: Proj(init='epsg:4326'),
                }
    for _epsg in WEBMERCATOR_EPSG:
        proj_init[_epsg] = epsg900913
        
    """
    This class represents a Spatial Reference System.
    """
    def __init__(self, srs_code):
        """
        Create a new SRS with the given `srs_code` code.
        """
        self.srs_code = srs_code
        
        try:
            epsg_num = get_epsg_num(srs_code)   
            self.proj = Proj(init='epsg:%d' % epsg_num)
        except (ProjInitError, RuntimeError), ex:
            init = _SRS.proj_init.get(srs_code, None)
            if init is not None:
                self.proj = init()
            else:
                raise ex
    
    def transform_to(self, other_srs, points):
        """
        :type points: ``(x, y)`` or ``[(x1, y1), (x2, y2), …]``
        
        >>> srs1 = SRS(4326)
        >>> srs2 = SRS(900913)
        >>> [str(round(x, 5)) for x in srs1.transform_to(srs2, (8.22, 53.15))]
        ['915046.21432', '7010792.20171']
        >>> srs1.transform_to(srs1, (8.25, 53.5))
        (8.25, 53.5)
        >>> [(str(round(x, 5)), str(round(y, 5))) for x, y in
        ...  srs1.transform_to(srs2, [(8.2, 53.1), (8.22, 53.15), (8.3, 53.2)])]
        ... #doctest: +NORMALIZE_WHITESPACE
        [('912819.8245', '7001516.67745'),
         ('915046.21432', '7010792.20171'),
         ('923951.77358', '7020078.53264')]
        """
        if self == other_srs:
            return points
        if isinstance(points[0], (int, float)) and 2 >= len(points) <= 3:
            return transform(self.proj, other_srs.proj, *points)
        
        x = [p[0] for p in points]
        y = [p[1] for p in points]
        transf_pts = transform(self.proj, other_srs.proj, x, y)
        return izip(transf_pts[0], transf_pts[1])
    
    def transform_bbox_to(self, other_srs, bbox, with_points=16):
        """
        
        :param with_points: the number of points to use for the transformation.
            A bbox transformation with only two or four points may cut off some
            parts due to distortions.

        >>> ['%.3f' % x for x in
        ...  SRS(4326).transform_bbox_to(SRS(900913), (-180.0, -90.0, 180.0, 90.0))]
        ['-20037508.343', '-147730762.670', '20037508.343', '147730758.195']
        >>> ['%.5f' % x for x in
        ...  SRS(4326).transform_bbox_to(SRS(900913), (8.2, 53.1, 8.3, 53.2))]
        ['912819.82450', '7001516.67745', '923951.77358', '7020078.53264']
        >>> SRS(4326).transform_bbox_to(SRS(4326), (8.25, 53.0, 8.5, 53.75))
        (8.25, 53.0, 8.5, 53.75)
        """
        if self == other_srs:
            return bbox
        bbox = self.align_bbox(bbox)
        points = generate_envelope_points(bbox, with_points)
        transf_pts = self.transform_to(other_srs, points)
        result = calculate_bbox(transf_pts)
        
        log_proj.debug('transformed from %r to %r (%s -> %s)' % 
                  (self, other_srs, bbox, result))
        
        return result
    
    def align_bbox(self, bbox):
        """
        Align bbox to reasonable values to prevent errors in transformations.
        E.g. transformations from EPSG:4326 with lat=90 or -90 will fail, so
        we subtract a tiny delta.
        
        At the moment only EPSG:4326 bbox will be modifyed.
        
        >>> bbox = SRS(4326).align_bbox((-180, -90, 180, 90))
        >>> -90 < bbox[1] < -89.99999998
        True
        >>> 90 > bbox[3] > 89.99999998
        True
        """
        if self.srs_code == 'EPSG:4326':
            delta = 0.00000001
            (minx, miny, maxx, maxy) = bbox
            if miny <= -90.0:
                miny = -90.0 + delta
            if maxy >= 90.0:
                maxy = 90.0 - delta
            bbox = minx, miny, maxx, maxy
        return bbox
    
    @property
    def is_latlong(self):
        """
        >>> SRS(4326).is_latlong
        True
        >>> SRS(31466).is_latlong
        False
        """
        return self.proj.is_latlong()
    
    @property
    def is_axis_order_ne(self):
        """
        Returns `True` if the axis order is North, then East
        (i.e. y/x or lat/lon).
        
        >>> SRS(4326).is_axis_order_ne
        True
        >>> SRS('CRS:84').is_axis_order_ne
        False
        >>> SRS(31468).is_axis_order_ne
        True
        >>> SRS(31463).is_axis_order_ne
        False
        >>> SRS(25831).is_axis_order_ne
        False
        """
        if self.srs_code in base_config().srs.axis_order_ne:
            return True
        if self.srs_code in base_config().srs.axis_order_en:
            return False
        if self.is_latlong:
            return True
        return False
    
    @property
    def is_axis_order_en(self):
        """
        Returns `True` if the axis order is East then North
        (i.e. x/y or lon/lat).
        """
        return not self.is_axis_order_ne
    
    def __eq__(self, other):
        """
        >>> SRS(4326) == SRS("EpsG:4326")
        True
        >>> SRS(4326) == SRS("4326")
        True
        >>> SRS(4326) == SRS(900913)
        False
        >>> SRS(3857) == SRS(900913)
        True
        >>> SRS(900913) == SRS(3857)
        True

        """
        if isinstance(other, _SRS):
            if (self.srs_code in WEBMERCATOR_EPSG
                and other.srs_code in WEBMERCATOR_EPSG):
                return True
            return self.proj.srs == other.proj.srs
        else:
            return NotImplemented
    def __ne__(self, other):
        """
        >>> SRS(900913) != SRS(900913)
        False
        >>> SRS(4326) != SRS(900913)
        True
        """
        equal_result = self.__eq__(other)
        if equal_result is NotImplemented:
            return NotImplemented
        else:
            return not equal_result
    def __str__(self):
        #pylint: disable-msg=E1101
        return "SRS %s ('%s')" % (self.srs_code, self.proj.srs)
    
    def __repr__(self):
        """
        >>> repr(SRS(4326))
        "SRS('EPSG:4326')"
        """
        return "SRS('%s')" % (self.srs_code,)
    
    def __hash__(self):
        return hash(self.srs_code)


def generate_envelope_points(bbox, n):
    """
    Generates points that form a linestring around a given bbox.
    
    @param bbox: bbox to generate linestring for
    @param n: the number of points to generate around the bbox
    
    >>> generate_envelope_points((10.0, 5.0, 20.0, 15.0), 4)
    [(10.0, 5.0), (20.0, 5.0), (20.0, 15.0), (10.0, 15.0)]
    >>> generate_envelope_points((10.0, 5.0, 20.0, 15.0), 8)
    ... #doctest: +NORMALIZE_WHITESPACE
    [(10.0, 5.0), (15.0, 5.0), (20.0, 5.0), (20.0, 10.0),\
     (20.0, 15.0), (15.0, 15.0), (10.0, 15.0), (10.0, 10.0)]
    """
    (minx, miny, maxx, maxy) = bbox
    if n <= 4:
        n = 0
    else:
        n = int(math.ceil((n - 4) / 4.0))
    
    width = maxx - minx
    height = maxy - miny
    
    minx, maxx = min(minx, maxx), max(minx, maxx)
    miny, maxy = min(miny, maxy), max(miny, maxy)
    
    n += 1
    xstep = width / n
    ystep = height / n
    result = []
    for i in range(n+1):
        result.append((minx + i*xstep, miny))
    for i in range(1, n):
        result.append((maxx, miny + i*ystep))
    for i in range(n, -1, -1):
        result.append((minx + i*xstep, maxy))
    for i in range(n-1, 0, -1):
        result.append((minx, miny + i*ystep))
    return result
    
def calculate_bbox(points):
    """
    Calculates the bbox of a list of points.
    
    >>> calculate_bbox([(-5, 20), (3, 8), (99, 0)])
    (-5, 0, 99, 20)
    
    @param points: list of points [(x0, y0), (x1, y2), ...]
    @returns: bbox of the input points.
    """
    points = list(points)
    # points can be INF for invalid transformations, filter out
    # INF is not portable for <2.6 so we check against a large value
    MAX = 1e300
    try:
        minx = min(p[0] for p in points if p[0] <= MAX)
        miny = min(p[1] for p in points if p[1] <= MAX)
        maxx = max(p[0] for p in points if p[0] <= MAX)
        maxy = max(p[1] for p in points if p[1] <= MAX)
        return (minx, miny, maxx, maxy)
    except ValueError: # everything is INF
        raise TransformationError()
        
def merge_bbox(bbox1, bbox2):
    """
    Merge two bboxes.
    
    >>> merge_bbox((-10, 20, 0, 30), (30, -20, 90, 10))
    (-10, -20, 90, 30)
    
    """
    minx = min(bbox1[0], bbox2[0])
    miny = min(bbox1[1], bbox2[1])
    maxx = max(bbox1[2], bbox2[2])
    maxy = max(bbox1[3], bbox2[3])
    return (minx, miny, maxx, maxy)

def bbox_equals(src_bbox, dst_bbox, x_delta, y_delta=None):
    """
    Compares two bbox and checks if they are equal, or nearly equal.
    
    :param x_delta: how precise the comparison should be.
                    should be reasonable small, like a tenth of a pixle
    :type x_delta: bbox units
    
    >>> src_bbox = (939258.20356824622, 6887893.4928338043, 
    ...             1095801.2374962866, 7044436.5267618448)
    >>> dst_bbox = (939258.20260000182, 6887893.4908000007,
    ...             1095801.2365000017, 7044436.5247000009)
    >>> bbox_equals(src_bbox, dst_bbox, 61.1, 61.1)
    True
    >>> bbox_equals(src_bbox, dst_bbox, 0.0001)
    False
    """
    if y_delta is None:
        y_delta = x_delta
    return (abs(src_bbox[0] - dst_bbox[0]) < x_delta and
            abs(src_bbox[1] - dst_bbox[1]) < x_delta and
            abs(src_bbox[2] - dst_bbox[2]) < y_delta and
            abs(src_bbox[3] - dst_bbox[3]) < y_delta)


def make_lin_transf(src_bbox, dst_bbox):
    """
    Create a transformation function that transforms linear between two
    plane coordinate systems.
    One needs to be cartesian (0, 0 at the lower left, x goes up) and one
    needs to be an image coordinate system (0, 0 at the top left, x goes down).
    
    :return: function that takes src x/y and returns dest x/y coordinates
    
    >>> transf = make_lin_transf((7, 50, 8, 51), (0, 0, 500, 400))
    >>> transf((7.5, 50.5))
    (250.0, 200.0)
    >>> transf((7.0, 50.0))
    (0.0, 400.0)
    >>> transf = make_lin_transf((7, 50, 8, 51), (200, 300, 700, 700))
    >>> transf((7.5, 50.5))
    (450.0, 500.0)
    """
    func = lambda (x, y): (dst_bbox[0] + (x - src_bbox[0]) *
                           (dst_bbox[2]-dst_bbox[0]) / (src_bbox[2] - src_bbox[0]),
                           dst_bbox[1] + (src_bbox[3] - y) * 
                           (dst_bbox[3]-dst_bbox[1]) / (src_bbox[3] - src_bbox[1]))
    return func
