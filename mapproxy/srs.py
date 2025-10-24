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
from mapproxy.proj import USE_PROJ4_API
# Old Proj.4 API
from mapproxy.proj import Proj, transform, set_datapath
# New Proj API
from mapproxy.proj import CRS, Transformer
from mapproxy.config import base_config

import logging

from mapproxy.util.bbox import calculate_bbox

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
    >>> get_epsg_num('IGNF:ETRS89UTM28') is None
    True
    """
    if isinstance(epsg_code, str):
        if ':' in epsg_code and epsg_code.upper().startswith('EPSG'):
            epsg_code = int(epsg_code.split(':')[1])
        elif epsg_code.isdigit():
            epsg_code = int(epsg_code)
        else:
            return
    return epsg_code


def get_authority(srs_code):
    """
    >>> get_authority('IAU:1000')
    ('IAU', '1000')
    """
    if isinstance(srs_code, str) and ':' in srs_code:
        auth_name, auth_id = srs_code.rsplit(':', 1)
        return auth_name, auth_id


def _clean_srs_code(code):
    """
    >>> _clean_srs_code(4326)
    'EPSG:4326'
    >>> _clean_srs_code('31466')
    'EPSG:31466'
    >>> _clean_srs_code('crs:84')
    'CRS:84'
    """
    if isinstance(code, str) and ':' in code:
        return code.upper()
    else:
        return 'EPSG:' + str(code)


_proj_initialized = False


def _init_proj():
    global _proj_initialized
    if not _proj_initialized and 'proj_data_dir' in base_config().srs:
        proj_data_dir = base_config().srs['proj_data_dir']
        if proj_data_dir is None:
            _proj_initialized = True
            return
        log_system.info('loading proj data from %s', proj_data_dir)
        set_datapath(proj_data_dir)
        _proj_initialized = True


_thread_local = threading.local()


def SRS(srs_code):
    _init_proj()
    if isinstance(srs_code, _srs_impl):
        return srs_code

    srs_code = _clean_srs_code(srs_code)

    if not hasattr(_thread_local, 'srs_cache'):
        _thread_local.srs_cache = {}

    if srs_code in _thread_local.srs_cache:
        return _thread_local.srs_cache[srs_code]
    else:
        srs = _srs_impl(srs_code)
        _thread_local.srs_cache[srs_code] = srs
        return srs


WEBMERCATOR_EPSG = set(('EPSG:900913', 'EPSG:3857',
                        'EPSG:102100', 'EPSG:102113'))


class _SRS_Proj4_API(object):
    # http://trac.openlayers.org/wiki/SphericalMercator
    proj_init = {
        'EPSG:4326': lambda: Proj('+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs +over'),  # type: ignore
        'CRS:84': lambda: Proj('+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs +over'),  # type: ignore
    }
    for _epsg in WEBMERCATOR_EPSG:
        proj_init[_epsg] = lambda: Proj(  # type: ignore
            '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 '
            '+lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m '
            '+nadgrids=@null +no_defs +over')

    """
    This class represents a Spatial Reference System.

    Abstracts transformations between different projections.
    Uses the old Proj.4 API, either via pyproj 1 or c-types.
    """

    def __init__(self, srs_code):
        """
        Create a new SRS with the given `srs_code` code.
        """
        self.srs_code = srs_code

        init = self.proj_init.get(srs_code, None)
        if init is not None:
            self.proj = init()
        else:
            epsg_num = get_epsg_num(srs_code)
            if epsg_num is not None:
                self.proj = Proj(init='epsg:%d' % epsg_num)
            else:
                raise ValueError("the old Proj.4 API doesn't support non-EPSG authorities")

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
        return zip(transf_pts[0], transf_pts[1])

    def transform_bbox_to(self, other_srs, bbox, with_points=16):
        """

        :param with_points: the number of points to use for the transformation.
            A bbox transformation with only two or four points may cut off some
            parts due to distortions.

        >>> ['%.3f' % x for x in
        ...  SRS(4326).transform_bbox_to(SRS(3857), (-180.0, -90.0, 180.0, 90.0))]
        ['-20037508.343', '-147730762.670', '20037508.343', '147730758.195']
        >>> ['%.5f' % x for x in
        ...  SRS(4326).transform_bbox_to(SRS(3857), (8.2, 53.1, 8.3, 53.2))]
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

        log_proj.debug('transformed from %r to %r (%s -> %s)',
                       self, other_srs, bbox, result)

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
        # TODO should not be needed anymore since we transform with +over
        # still a few tests depend on the rounding behavior of this
        if self.srs_code == 'EPSG:4326':
            delta = 0.00000001
            (minx, miny, maxx, maxy) = bbox
            if abs(miny - -90.0) < 1e-6:
                miny = -90.0 + delta
            if abs(maxy - 90.0) < 1e-6:
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

    def get_geographic_srs(self):
        """ Return the "canonical" geographic CRS corresponding to this CRS.
            Always EPSG:4326 for Proj4 implementation """
        return SRS(4326)

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
        >>> SRS(4326) == SRS(3857)
        False
        """
        if isinstance(other, _SRS_Proj4_API):
            return self.proj.srs == other.proj.srs
        else:
            return NotImplemented

    def __ne__(self, other):
        """
        >>> SRS(3857) != SRS(3857)
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
        return "SRS %s ('%s')" % (self.srs_code, self.proj.srs)

    def __repr__(self):
        """
        >>> repr(SRS(4326))
        "SRS('EPSG:4326')"
        """
        return "SRS('%s')" % (self.srs_code,)

    def __hash__(self):
        return hash(self.srs_code)


