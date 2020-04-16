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
Service requests (parsing, handling, etc).
"""
import codecs
from mapproxy.request.wms import exception
from mapproxy.exception import RequestError
from mapproxy.srs import SRS, make_lin_transf
from mapproxy.request.base import RequestParams, BaseRequest, split_mime_type
from mapproxy.compat import string_type, iteritems

import logging
log = logging.getLogger(__name__)

class WMSMapRequestParams(RequestParams):
    """
    This class represents key-value parameters for WMS map requests.

    All values can be accessed as a property.
    Some properties return processed values. ``size`` returns a tuple of the width
    and height, ``layers`` returns an iterator of all layers, etc.

    """
    def _get_layers(self):
        """
        List with all layer names.
        """
        return sum((layers.split(',') for layers in self.params.get_all('layers')), [])
    def _set_layers(self, layers):
        if isinstance(layers, (list, tuple)):
            layers = ','.join(layers)
        self.params['layers'] = layers
    layers = property(_get_layers, _set_layers)
    del _get_layers
    del _set_layers

    def _get_bbox(self):
        """
        ``bbox`` as a tuple (minx, miny, maxx, maxy).
        """
        if 'bbox' not in self.params or self.params['bbox'] is None:
            return None
        points = map(float, self.params['bbox'].split(','))
        return tuple(points)

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
        if 'height' not in self or 'width' not in self:
            return None
        width = int(float(self.params['width'])) # allow float sizes (100.0), but truncate decimals
        height = int(float(self.params['height']))
        return (width, height)
    def _set_size(self, value):
        self['width'] = str(value[0])
        self['height'] = str(value[1])
    size = property(_get_size, _set_size)
    del _get_size
    del _set_size

    def _get_srs(self):
        return self.params.get('srs', None)
    def _set_srs(self, srs):
        if hasattr(srs, 'srs_code'):
            self.params['srs'] = srs.srs_code
        else:
            self.params['srs'] = srs

    srs = property(_get_srs, _set_srs)
    del _get_srs
    del _set_srs

    def _get_transparent(self):
        """
        ``True`` if transparent is set to true, otherwise ``False``.
        """
        if self.get('transparent', 'false').lower() == 'true':
            return True
        return False
    def _set_transparent(self, transparent):
        self.params['transparent'] = str(transparent).lower()
    transparent = property(_get_transparent, _set_transparent)
    del _get_transparent
    del _set_transparent

    @property
    def bgcolor(self):
        """
        The background color in PIL format (#rrggbb). Defaults to '#ffffff'.
        """
        color = self.get('bgcolor', '0xffffff')
        return '#'+color[2:]

    def _get_format(self):
        """
        The requested format as string (w/o any 'image/', 'text/', etc prefixes)
        """
        _mime_class, format, options = split_mime_type(self.get('format', default=''))
        return format

    def _set_format(self, format):
        if '/' not in format:
            format = 'image/' + format
        self['format'] = format

    format = property(_get_format, _set_format)
    del _get_format
    del _set_format

    @property
    def format_mime_type(self):
        return self.get('format')

    def __repr__(self):
        return '%s(param=%r)' % (self.__class__.__name__, self.params)


class WMSRequest(BaseRequest):
    request_params = RequestParams
    request_handler_name = None
    fixed_params = {}
    expected_param = []
    non_strict_params = set()
    #pylint: disable-msg=E1102
    xml_exception_handler = None

    def __init__(self, param=None, url='', validate=False, non_strict=False, **kw):
        self.non_strict = non_strict
        BaseRequest.__init__(self, param=param, url=url, validate=validate, **kw)
        self.adapt_to_111()

    def adapt_to_111(self):
        pass

    def adapt_params_to_version(self):
        params = self.params.copy()
        for key, value in iteritems(self.fixed_params):
            params[key] = value
        if 'styles' not in params:
            params['styles'] = ''
        return params

    @property
    def query_string(self):
        return self.adapt_params_to_version().query_string

class WMSMapRequest(WMSRequest):
    """
    Base class for all WMS GetMap requests.

    :ivar requests: the ``RequestParams`` class for this request
    :ivar request_handler_name: the name of the server handler
    :ivar fixed_params: parameters that are fixed for a request
    :ivar expected_param: required parameters, used for validating
    """
    request_params = WMSMapRequestParams
    request_handler_name = 'map'
    fixed_params = {'request': 'GetMap', 'service': 'WMS'}
    expected_param = ['version', 'request', 'layers', 'styles', 'srs', 'bbox',
                      'width', 'height', 'format']
    #pylint: disable-msg=E1102
    xml_exception_handler = None
    prevent_image_exception = False

    def __init__(self, param=None, url='', validate=False, non_strict=False, **kw):
        WMSRequest.__init__(self, param=param, url=url, validate=validate,
                            non_strict=non_strict, **kw)

    def validate(self):
        self.validate_param()
        self.validate_bbox()
        self.validate_styles()

    def validate_param(self):
        missing_param = []
        for param in self.expected_param:
            if self.non_strict and param in self.non_strict_params:
                continue
            if param not in self.params:
                missing_param.append(param)

        if missing_param:
            if 'format' in missing_param:
                self.params['format'] = 'image/png'
            raise RequestError('missing parameters ' + str(missing_param),
                               request=self)

    def validate_bbox(self):
        x0, y0, x1, y1 = self.params.bbox
        if x0 >= x1 or y0 >= y1:
            raise RequestError('invalid bbox ' + self.params.get('bbox', None),
                               request=self)

    def validate_format(self, image_formats):
        format = self.params['format']
        if format not in image_formats:
            format = self.params['format']
            self.params['format'] = 'image/png'
            raise RequestError('unsupported image format: ' + format,
                               code='InvalidFormat', request=self)
    def validate_srs(self, srs):
        if self.params['srs'].upper() not in srs:
            raise RequestError('unsupported srs: ' + self.params['srs'],
                               code='InvalidSRS', request=self)
    def validate_styles(self):
        if 'styles' in self.params:
            styles = self.params['styles']
            if not set(styles.split(',')).issubset(set(['default', '', 'inspire_common:DEFAULT'])):
                raise RequestError('unsupported styles: ' + self.params['styles'],
                                   code='StyleNotDefined', request=self)


    @property
    def exception_handler(self):
        if self.prevent_image_exception:
            return self.xml_exception_handler()
        if 'exceptions' in self.params:
            if 'image' in self.params['exceptions'].lower():
                return exception.WMSImageExceptionHandler()
            elif 'blank' in self.params['exceptions'].lower():
                return exception.WMSBlankExceptionHandler()
        return self.xml_exception_handler()

    def copy(self):
        return self.__class__(param=self.params.copy(), url=self.url)


class Version(object):
    _versions = {}
    def __new__(cls, version):
        if version in cls._versions:
            return cls._versions[version]
        version_obj = object.__new__(cls)
        version_obj.__init__(version)
        cls._versions[version] = version_obj
        return version_obj
    def __init__(self, version):
        self.parts = tuple(int(x) for x in version.split('.'))

    def __lt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self.parts < other.parts

    def __ge__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self.parts >= other.parts

    def __repr__(self):
        return "Version('%s')" % ('.'.join(str(part) for part in self.parts),)

class WMS100MapRequest(WMSMapRequest):
    version = Version('1.0.0')
    xml_exception_handler = exception.WMS100ExceptionHandler
    fixed_params = {'request': 'map', 'wmtver': '1.0.0'}
    expected_param = ['wmtver', 'request', 'layers', 'styles', 'srs', 'bbox',
                      'width', 'height', 'format']
    def adapt_to_111(self):
        del self.params['wmtver']
        self.params['version'] = '1.0.0'
        self.params['request'] = 'GetMap'

    def adapt_params_to_version(self):
        params = WMSMapRequest.adapt_params_to_version(self)
        del params['version']
        del params['service']

        image_format = params['format']
        if '/' in image_format:
            params['format'] = image_format.split('/', 1)[1].upper()
        return params

    def validate_format(self, image_formats):
        format = self.params['format']
        image_formats100 = [f.split('/', 1)[1].upper() for f in image_formats]

        if format in image_formats100:
            format = 'image/' + format.lower()
            self.params['format'] = format

        if format not in image_formats:
            format = self.params['format']
            self.params['format'] = 'image/png'
            raise RequestError('unsupported image format: ' + format,
                               code='InvalidFormat', request=self)

class WMS110MapRequest(WMSMapRequest):
    version = Version('1.1.0')
    fixed_params = {'request': 'GetMap', 'version': '1.1.0', 'service': 'WMS'}
    xml_exception_handler = exception.WMS110ExceptionHandler

    def adapt_to_111(self):
        del self.params['wmtver']

class WMS111MapRequest(WMSMapRequest):
    version = Version('1.1.1')
    fixed_params = {'request': 'GetMap', 'version': '1.1.1', 'service': 'WMS'}
    xml_exception_handler = exception.WMS111ExceptionHandler

    def adapt_to_111(self):
        del self.params['wmtver']

def switch_bbox_epsg_axis_order(bbox, srs):
    if bbox is not None and srs is not None:
        try:
            if SRS(srs).is_axis_order_ne:
                return bbox[1], bbox[0], bbox[3], bbox[2]
        except RuntimeError:
            log.warning('unknown SRS %s' % srs)
    return bbox

def _switch_bbox(self):
    self.bbox = switch_bbox_epsg_axis_order(self.bbox, self.srs)

class WMS130MapRequestParams(WMSMapRequestParams):
    """
    RequestParams for WMS 1.3.0 GetMap requests. Handles bbox axis-order.
    """
    switch_bbox = _switch_bbox


class WMS130MapRequest(WMSMapRequest):
    version = Version('1.3.0')
    request_params = WMS130MapRequestParams
    xml_exception_handler = exception.WMS130ExceptionHandler
    fixed_params = {'request': 'GetMap', 'version': '1.3.0', 'service': 'WMS'}
    expected_param = ['version', 'request', 'layers', 'styles', 'crs', 'bbox',
                      'width', 'height', 'format']
    def adapt_to_111(self):
        del self.params['wmtver']
        if 'crs' in self.params:
            self.params['srs'] = self.params['crs']
            del self.params['crs']
        self.params.switch_bbox()

    def adapt_params_to_version(self):
        params = WMSMapRequest.adapt_params_to_version(self)
        params.switch_bbox()
        if 'srs' in params:
            params['crs'] = params['srs']
            del params['srs']
        return params

    def validate_srs(self, srs):
        # its called crs in 1.3.0 and we validate before adapt_to_111
        if self.params['srs'].upper() not in srs:
            raise RequestError('unsupported crs: ' + self.params['srs'],
                               code='InvalidCRS', request=self)

    def copy_with_request_params(self, req):
        new_req = WMSMapRequest.copy_with_request_params(self, req)
        new_req.params.switch_bbox()
        return new_req

class WMSLegendGraphicRequestParams(WMSMapRequestParams):
    """
    RequestParams for WMS GetLegendGraphic requests.
    """
    def _set_layer(self, value):
        self.params['layer'] = value

    def _get_layer(self):
        """
        Layer for which to produce legend graphic.
        """
        return self.params.get('layer')
    layer = property(_get_layer, _set_layer)
    del _set_layer
    del _get_layer

    @property
    def sld_version(self):
        """
        Specification version for SLD-specification
        """
        return self.params.get('sld_version')


    def _set_scale(self, value):
        self.params['scale'] = value

    def _get_scale(self):
        if self.params.get('scale') is not None:
            return float(self['scale'])
        return None

    scale = property(_get_scale,_set_scale)
    del _set_scale
    del _get_scale

class WMSFeatureInfoRequestParams(WMSMapRequestParams):
    """
    RequestParams for WMS GetFeatureInfo requests.
    """
    @property
    def query_layers(self):
        """
        List with all query_layers.
        """
        return sum((layers.split(',') for layers in self.params.get_all('query_layers')), [])

    def _get_pos(self):
        """x, y query image coordinates (in pixel)"""
        if '.' in self['x'] or '.' in self['y']:
            return float(self['x']), float(self['y'])
        return int(self['x']), int(self['y'])

    def _set_pos(self, value):
        self['x'] = str(value[0])
        self['y'] = str(value[1])
    pos = property(_get_pos, _set_pos)
    del _get_pos
    del _set_pos

    @property
    def pos_coords(self):
        """x, y query coordinates (in request SRS)"""
        width, height = self.size
        bbox = self.bbox
        return make_lin_transf((0, 0, width, height), bbox)(self.pos)

class WMS130FeatureInfoRequestParams(WMSFeatureInfoRequestParams):
    switch_bbox = _switch_bbox

class WMSLegendGraphicRequest(WMSMapRequest):
    request_params = WMSLegendGraphicRequestParams
    request_handler_name = 'legendgraphic'
    non_strict_params = set(['sld_version', 'scale'])
    fixed_params = {'request': 'GetLegendGraphic', 'service': 'WMS', 'sld_version': '1.1.0'}
    expected_param = ['version', 'request', 'layer', 'format', 'sld_version']

    def validate(self):
        self.validate_param()
        self.validate_sld_version()

    def validate_sld_version(self):
        if self.params.get('sld_version', '1.1.0') != '1.1.0':
            raise RequestError('invalid sld_version ' + self.params.get('sld_version'),
                                request=self)


class WMS111LegendGraphicRequest(WMSLegendGraphicRequest):
    version = Version('1.1.1')
    fixed_params = WMSLegendGraphicRequest.fixed_params.copy()
    fixed_params['version'] = '1.1.1'
    xml_exception_handler = exception.WMS111ExceptionHandler

class WMS130LegendGraphicRequest(WMSLegendGraphicRequest):
    version = Version('1.3.0')
    fixed_params = WMSLegendGraphicRequest.fixed_params.copy()
    fixed_params['version'] = '1.3.0'
    xml_exception_handler = exception.WMS130ExceptionHandler

class WMSFeatureInfoRequest(WMSMapRequest):
    non_strict_params = set(['format', 'styles'])

    def validate_format(self, image_formats):
        if self.non_strict: return
        WMSMapRequest.validate_format(self, image_formats)

class WMS111FeatureInfoRequest(WMSFeatureInfoRequest):
    version = Version('1.1.1')
    request_params = WMSFeatureInfoRequestParams
    xml_exception_handler = exception.WMS111ExceptionHandler
    request_handler_name = 'featureinfo'
    fixed_params = WMS111MapRequest.fixed_params.copy()
    fixed_params['request'] = 'GetFeatureInfo'
    expected_param = WMSMapRequest.expected_param[:] + ['query_layers', 'x', 'y']

class WMS110FeatureInfoRequest(WMSFeatureInfoRequest):
    version = Version('1.1.0')
    request_params = WMSFeatureInfoRequestParams
    xml_exception_handler = exception.WMS110ExceptionHandler
    request_handler_name = 'featureinfo'
    fixed_params = WMS110MapRequest.fixed_params.copy()
    fixed_params['request'] = 'GetFeatureInfo'
    expected_param = WMSMapRequest.expected_param[:] + ['query_layers', 'x', 'y']

class WMS100FeatureInfoRequest(WMSFeatureInfoRequest):
    version = Version('1.0.0')
    request_params = WMSFeatureInfoRequestParams
    xml_exception_handler = exception.WMS100ExceptionHandler
    request_handler_name = 'featureinfo'
    fixed_params = WMS100MapRequest.fixed_params.copy()
    fixed_params['request'] = 'feature_info'
    expected_param = WMS100MapRequest.expected_param[:] + ['query_layers', 'x', 'y']

    def adapt_to_111(self):
        del self.params['wmtver']

    def adapt_params_to_version(self):
        params = WMSMapRequest.adapt_params_to_version(self)
        del params['version']
        return params

class WMS130FeatureInfoRequest(WMS130MapRequest):
    # XXX: this class inherits from WMS130MapRequest to reuse
    # the axis order stuff
    version = Version('1.3.0')
    request_params = WMS130FeatureInfoRequestParams
    xml_exception_handler = exception.WMS130ExceptionHandler
    request_handler_name = 'featureinfo'
    fixed_params = WMS130MapRequest.fixed_params.copy()
    fixed_params['request'] = 'GetFeatureInfo'
    expected_param = WMS130MapRequest.expected_param[:] + ['query_layers', 'i', 'j']
    non_strict_params = set(['format', 'styles'])

    def adapt_to_111(self):
        WMS130MapRequest.adapt_to_111(self)
        # only set x,y when present,
        # avoids empty values for request templates
        if 'i' in self.params:
            self.params['x'] = self.params['i']
        if 'j' in self.params:
            self.params['y'] = self.params['j']
        del self.params['i']
        del self.params['j']

    def adapt_params_to_version(self):
        params = WMS130MapRequest.adapt_params_to_version(self)
        params['i'] = self.params['x']
        params['j'] = self.params['y']
        del params['x']
        del params['y']
        return params

    def validate_format(self, image_formats):
        if self.non_strict: return
        WMSMapRequest.validate_format(self, image_formats)

class WMSCapabilitiesRequest(WMSRequest):
    request_handler_name = 'capabilities'
    exception_handler = None
    mime_type = 'text/xml'
    fixed_params = {}
    def __init__(self, param=None, url='', validate=False, non_strict=False, **kw):
        WMSRequest.__init__(self, param=param, url=url, validate=validate, **kw)

    def adapt_to_111(self):
        pass

    def validate(self):
        pass


class WMS100CapabilitiesRequest(WMSCapabilitiesRequest):
    version = Version('1.0.0')
    capabilities_template = 'wms100capabilities.xml'
    fixed_params = {'request': 'capabilities', 'wmtver': '1.0.0'}

    @property
    def exception_handler(self):
        return exception.WMS100ExceptionHandler()


class WMS110CapabilitiesRequest(WMSCapabilitiesRequest):
    version = Version('1.1.0')
    capabilities_template = 'wms110capabilities.xml'
    mime_type = 'application/vnd.ogc.wms_xml'
    fixed_params = {'request': 'GetCapabilities', 'version': '1.1.0', 'service': 'WMS'}

    @property
    def exception_handler(self):
        return exception.WMS110ExceptionHandler()

class WMS111CapabilitiesRequest(WMSCapabilitiesRequest):
    version = Version('1.1.1')
    capabilities_template = 'wms111capabilities.xml'
    mime_type = 'application/vnd.ogc.wms_xml'
    fixed_params = {'request': 'GetCapabilities', 'version': '1.1.1', 'service': 'WMS'}

    @property
    def exception_handler(self):
        return exception.WMS111ExceptionHandler()


class WMS130CapabilitiesRequest(WMSCapabilitiesRequest):
    version = Version('1.3.0')
    capabilities_template = 'wms130capabilities.xml'
    fixed_params = {'request': 'GetCapabilities', 'version': '1.3.0', 'service': 'WMS'}

    @property
    def exception_handler(self):
        return exception.WMS130ExceptionHandler()

request_mapping = {Version('1.0.0'): {'featureinfo': WMS100FeatureInfoRequest,
                                      'map': WMS100MapRequest,
                                      'capabilities': WMS100CapabilitiesRequest},
                   Version('1.1.0'): {'featureinfo': WMS110FeatureInfoRequest,
                                       'map': WMS110MapRequest,
                                       'capabilities': WMS110CapabilitiesRequest},
                   Version('1.1.1'): {'featureinfo': WMS111FeatureInfoRequest,
                                      'map': WMS111MapRequest,
                                      'capabilities': WMS111CapabilitiesRequest,
                                      'legendgraphic': WMS111LegendGraphicRequest},
                   Version('1.3.0'): {'featureinfo': WMS130FeatureInfoRequest,
                                      'map': WMS130MapRequest,
                                      'capabilities': WMS130CapabilitiesRequest,
                                      'legendgraphic': WMS130LegendGraphicRequest},
                   }



def _parse_version(req):
    if 'version' in req.args:
        return Version(req.args['version'])
    if 'wmtver' in req.args:
        return Version(req.args['wmtver'])

    return None

def _parse_request_type(req):
    if 'request' in req.args:
        request_type = req.args['request'].lower()
        if request_type in ('getmap', 'map'):
            return 'map'
        elif request_type in ('getfeatureinfo', 'feature_info'):
            return 'featureinfo'
        elif request_type in ('getcapabilities', 'capabilities'):
            return 'capabilities'
        elif request_type in ('getlegendgraphic',):
            return 'legendgraphic'
        else:
            return request_type
    else:
        return None

def negotiate_version(version, supported_versions=None):
    """
    >>> negotiate_version(Version('0.9.0'))
    Version('1.0.0')
    >>> negotiate_version(Version('2.0.0'))
    Version('1.3.0')
    >>> negotiate_version(Version('1.1.1'))
    Version('1.1.1')
    >>> negotiate_version(Version('1.1.0'))
    Version('1.1.0')
    >>> negotiate_version(Version('1.1.0'), [Version('1.0.0')])
    Version('1.0.0')
    >>> negotiate_version(Version('1.3.0'), sorted([Version('1.1.0'), Version('1.1.1')]))
    Version('1.1.1')
    """
    if not supported_versions:
        supported_versions = list(request_mapping.keys())
        supported_versions.sort()

    if version < supported_versions[0]:
        return supported_versions[0] # smallest version we support

    if version > supported_versions[-1]:
        return supported_versions[-1] # highest version we support

    while True:
        next_highest_version = supported_versions.pop()
        if version >= next_highest_version:
            return next_highest_version

def wms_request(req, validate=True, strict=True, versions=None):
    version = _parse_version(req)
    req_type = _parse_request_type(req)

    if versions is None:
        versions = sorted([
            Version(v) for v in ('1.0.0', '1.1.0', '1.1.1', '1.3.0')])

    if version is None:
        # If no version number is specified in the request,
        # the server shall respond with the highest version.
        version = max(versions)

    if version not in versions:
        version_requests = None
    else:
        version_requests = request_mapping.get(version, None)

    if version_requests is None:
        negotiated_version = negotiate_version(version, supported_versions=versions)
        version_requests = request_mapping[negotiated_version]
    req_class = version_requests.get(req_type, None)
    if req_class is None:
        # use map request to get an exception handler for the requested version
        dummy_req = version_requests['map'](param=req.args, url=req.base_url,
                                            validate=False)
        raise RequestError("unknown WMS request type '%s'" % req_type, request=dummy_req)
    return req_class(param=req.args, url=req.base_url, validate=True,
                     non_strict=not strict, http=req)


def create_request(req_data, param, req_type='map', version='1.1.1', abspath=None):
    url = req_data['url']
    req_data = req_data.copy()
    del req_data['url']
    if 'request_format' in param:
        req_data['format'] = param['request_format']
    elif 'format' in param:
        req_data['format'] = param['format']

    if 'info_format' in param:
        req_data['info_format'] = param['info_format']

    if 'transparent' in req_data:
        # we don't want a boolean
        req_data['transparent'] = str(req_data['transparent'])

    if req_data.get('sld', '').startswith('file://'):
        sld_path = req_data['sld'][len('file://'):]
        if abspath:
            sld_path = abspath(sld_path)
        with codecs.open(sld_path, 'r', 'utf-8') as f:
            req_data['sld_body'] = f.read()
        del req_data['sld']

    return request_mapping[Version(version)][req_type](url=url, param=req_data)


info_formats = {
    Version('1.3.0'): (('text', 'text/plain'),
                       ('html', 'text/html'),
                       ('xml', 'text/xml'),
                       ('json', 'application/json'),
                      ),
    None: (('text', 'text/plain'),
           ('html', 'text/html'),
           ('xml', 'application/vnd.ogc.gml'),
           ('json', 'application/json'),
          )
}


def infotype_from_mimetype(version, mime_type):
    if version in info_formats:
        formats = info_formats[version]
    else:
        formats = info_formats[None] # default
    for t, m in formats:
        if m == mime_type: return t

def mimetype_from_infotype(version, info_type):
    if version in info_formats:
        formats = info_formats[version]
    else:
        formats = info_formats[None] # default
    for t, m in formats:
        if t == info_type: return m
    return 'text/plain'

