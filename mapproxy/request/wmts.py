# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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
import re

from mapproxy.exception import RequestError
from mapproxy.request.base import RequestParams, BaseRequest, split_mime_type
from mapproxy.request.tile import TileRequest
from mapproxy.exception import XMLExceptionHandler
from mapproxy.template import template_loader

import mapproxy.service
get_template = template_loader(mapproxy.service.__name__, 'templates')


class WMTS100ExceptionHandler(XMLExceptionHandler):
    template_func = get_template
    template_file = 'wmts100exception.xml'
    content_type = 'text/xml'

    status_codes = {
        None: 500,
        'TileOutOfRange': 400,
        'MissingParameterValue': 400,
        'InvalidParameterValue': 400,
        'OperationNotSupported': 501
    }

class WMTSTileRequestParams(RequestParams):
    """
    This class represents key-value parameters for WMTS map requests.

    All values can be accessed as a property.
    Some properties return processed values. ``size`` returns a tuple of the width
    and height, ``layers`` returns an iterator of all layers, etc.

    """
    @property
    def layer(self):
        """
        List with all layer names.
        """
        return self['layer']

    def _get_coord(self):
        x = int(self['tilecol'])
        y = int(self['tilerow'])
        z = self['tilematrix']
        return x, y, z
    def _set_coord(self, value):
        x, y, z = value
        self['tilecol'] = x
        self['tilerow'] = y
        self['tilematrix'] = z
    coord = property(_get_coord, _set_coord)
    del _get_coord
    del _set_coord


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

    @property
    def dimensions(self):
        expected_param = set(['version', 'request', 'layer', 'style', 'tilematrixset',
            'tilematrix', 'tilerow', 'tilecol', 'format', 'service'])
        dimensions = {}
        for key, value in self.iteritems():
            if key not in expected_param:
                dimensions[key.lower()] = value
        return dimensions

    def __repr__(self):
        return '%s(param=%r)' % (self.__class__.__name__, self.params)


class WMTSRequest(BaseRequest):
    request_params = WMTSTileRequestParams
    request_handler_name = None
    fixed_params = {}
    expected_param = []
    non_strict_params = set()
    #pylint: disable=E1102
    xml_exception_handler = None

    def __init__(self, param=None, url='', validate=False, non_strict=False, **kw):
        self.non_strict = non_strict
        BaseRequest.__init__(self, param=param, url=url, validate=validate, **kw)

    def validate(self):
        pass


    @property
    def query_string(self):
        return self.params.query_string

class WMTS100TileRequest(WMTSRequest):
    """
    Base class for all WMTS GetTile requests.

    :ivar requests: the ``RequestParams`` class for this request
    :ivar request_handler_name: the name of the server handler
    :ivar fixed_params: parameters that are fixed for a request
    :ivar expected_param: required parameters, used for validating
    """
    request_params = WMTSTileRequestParams
    request_handler_name = 'tile'
    fixed_params = {'request': 'GetTile', 'version': '1.0.0', 'service': 'WMTS'}
    xml_exception_handler = WMTS100ExceptionHandler
    expected_param = ['version', 'request', 'layer', 'style', 'tilematrixset',
                      'tilematrix', 'tilerow', 'tilecol', 'format']
    #pylint: disable=E1102

    def __init__(self, param=None, url='', validate=False, non_strict=False, **kw):
        WMTSRequest.__init__(self, param=param, url=url, validate=validate,
                            non_strict=non_strict, **kw)

    def make_request(self):
        self.layer = self.params.layer
        self.tilematrixset = self.params.tilematrixset
        self.format = self.params.format # TODO
        self.tile = (int(self.params.coord[0]), int(self.params.coord[1]), int(self.params.coord[2]))
        self.origin = 'nw'
        self.dimensions = self.params.dimensions

    def validate(self):
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

        self.validate_styles()

    def validate_styles(self):
        if 'styles' in self.params:
            styles = self.params['styles']
            if styles.replace(',', '').strip() != '':
                raise RequestError('unsupported styles: ' + self.params['styles'],
                                   code='StyleNotDefined', request=self)


    @property
    def exception_handler(self):
        return self.xml_exception_handler()

    def copy(self):
        return self.__class__(param=self.params.copy(), url=self.url)