class _SRS(object):
    """
    This class represents a Spatial Reference System.

    Abstracts transformations between different projections.
    Uses the new Proj API via pyproj >=2.
    """

    def __init__(self, srs_code):
        """
        Create a new SRS with the given `srs_code` code.
        """
        self.srs_code = srs_code

        if srs_code in WEBMERCATOR_EPSG:
            epsg_num = 3857
        elif srs_code == 'CRS:84':
            epsg_num = 4326
        else:
            epsg_num = get_epsg_num(srs_code)

        if epsg_num is not None:
            self.proj = CRS.from_epsg(epsg_num)
        else:
            auth_name, auth_id = get_authority(srs_code)
            self.proj = CRS.from_authority(auth_name, auth_id)

        self._transformers = {}

    def _transformer(self, other_srs):
        if other_srs in self._transformers:
            return self._transformers[other_srs]

        t = Transformer.from_crs(self.proj, other_srs.proj, always_xy=True)
        self._transformers[other_srs] = t
        return t

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

        transformer = self._transformer(other_srs)
        if isinstance(points[0], (int, float)) and 2 >= len(points) <= 3:
            return transformer.transform(*points)

        x = [p[0] for p in points]
        y = [p[1] for p in points]
        transf_pts = transformer.transform(x, y)
        return zip(transf_pts[0], transf_pts[1])

    def transform_bbox_to(self, other_srs, bbox, with_points=16):
        """

        :param with_points: the number of points to use for the transformation.
            A bbox transformation with only two or four points may cut off some
            parts due to distortions.

        >>> ['%.3f' % x for x in
        ...  SRS(4326).transform_bbox_to(SRS(3857), (-180.0, -90.0, 180.0, 90.0))]
        ['-20037508.343', '-20037508.343', '20037508.343', '20037508.343']
        >>> ['%.5f' % x for x in
        ...  SRS(4326).transform_bbox_to(SRS(3857), (8.2, 53.1, 8.3, 53.2))]
        ['912819.82450', '7001516.67745', '923951.77358', '7020078.53264']
        >>> SRS(4326).transform_bbox_to(SRS(4326), (8.25, 53.0, 8.5, 53.75))
        (8.25, 53.0, 8.5, 53.75)
        """
        if self == other_srs:
            return bbox
        bbox = bbox
        points = generate_envelope_points(bbox, with_points)
        transf_pts = list(self.transform_to(other_srs, points))
        result = calculate_bbox(transf_pts)

        log_proj.debug('transformed from %r to %r (%s -> %s)',
                       self, other_srs, bbox, result)

        # XXX: 3857 is only defined within 85.06 N/S, new Proj returns 'inf' for coords
        # outside of these bounds. Adjust bbox for 4326->3857 transformations to the old
        # behavior, as this is expected in a few places (WMS layer extents and quite a few
        # tests).
        if self.srs_code == 'EPSG:4326' and other_srs.srs_code in ('EPSG:3857', 'EPSG:900913'):
            minx, miny, maxx, maxy = result
            if bbox[0] <= -180.0:
                minx = -20037508.342789244
            if bbox[1] <= -85.06:
                miny = -20037508.342789244
            if bbox[2] >= 180.0:
                maxx = 20037508.342789244
            if bbox[3] >= 85.06:
                maxy = 20037508.342789244
            result = (minx, miny, maxx, maxy)
        return result

    @property
    def is_latlong(self):
        """
        >>> SRS(4326).is_latlong
        True
        >>> SRS(31466).is_latlong
        False
        """
        return self.proj.is_geographic

    def get_geographic_srs(self):
        """ Return the "canonical" geographic CRS corresponding to this CRS.
            EPSG:4326 for Earth CRS, or another one from other celestial bodies """
        auth = self.proj.to_authority()
        if auth is None or not auth[0].startswith('IAU'):
            ret = SRS(4326)
        else:
            return _SRS(':'.join(self.proj.geodetic_crs.to_authority()))
        return ret

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
        if self.srs_code == 'CRS:84':
            return False
        return self.proj.axis_info[0].direction == 'north'

    @property
    def is_axis_order_en(self):
        """
        Returns `True` if the axis order is East then North
        (i.e. x/y or lon/lat).
        """
        return not self.is_axis_order_ne

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
        # TODO should not be needed anymore since we transform with +over
        # still a few tests depend on the rounding behavior of this
        if self.srs_code == 'EPSG:4326':
            delta = 0.00000001
            (minx, miny, maxx, maxy) = bbox
            if abs(miny - -90.0) < 1e-6:
                miny = -90.0 + delta
            if abs(maxy - 90.0) < 1e-6:
                maxy = 90.0 - delta
            bbox = minx, miny, maxx, maxy
        return bbox

    def __eq__(self, other):
        """
        >>> SRS(4326) == SRS("EpsG:4326")
        True
        >>> SRS(4326) == SRS("4326")
        True
        >>> SRS(4326) == SRS(3857)
        False
        """
        if isinstance(other, _SRS):
            return self.proj.srs == other.proj.srs
        else:
            return NotImplemented

    def __ne__(self, other):
        """
        >>> SRS(3857) != SRS(3857)
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
        return "SRS %s ('%s')" % (self.srs_code, self.proj.srs)

    def __repr__(self):
        """
        >>> repr(SRS(4326))
        "SRS('EPSG:4326')"
        """
        return "SRS('%s')" % (self.srs_code,)

    def __hash__(self):
        return hash(self.srs_code)

    def to_ogc_url(self):
        """Return a OGC SRS URL like http://www.opengis.net/def/crs/AUTH_NAME/[VERSION]/CODE"""
        auth_name, code = self.srs_code.split(':')
        version = 0
        if auth_name == "OGC":
            version = "1.3"
            if code == "84":
                code = "CRS84"
        if auth_name.startswith("IAU_"):
            version = auth_name[4:]
            auth_name = "IAU"
        return f"http://www.opengis.net/def/crs/{auth_name}/{version}/{code}"

    def semi_major_meters(self):
        """Return the semi major axis in meters of the ellipsoid underlying this SRS"""
        return self.proj.ellipsoid.semi_major_metre


