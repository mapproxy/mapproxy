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
Service requests (parsing, handling, etc).
"""
from mapproxy.wms import exceptions
from mapproxy.core.config import base_config
from mapproxy.core.exceptions import RequestError
from mapproxy.core.srs import SRS
from mapproxy.core.request import RequestParams, BaseRequest, split_mime_type

import logging
log = logging.getLogger(__name__)

class WMSMapRequestParams(RequestParams):
    """
    This class represents key-value parameters for WMS map requests.
    
    All values can be accessed as a property.
    Some properties return processed values. ``size`` returns a tuple of the width
    and height, ``layers`` returns an iterator of all layers, etc. 
    
    """
    @property
    def layers(self):
        """
        List with all layer names.
        """
        return sum((layers.split(',') for layers in self.params.get_all('layers')), [])
    
    def _get_bbox(self):
        """
        ``bbox`` as a tuple (minx, miny, maxx, maxy).
        """
        if 'bbox' not in self.params or self.params['bbox'] is None:
            return None
        points = map(float, self.params['bbox'].split(','))
        return tuple(points[:4])
    def _set_bbox(self, value):
        if value is not None and not isinstance(value, basestring):
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
        width = int(self.params['width'])
        height = int(self.params['height'])
        return (width, height)
    def _set_size(self, value):
        self['width'] = str(value[0])
        self['height'] = str(value[1])
    size = property(_get_size, _set_size)
    del _get_size
    del _set_size
    
    @property
    def srs(self):
        return self.params.get('srs', None)
    
    @property
    def transparent(self):
        """
        ``True`` if transparent is set to true, otherwise ``False``.
        """
        if self.get('transparent', 'false').lower() == 'true':
            return True
        return False
    
    @property
    def bgcolor(self):
        """
        The background color in PIL format (#rrggbb). Defaults to '#ffffff'.
        """
        color = self.get('bgcolor', '0xffffff')
        return '#'+color[2:]
    
    @property
    def format(self):
        """
        The requested format as string (w/o any 'image/', 'text/', etc prefixes)
        """
        _mime_class, format, options = split_mime_type(self.get('format', default=''))
        if format == 'png' and (options == 'mode=8bit' or not self.transparent):
            format = 'png8'
        return format
    
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
    #pylint: disable-msg=E1102
    xml_exception_handler = None
    
    def __init__(self, param=None, url='', validate=False):
        BaseRequest.__init__(self, param=param, url=url, validate=validate)
        self.adapt_to_111()
    
    def adapt_to_111(self):
        pass
    
    def adapt_params_to_version(self):
        params = self.params.copy()
        for key, value in self.fixed_params.iteritems():
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

    def __init__(self, param=None, url='', validate=False):
        WMSRequest.__init__(self, param=param, url=url, validate=validate)
    
    def validate(self):
        missing_param = []
        for param in self.expected_param:
            if param not in self.params:
                missing_param.append(param)
        
        if missing_param:
            if 'format' in missing_param:
                self.params['format'] = 'image/png'
            raise RequestError('missing parameters ' + str(missing_param),
                               request=self)
        
        self.validate_bbox()
        self.validate_format()
        self.validate_srs()
        self.validate_styles()
    
    def validate_bbox(self):
        x0, y0, x1, y1 = self.params.bbox
        if x0 >= x1 or y0 >= y1:
            raise RequestError('invalid bbox ' + self.params.get('bbox', None),
                               request=self)
    
    def validate_format(self):
        format = self.params['format'].split(';', 1)[0].strip()
        if format not in base_config().wms.image_formats:
            format = self.params['format']
            self.params['format'] = 'image/png'
            raise RequestError('unsupported image format: ' + format,
                               code='InvalidFormat', request=self)
    def validate_srs(self):
        if self.params['srs'].upper() not in base_config().wms.srs:
            raise RequestError('unsupported srs: ' + self.params['srs'],
                               code='InvalidSRS', request=self)
    def validate_styles(self):
        if 'styles' in self.params:
            styles = self.params['styles']
            if styles.replace(',', '').strip() != '':
                raise RequestError('unsupported styles: ' + self.params['styles'],
                                   code='StyleNotDefined', request=self)
        
    
    @property
    def exception_handler(self):
        if 'exceptions' in self.params:
            if 'image' in self.params['exceptions'].lower():
                return exceptions.WMSImageExceptionHandler()
            elif 'blank' in self.params['exceptions'].lower():
                return exceptions.WMSBlankExceptionHandler()
        return self.xml_exception_handler()
    
    def copy(self):
        return self.__class__(param=self.params.copy(), url=self.url)
    
    

class WMS100MapRequest(WMSMapRequest):
    xml_exception_handler = exceptions.WMS100ExceptionHandler
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
        return params

class WMS111MapRequest(WMSMapRequest):
    fixed_params = {'request': 'GetMap', 'version': '1.1.1', 'service': 'WMS'}
    xml_exception_handler = exceptions.WMS111ExceptionHandler
    
    def adapt_to_111(self):
        del self.params['wmtver']

def _switch_bbox(self):
    if self.bbox is not None and self.srs is not None and self.srs != 'CRS:84':
        try:
            if SRS(self.srs).is_latlong:
                bbox = self.bbox
                bbox = bbox[1], bbox[0], bbox[3], bbox[2]
                self.bbox = bbox
        except RuntimeError:
            log.warn('unknown SRS %s' % self.srs)

class WMS130MapRequestParams(WMSMapRequestParams):
    """
    RequestParams for WMS 1.3.0 GetMap requests. Handles bbox axis-order.
    """
    switch_bbox = _switch_bbox


    
class WMS130MapRequest(WMSMapRequest):
    request_params = WMS130MapRequestParams
    xml_exception_handler = exceptions.WMS130ExceptionHandler
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
        
    def validate_srs(self):
        # its called crs in 1.3.0 and we validate before adapt_to_111
        if self.params['crs'].upper() not in base_config().wms.srs:
            raise RequestError('unsupported crs: ' + self.params['crs'],
                               code='InvalidCRS', request=self)
    
    def copy_with_request_params(self, req):
        new_req = WMSMapRequest.copy_with_request_params(self, req)
        new_req.params.switch_bbox()
        return new_req

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
        """x, y query image coordinates"""
        return int(self['x']), int(self['y'])
    def _set_pos(self, value):
        self['x'] = str(int(round(value[0])))
        self['y'] = str(int(round(value[1])))
    pos = property(_get_pos, _set_pos)
    del _get_pos
    del _set_pos

class WMS130FeatureInfoRequestParams(WMSFeatureInfoRequestParams):
    switch_bbox = _switch_bbox

class WMS111FeatureInfoRequest(WMSMapRequest):
    request_params = WMSFeatureInfoRequestParams
    xml_exception_handler = exceptions.WMS111ExceptionHandler
    request_handler_name = 'featureinfo'
    fixed_params = WMS111MapRequest.fixed_params.copy()
    fixed_params['request'] = 'GetFeatureInfo'
    expected_param = WMSMapRequest.expected_param[:] + ['query_layers', 'x', 'y']
    
class WMS100FeatureInfoRequest(WMSMapRequest):
    request_params = WMSFeatureInfoRequestParams
    xml_exception_handler = exceptions.WMS100ExceptionHandler
    request_handler_name = 'featureinfo'
    fixed_params = WMS100MapRequest.fixed_params.copy()
    fixed_params['request'] = 'feature_info'
    expected_param = WMS100MapRequest.expected_param[:] + ['query_layers', 'x', 'y']
    
    def adapt_to_111(self):
        del self.params['wmtver']
    
    def adapt_params_to_version(self):
        params = WMSMapRequest.adapt_params_to_version(self)
        del self.params['version']
        return params


class WMS130FeatureInfoRequest(WMSMapRequest):
    request_params = WMS130FeatureInfoRequestParams
    xml_exception_handler = exceptions.WMS130ExceptionHandler
    request_handler_name = 'featureinfo'
    fixed_params = WMS130MapRequest.fixed_params.copy()
    fixed_params['request'] = 'GetFeatureInfo'
    expected_param = WMS130MapRequest.expected_param[:] + ['query_layers', 'x', 'y']
    

class WMSCapabilitiesRequest(WMSRequest):
    request_handler_name = 'capabilities'
    exception_handler = None
    mime_type = 'text/xml'
    fixed_params = {}
    def __init__(self, param=None, url='', validate=False):
        WMSRequest.__init__(self, param=param, url=url, validate=validate)
    
    def adapt_to_111(self):
        pass
    
    def validate(self):
        pass
    

class WMS100CapabilitiesRequest(WMSCapabilitiesRequest):
    capabilities_template = 'wms100capabilities.xml'
    fixed_params = {'request': 'capabilities', 'wmtver': '1.0.0'}
    
    @property
    def exception_handler(self):
        return exceptions.WMS100ExceptionHandler()
    

class WMS111CapabilitiesRequest(WMSCapabilitiesRequest):
    capabilities_template = 'wms111capabilities.xml'
    mime_type = 'application/vnd.ogc.wms_xml'
    fixed_params = {'request': 'GetCapabilities', 'version': '1.1.1', 'service': 'WMS'}
    
    @property
    def exception_handler(self):
        return exceptions.WMS111ExceptionHandler()
    

class WMS130CapabilitiesRequest(WMSCapabilitiesRequest):
    capabilities_template = 'wms130capabilities.xml'
    fixed_params = {'request': 'GetCapabilities', 'version': '1.3.0', 'service': 'WMS'}
    
    @property
    def exception_handler(self):
        return exceptions.WMS130ExceptionHandler()
    
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
    
    def __cmp__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return cmp(self.parts, other.parts)
    def __repr__(self):
        return "Version('%s')" % ('.'.join(str(part) for part in self.parts),)

request_mapping = {Version('1.0.0'): {'featureinfo': WMS100FeatureInfoRequest,
                                      'map': WMS100MapRequest,
                                      'capabilities': WMS100CapabilitiesRequest},
                   Version('1.1.1'): {'featureinfo': WMS111FeatureInfoRequest,
                                      'map': WMS111MapRequest,
                                      'capabilities': WMS111CapabilitiesRequest},
                   Version('1.3.0'): {'featureinfo': WMS130FeatureInfoRequest,
                                      'map': WMS130MapRequest,
                                      'capabilities': WMS130CapabilitiesRequest},
                   }


    
def _parse_version(req):
    if 'version' in req.args:
        return Version(req.args['version'])
    if 'wmtver' in req.args:
        return Version(req.args['wmtver'])
    
    return Version('1.1.1') # default

def _parse_request_type(req):
    if 'request' in req.args:
        request_type = req.args['request'].lower()
        if request_type in ('getmap', 'map'):
            return 'map'
        elif request_type in ('getfeatureinfo', 'feature_info'):
            return 'featureinfo'
        elif request_type in ('getcapabilities', 'capabilities'):
            return 'capabilities'
        else:
            return request_type
    else:
        return None
        

def negotiate_version(version):
    """
    >>> negotiate_version(Version('0.9.0'))
    Version('1.0.0')
    >>> negotiate_version(Version('2.0.0'))
    Version('1.3.0')
    >>> negotiate_version(Version('1.1.1'))
    Version('1.1.1')
    >>> negotiate_version(Version('1.1.0'))
    Version('1.0.0')
    """
    supported_versions = request_mapping.keys()
    supported_versions.sort()
    
    if version < supported_versions[0]:
        return supported_versions[0] # smallest version we support
    
    if version > supported_versions[-1]:
        return supported_versions[-1] # highest version we support
    
    while True:
        next_highest_version = supported_versions.pop()
        if version >= next_highest_version:
            return next_highest_version

def wms_request(req, validate=True):
    version = _parse_version(req)
    req_type = _parse_request_type(req)
    
    version_requests = request_mapping.get(version, None)
    if version_requests is None:
        negotiated_version = negotiate_version(version)
        version_requests = request_mapping[negotiated_version]
    req_class = version_requests.get(req_type, None)
    if req_class is None:
        # use map request to get an exception handler for the requested version
        dummy_req = version_requests['map'](param=req.args, url=req.base_url,
                                            validate=False)
        raise RequestError("unknown WMS request type '%s'" % req_type, request=dummy_req)
    return req_class(param=req.args, url=req.base_url, validate=True)