class WMTSFeatureInfoRequestParams(WMTSTileRequestParams):
    """
    RequestParams for WMTS GetFeatureInfo requests.
    """
    def _get_pos(self):
        """x, y query image coordinates (in pixel)"""
        return int(self['i']), int(self['j'])
    def _set_pos(self, value):
        self['i'] = str(int(round(value[0])))
        self['j'] = str(int(round(value[1])))
    pos = property(_get_pos, _set_pos)
    del _get_pos
    del _set_pos


class WMTS100FeatureInfoRequest(WMTS100TileRequest):
    request_params = WMTSFeatureInfoRequestParams
    request_handler_name = 'featureinfo'
    fixed_params = WMTS100TileRequest.fixed_params.copy()
    fixed_params['request'] = 'GetFeatureInfo'
    expected_param = WMTS100TileRequest.expected_param[:] + ['infoformat', 'i', 'j']
    non_strict_params = set(['format', 'styles'])

    def make_request(self):
        WMTS100TileRequest.make_request(self)
        self.infoformat = self.params.infoformat
        self.pos = self.params.pos

class WMTS100CapabilitiesRequest(WMTSRequest):
    request_handler_name = 'capabilities'
    capabilities_template = 'wmts100capabilities.xml'
    exception_handler = None
    mime_type = 'text/xml'
    fixed_params = {}
    def __init__(self, param=None, url='', validate=False, non_strict=False, **kw):
        WMTSRequest.__init__(self, param=param, url=url, validate=validate, **kw)



request_mapping = { 'featureinfo': WMTS100FeatureInfoRequest,
                    'tile': WMTS100TileRequest,
                    'capabilities': WMTS100CapabilitiesRequest
}


def _parse_request_type(req):
    if 'request' in req.args:
        request_type = req.args['request'].lower()
        if request_type.startswith('get'):
            request_type = request_type[3:]
            if request_type in ('tile', 'featureinfo', 'capabilities'):
                return request_type

    return None


def wmts_request(req, validate=True):
    req_type = _parse_request_type(req)

    req_class = request_mapping.get(req_type, None)
    if req_class is None:
        # use map request to get an exception handler for the requested version
        dummy_req = request_mapping['tile'](param=req.args, url=req.base_url,
                                            validate=False)
        raise RequestError("unknown WMTS request type '%s'" % req_type, request=dummy_req)
    return req_class(param=req.args, url=req.base_url, validate=True, http=req)

def create_request(req_data, param, req_type='tile'):
    url = req_data['url']
    req_data = req_data.copy()
    del req_data['url']
    if 'request_format' in param:
        req_data['format'] = param['request_format']
    elif 'format' in param:
        req_data['format'] = param['format']
    # req_data['bbox'] = param['bbox']
    # if isinstance(req_data['bbox'], types.ListType):
    #     req_data['bbox'] = ','.join(str(x) for x in req_data['bbox'])
    # req_data['srs'] = param['srs']

    return request_mapping[req_type](url=url, param=req_data)


class InvalidWMTSTemplate(Exception):
    pass

class URLTemplateConverter(object):
    var_re = re.compile(r'(?:\\{)?\\{(\w+)\\}(?:\\})?')
    # TODO {{}} format is deprecated, change to this in 1.6
    # var_re = re.compile(r'\\{(\w+)\\}')

    variables = {
        'TileMatrixSet': r'[\w_.:-]+',
        'TileMatrix': r'\d+',
        'TileRow': r'-?\d+',
        'TileCol': r'-?\d+',
        'I': r'\d+',
        'J': r'\d+',
        'Style': r'[\w_.:-]+',
        'Layer': r'[\w_.:-]+',
        'Format': r'\w+',
        'InfoFormat': r'\w+',
    }

    required = set(['TileCol', 'TileRow', 'TileMatrix', 'TileMatrixSet', 'Layer'])

    def __init__(self, template):
        self.template = template
        self.found = set()
        self.dimensions = []
        self._regexp = None
        self.regexp()

    def substitute_var(self, match):
        var = match.group(1)
        if var in self.variables:
            var_type_re = self.variables[var]
        else:
            self.dimensions.append(var)
            var = var.lower()
            var_type_re = r'[\w_.,:-]+'
        self.found.add(var)
        return r'(?P<%s>%s)' % (var, var_type_re)


    def regexp(self):
        if self._regexp:
            return self._regexp
        converted_re = self.var_re.sub(self.substitute_var, re.escape(self.template))
        wmts_re = re.compile(r'/wmts' + converted_re)
        if not self.found.issuperset(self.required):
            raise InvalidWMTSTemplate('missing required variables in WMTS restful template: %s' %
                self.required.difference(self.found))
        self._regexp = wmts_re
        return wmts_re

