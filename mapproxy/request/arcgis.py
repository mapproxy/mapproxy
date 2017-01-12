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

from functools import partial as fp
from mapproxy.compat import string_type
from mapproxy.compat.modules import urlparse
from mapproxy.request.base import RequestParams, BaseRequest
from mapproxy.srs import make_lin_transf

class ArcGISExportRequestParams(RequestParams):
    """
    Supported params f, bbox(required), size, dpi, imageSR, bboxSR, format, layerDefs,
    layers, transparent, time, layerTimeOptions.

    @param layers: Determines which layers appear on the exported map. There are
                   four ways to specify layers: show, hide, include, exclude.
                   (ex show:1,2)
    """
    def _get_format(self):
        """
        The requested format as string (w/o any 'image/', 'text/', etc prefixes)
        """
        return self["format"]
    def _set_format(self, format):
        self["format"] = format.rsplit("/")[-1]
    format = property(_get_format, _set_format)
    del _get_format
    del _set_format

    def _get_bbox(self):
        """
        ``bbox`` as a tuple (minx, miny, maxx, maxy).
        """
        if 'bbox' not in self.params or self.params['bbox'] is None:
            return None
        points = [float(val) for val in self.params['bbox'].split(',')]
        return tuple(points[:4])
    def _set_bbox(self, value):
        if value is not None and not isinstance(value, string_type):
            value = ','.join(str(x) for x in value)
        self['bbox'] = value
    bbox = property(_get_bbox, _set_bbox)
    del _get_bbox
    del _set_bbox

    def _get_size(self):
        """
        Size of the request in pixel as a tuple (width, height),
        or None if one is missing.
        """
        if 'size' not in self.params or self.params['size'] is None:
            return None
        dim = [float(val) for val in self.params['size'].split(',')]
        return tuple(dim[:2])
    def _set_size(self, value):
        if value is not None and not isinstance(value, string_type):
            value = ','.join(str(x) for x in value)
        self['size'] = value
    size = property(_get_size, _set_size)
    del _get_size
    del _set_size

    def _get_srs(self, key):
        return self.params.get(key, None)
    def _set_srs(self, srs, key):
        if hasattr(srs, 'srs_code'):
            code = srs.srs_code
        else:
            code = srs
        self.params[key] = code.rsplit(":", 1)[-1]

    bboxSR = property(fp(_get_srs, key="bboxSR"), fp(_set_srs, key="bboxSR"))
    imageSR = property(fp(_get_srs, key="imageSR"), fp(_set_srs, key="imageSR"))
    del _get_srs
    del _set_srs



class ArcGISIdentifyRequestParams(ArcGISExportRequestParams):
    def _get_format(self):
        """
        The requested format as string (w/o any 'image/', 'text/', etc prefixes)
        """
        return self["format"]
    def _set_format(self, format):
        self["format"] = format.rsplit("/")[-1]
    format = property(_get_format, _set_format)
    del _get_format
    del _set_format

    def _get_bbox(self):
        """
        ``bbox`` as a tuple (minx, miny, maxx, maxy).
        """
        if 'mapExtent' not in self.params or self.params['mapExtent'] is None:
            return None
        points = [float(val) for val in self.params['mapExtent'].split(',')]
        return tuple(points[:4])
    def _set_bbox(self, value):
        if value is not None and not isinstance(value, string_type):
            value = ','.join(str(x) for x in value)
        self['mapExtent'] = value
    bbox = property(_get_bbox, _set_bbox)
    del _get_bbox
    del _set_bbox

    def _get_size(self):
        """
        Size of the request in pixel as a tuple (width, height),
        or None if one is missing.
        """
        if 'imageDisplay' not in self.params or self.params['imageDisplay'] is None:
            return None
        dim = [float(val) for val in self.params['imageDisplay'].split(',')]
        return tuple(dim[:2])
    def _set_size(self, value):
        if value is not None and not isinstance(value, string_type):
            value = ','.join(str(x) for x in value) + ',96'
        self['imageDisplay'] = value
    size = property(_get_size, _set_size)
    del _get_size
    del _set_size

    def _get_pos(self):
        size = self.size
        vals = self['geometry'].split(',')
        x, y = float(vals[0]), float(vals[1])
        return make_lin_transf(self.bbox, (0, 0, size[0], size[1]))((x, y))

    def _set_pos(self, value):
        size = self.size
        req_coord = make_lin_transf((0, 0, size[0], size[1]), self.bbox)(value)
        self['geometry'] = '%f,%f' % req_coord
    pos = property(_get_pos, _set_pos)
    del _get_pos
    del _set_pos

    @property
    def srs(self):
        srs = self.params.get('sr', None)
        if srs:
            return 'EPSG:%s' % srs

    @srs.setter
    def srs(self, srs):
        if hasattr(srs, 'srs_code'):
            code = srs.srs_code
        else:
            code = srs
        self.params['sr'] = code.rsplit(':', 1)[-1]

class ArcGISRequest(BaseRequest):
    request_params = ArcGISExportRequestParams
    fixed_params = {"f": "image"}

    def __init__(self, param=None, url='', validate=False, http=None):
        BaseRequest.__init__(self, param, url, validate, http)

        self.url = rest_endpoint(url)

    def copy(self):
        return self.__class__(param=self.params.copy(), url=self.url)

    @property
    def query_string(self):
        params = self.params.copy()
        for key, value in self.fixed_params.items():
            params[key] = value
        return params.query_string


class ArcGISIdentifyRequest(BaseRequest):
    request_params = ArcGISIdentifyRequestParams
    fixed_params = {'geometryType': 'esriGeometryPoint'}
    def __init__(self, param=None, url='', validate=False, http=None):
        BaseRequest.__init__(self, param, url, validate, http)

        self.url = rest_identify_endpoint(url)

    def copy(self):
        return self.__class__(param=self.params.copy(), url=self.url)

    @property
    def query_string(self):
        params = self.params.copy()
        for key, value in self.fixed_params.items():
            params[key] = value
        return params.query_string



def create_identify_request(req_data, param):
    req_data = req_data.copy()

    # Pop the URL off the request data.
    url = req_data['url']
    del req_data['url']

    return ArcGISIdentifyRequest(url=url, param=req_data)

def create_request(req_data, param):
    req_data = req_data.copy()

    # Pop the URL off the request data.
    url = req_data['url']
    del req_data['url']

    if 'format' in param:
        req_data['format'] = param['format']

    if 'transparent' in req_data:
        # Convert boolean to a string.
        req_data['transparent'] = str(req_data['transparent'])

    return ArcGISRequest(url=url, param=req_data)


def rest_endpoint(url):
    parts = urlparse.urlsplit(url)
    path = parts.path.rstrip('/').split('/')

    if path[-1] in ('export', 'exportImage'):
        if path[-2] == 'MapServer':
            path[-1] = 'export'
        elif path[-2] == 'ImageServer':
            path[-1] = 'exportImage'
    elif path[-1] == 'MapServer':
        path.append('export')
    elif path[-1] == 'ImageServer':
        path.append('exportImage')

    parts = parts[0], parts[1], '/'.join(path), parts[3], parts[4]
    return urlparse.urlunsplit(parts)


def rest_identify_endpoint(url):
    parts = urlparse.urlsplit(url)
    path = parts.path.rstrip('/').split('/')

    if path[-1] in ('export', 'exportImage'):
        path[-1] = 'identify'
    elif path[-1] in ('MapServer', 'ImageServer'):
        path.append('identify')

    parts = parts[0], parts[1], '/'.join(path), parts[3], parts[4]
    return urlparse.urlunsplit(parts)