_srs_impl: type

if USE_PROJ4_API:
    _srs_impl = _SRS_Proj4_API
    del _SRS
else:
    _srs_impl = _SRS
    del _SRS_Proj4_API


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
    def func(x_y): return (dst_bbox[0] + (x_y[0] - src_bbox[0]) *
                           (dst_bbox[2]-dst_bbox[0]) / (src_bbox[2] - src_bbox[0]),
                           dst_bbox[1] + (src_bbox[3] - x_y[1]) *
                           (dst_bbox[3]-dst_bbox[1]) / (src_bbox[3] - src_bbox[1]))
    return func


class PreferredSrcSRS(object):
    def __init__(self):
        self.target_proj = {}

    def add(self, target, prefered_srs):
        self.target_proj[target] = prefered_srs

    def preferred_src(self, target, available_src):
        if not available_src:
            raise ValueError("no available src SRS")
        if target in available_src:
            return target
        if target in self.target_proj:
            for preferred in self.target_proj[target]:
                if preferred in available_src:
                    return preferred

        for avail in available_src:
            if avail.is_latlong == target.is_latlong:
                return avail
        return available_src[0]


class SupportedSRS(object):
    def __init__(self, supported_srs, preferred_srs=None):
        self.supported_srs = supported_srs
        self.preferred_srs = preferred_srs or PreferredSrcSRS()

    def __iter__(self):
        return iter(self.supported_srs)

    def __contains__(self, srs):
        return srs in self.supported_srs

    def best_srs(self, target):
        return self.preferred_srs.preferred_src(target, self.supported_srs)

    def __eq__(self, other):
        # .prefered_srs is set global, so we only compare .supported_srs
        return self.supported_srs == other.supported_srs


def ogc_crs_url_to_auth_code(url):
    """Convert a OGC CRS URL (http://www.opengis.net/def/crs/AUTH_NAME/[VERSION]/CODE) into 'AUTH_NAME:CODE'"""

    prefix = "http://www.opengis.net/def/crs/"
    if not url.startswith(prefix):
        raise ValueError(f'{url} is not a OGC CRS URL')

    auth_name, version, code = url[len(prefix):].split('/')
    if auth_name == "IAU":
        return auth_name + "_" + version + ":" + code
    return auth_name + ':' + code