class FeatureInfoURLTemplateConverter(URLTemplateConverter):
    required = set(['TileCol', 'TileRow', 'TileMatrix', 'TileMatrixSet', 'Layer', 'I', 'J'])

class WMTS100RestTileRequest(TileRequest):
    """
    Class for RESTful WMTS requests.
    """
    xml_exception_handler = WMTS100ExceptionHandler
    request_handler_name = 'tile'
    origin = 'nw'

    def __init__(self, request, req_vars, url_converter=None):
        self.http = request
        self.url = request.base_url
        self.dimensions = {}
        self.req_vars = req_vars
        self.url_converter = url_converter

    def make_request(self):
        """
        Initialize tile request. Sets ``tile`` and ``layer`` and ``format``.
        :raise RequestError: if the format does not match the URL template``
        """
        req_vars = self.req_vars
        self.layer = req_vars['Layer']
        self.tile = int(req_vars['TileCol']), int(req_vars['TileRow']), int(req_vars['TileMatrix'])
        self.format = req_vars.get('Format')
        self.tilematrixset = req_vars['TileMatrixSet']
        if self.url_converter and self.url_converter.dimensions:
            for dim in self.url_converter.dimensions:
                self.dimensions[dim.lower()] = req_vars[dim.lower()]

    @property
    def exception_handler(self):
        return self.xml_exception_handler()

class WMTS100RestFeatureInfoRequest(TileRequest):
    """
    Class for RESTful WMTS FeatureInfo requests.
    """
    xml_exception_handler = WMTS100ExceptionHandler
    request_handler_name = 'featureinfo'

    def __init__(self, request, req_vars, url_converter=None):
        self.http = request
        self.url = request.base_url
        self.dimensions = {}
        self.req_vars = req_vars
        self.url_converter = url_converter

    def make_request(self):
        """
        Initialize tile request. Sets ``tile`` and ``layer`` and ``format``.
        :raise RequestError: if the format does not match the URL template``
        """
        req_vars = self.req_vars
        self.layer = req_vars['Layer']
        self.tile = int(req_vars['TileCol']), int(req_vars['TileRow']), int(req_vars['TileMatrix'])
        self.pos = int(req_vars['I']), int(req_vars['J'])
        self.format = req_vars.get('Format')
        self.infoformat = req_vars.get('InfoFormat')
        self.tilematrixset = req_vars['TileMatrixSet']
        if self.url_converter and self.url_converter.dimensions:
            for dim in self.url_converter.dimensions:
                self.dimensions[dim.lower()] = req_vars[dim.lower()]

    @property
    def exception_handler(self):
        return self.xml_exception_handler()

RESTFUL_CAPABILITIES_PATH = '/1.0.0/WMTSCapabilities.xml'

class WMTS100RestCapabilitiesRequest(object):
    """
    Class for RESTful WMTS capabilities requests.
    """
    xml_exception_handler = WMTS100ExceptionHandler
    request_handler_name = 'capabilities'
    capabilities_template = 'wmts100capabilities.xml'

    def __init__(self, request):
        self.http = request
        self.url = request.base_url[:-len(RESTFUL_CAPABILITIES_PATH)]

    @property
    def exception_handler(self):
        return self.xml_exception_handler()


def make_wmts_rest_request_parser(url_converter, fi_url_converter):
    tile_req_re = url_converter.regexp()
    fi_req_re = fi_url_converter.regexp()

    def wmts_request(req):
        if req.path.endswith(RESTFUL_CAPABILITIES_PATH):
            return WMTS100RestCapabilitiesRequest(req)

        match = tile_req_re.search(req.path)
        if not match:
            match = fi_req_re.search(req.path)
            if not match:
                raise RequestError('invalid request (%s)' % (req.path))

            req_vars = match.groupdict()
            return WMTS100RestFeatureInfoRequest(req, req_vars, fi_url_converter)
        req_vars = match.groupdict()
        return WMTS100RestTileRequest(req, req_vars, url_converter)

    return wmts_request
