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
from urllib.parse import parse_qsl, quote

from mapproxy.util.py import cached_property
from mapproxy.request.no_case_multi_dict import NoCaseMultiDict
from mapproxy.request.request_params import RequestParams


def url_decode(qs, charset='utf-8', decode_keys=False, include_empty=True,
               errors='ignore'):
    """
    Parse query string `qs` and return a `NoCaseMultiDict`.
    """
    tmp = []
    for key, value in parse_qsl(qs, include_empty):
        if not isinstance(key, str):
            key = key.decode(charset, errors)
        if not isinstance(value, str):
            value = value.decode(charset, errors)
        tmp.append((key, value))
    return NoCaseMultiDict(tmp)


class Request(object):
    charset = 'utf8'

    def __init__(self, environ):
        self.environ = environ
        self.environ['mapproxy.request'] = self

        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            del environ['HTTP_X_SCRIPT_NAME']
            environ['SCRIPT_NAME'] = script_name
            path_info = environ.get('PATH_INFO', '')
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

    @cached_property
    def args(self):
        if self.environ.get('QUERY_STRING'):
            return url_decode(self.environ['QUERY_STRING'], self.charset)
        else:
            return {}

    @property
    def path(self):
        path = self.environ.get('PATH_INFO', '')
        if path and isinstance(path, bytes):
            path = path.decode('utf-8')
        return path

    def pop_path(self):
        path = self.path.lstrip('/')
        if '/' in path:
            result, rest = path.split('/', 1)
            self.environ['PATH_INFO'] = '/' + rest
        else:
            self.environ['PATH_INFO'] = ''
            result = path
        if result:
            self.environ['SCRIPT_NAME'] = self.environ['SCRIPT_NAME'] + '/' + result
        return result

    @cached_property
    def host(self):
        if 'HTTP_X_FORWARDED_HOST' in self.environ:
            # might be a list, return first host only
            host = self.environ['HTTP_X_FORWARDED_HOST']
            host = host.split(',', 1)[0].strip()
            return host
        elif 'HTTP_HOST' in self.environ:
            host = self.environ['HTTP_HOST']
            if ':' in host:
                port = host.split(':')[1]
                if ((self.url_scheme, port) in (('https', '443'), ('http', '80'))):
                    host = host.split(':')[0]
            return host
        result = self.environ['SERVER_NAME']
        if ((self.url_scheme, self.environ['SERVER_PORT'])
                not in (('https', '443'), ('http', '80'))):
            result += ':' + self.environ['SERVER_PORT']
        return result

    @cached_property
    def url_scheme(self):
        scheme = self.environ.get('HTTP_X_FORWARDED_PROTO')
        if not scheme:
            scheme = self.environ['wsgi.url_scheme']
        return scheme

    @cached_property
    def accept_header(self):
        return self.environ.get('HTTP_ACCEPT', '')

    @cached_property
    def host_url(self):
        return '%s://%s/' % (self.url_scheme, self.host)

    @cached_property
    def server_url(self):
        return 'http://%s:%s/' % (
            self.environ['SERVER_NAME'],
            self.environ['SERVER_PORT']
        )

    @property
    def script_url(self):
        "Full script URL without trailing /"
        return (self.host_url.rstrip('/') +
                quote(self.environ.get('SCRIPT_NAME', '/').rstrip('/'))
                )

    @property
    def server_script_url(self):
        "Internal script URL"
        return self.server_url.rstrip('/')

    @property
    def base_url(self):
        return (self.host_url.rstrip('/')
                + quote(self.environ.get('SCRIPT_NAME', '').rstrip('/'))
                + quote(self.environ.get('PATH_INFO', ''))
                )


class BaseRequest(object):
    """
    This class represents a request with a URL and key-value parameters.

    :param param: A dict, `NoCaseMultiDict` or ``RequestParams``.
    :param url: The service URL for the request.
    :param validate: True if the request should be validated after initialization.
    """
    request_params = RequestParams

    def __init__(self, param=None, url='', validate=False, http=None, dimensions=None):
        self.delimiter = ','
        self.http = http

        if param is None:
            self.params = self.request_params(NoCaseMultiDict())
        else:
            if isinstance(param, RequestParams):
                self.params = self.request_params(param.params)
            else:
                self.params = self.request_params(NoCaseMultiDict(param))
        self.url = url
        if validate:
            self.validate()

    def __str__(self):
        return self.complete_url

    def validate(self):
        pass

    @property
    def raw_params(self):
        params = {}
        for key, value in self.params.items():
            params[key] = value
        return params

    @property
    def query_string(self):
        return self.params.query_string

    @property
    def complete_url(self):
        """
        The complete MapRequest as URL.
        """
        if not self.url:
            return self.query_string
        delimiter = '?'
        if '?' in self.url:
            delimiter = '&'
        if self.url[-1] == '?':
            delimiter = ''
        return self.url + delimiter + self.query_string

    def copy_with_request_params(self, req):
        """
        Return a copy of this request ond overwrite all param values from `req`.
        Use this method for templates
        (``req_template.copy_with_request_params(actual_values)``).
        """
        new_params = req.params.with_defaults(self.params)
        return self.__class__(param=new_params, url=self.url)

    def __repr__(self):
        return '%s(param=%r, url=%r)' % (self.__class__.__name__, self.params, self.url)


def split_mime_type(mime_type):
    """
    >>> split_mime_type('text/xml; charset=utf-8')
    ('text', 'xml', 'charset=utf-8')
    """
    options = None
    mime_class = None
    if '/' in mime_type:
        mime_class, mime_type = mime_type.split('/', 1)
    if ';' in mime_type:
        mime_type, options = [part.strip() for part in mime_type.split(';', 2)]
    return mime_class, mime_type, options
