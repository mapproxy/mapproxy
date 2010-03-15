# -*- coding: utf-8 -*-
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

"""
Spatial reference systems and transformation of coordinates.
"""
from __future__ import division

import math
from itertools import izip
from pyproj import Proj, transform

import logging
log = logging.getLogger(__name__)

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
        if epsg_code.lower().startswith('epsg:'):
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

_srs_cache = {}
def SRS(srs_code):
    srs_code = _clean_srs_code(srs_code)
    if srs_code in _srs_cache:
        return _srs_cache[srs_code]
    else:
        srs = _SRS(srs_code)
        _srs_cache[srs_code] = srs
        return srs

class _SRS(object):
    # http://trac.openlayers.org/wiki/SphericalMercator
    proj_init = {'EPSG:900913':
                    lambda:Proj('+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 '
                                '+lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m '
                                '+nadgrids=@null +no_defs'),
                 'CRS:84': lambda:Proj(init='epsg:4326'),
                }
    """
    This class represents a Spatial Reference System.
    """
    def __init__(self, srs_code):
        """
        Create a new SRS with the given `srs_code` code.
        """
        self.srs_code = srs_code
        
        init = _SRS.proj_init.get(srs_code, None)
        if init is None:
            epsg_num = get_epsg_num(srs_code)
            self.proj = Proj(init='epsg:%d' % epsg_num)
        else:
            self.proj = init()
    
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
        
        log.debug('transformed from %r to %r (%s -> %s)' % 
                  (self, other_srs, bbox, result))
        
        return result
    
    def align_bbox(self, bbox):
        """
        Align bbox to reasonable values to prevent errors in transformations.
        E.g. transformations from EPSG:4326 with lat=90 or -90 will fail, so
        we subtract a tiny delta.
        
        At the moment only EPSG:4326 bbox will be modifyed.
        
        >>> SRS(4326).align_bbox((-180, -90, 180, 90))
        (-180, -89.999999990000006, 180, 89.999999990000006)
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
    
    def __eq__(self, other):
        """
        >>> SRS(4326) == SRS("EpsG:4326")
        True
        >>> SRS(4326) == SRS("4326")
        True
        >>> SRS(4326) == SRS(900913)
        False
        """
        if isinstance(other, _SRS):
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
        """
        >>> print(SRS(4326))
        SRS EPSG:4326 ('+units=m +init=epsg:4326 ')
        """
        #pylint: disable-msg=E1101
        return "SRS %s ('%s')" % (self.srs_code, self.proj.srs)
    
    def __repr__(self):
        """
        >>> repr(SRS(4326))
        "SRS('EPSG:4326')"
        """
        return "SRS('%s')" % (self.srs_code,)


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
    cartesian coordinate systems.
    
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
