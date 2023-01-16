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
Service responses.
"""

import hashlib
from mapproxy.util.times import format_httpdate, parse_httpdate, timestamp
from mapproxy.compat import PY2, text_type, iteritems

class Response(object):
    charset = 'utf-8'
    default_content_type = 'text/plain'
    block_size = 1024 * 32

    def __init__(self, response, status=None, content_type=None, mimetype=None):
        self.response = response
        if status is None:
            status = 200
        self.status = status
        self._timestamp = None
        self.headers = {}
        if mimetype:
            if mimetype.startswith('text/'):
                content_type = mimetype + '; charset=' + self.charset
            else:
                content_type = mimetype
        if content_type is None:
            content_type = self.default_content_type
        self.headers['Content-type'] = content_type

    def _status_set(self, status):
        if isinstance(status, int):
            status = status_code(status)
        self._status = status

    def _status_get(self):
        return self._status

    status = property(_status_get, _status_set)

    def _last_modified_set(self, date):
        if not date: return
        self._timestamp = timestamp(date)
        self.headers['Last-modified'] = format_httpdate(self._timestamp)
    def _last_modified_get(self):
        return self.headers.get('Last-modified', None)

    last_modified = property(_last_modified_get, _last_modified_set)

    def _etag_set(self, value):
        self.headers['ETag'] = value

    def _etag_get(self):
        return self.headers.get('ETag', None)

    etag = property(_etag_get, _etag_set)

    def cache_headers(self, timestamp=None, etag_data=None, max_age=None, no_cache=False):
        """
        Set cache-related headers.

        :param timestamp: local timestamp of the last modification of the
            response content
        :param etag_data: list that will be used to build an ETag hash.
            calls the str function on each item.
        :param max_age: the maximum cache age in seconds
        """
        if etag_data:
            hash_src = ''.join((str(x) for x in etag_data)).encode('ascii')
            self.etag = hashlib.md5(hash_src).hexdigest()

        if no_cache:
            assert not timestamp and not max_age
            self.headers['Cache-Control'] = 'no-cache, no-store'
            self.headers['Pragma'] = 'no-cache'
            self.headers['Expires'] = '-1'

        self.last_modified = timestamp
        if (timestamp or etag_data) and max_age is not None:
            self.headers['Cache-control'] = 'public, max-age=%d, s-maxage=%d' % (max_age, max_age)

    def make_conditional(self, req):
        """
        Make the response conditional to the HTTP headers in the CGI/WSGI `environ`.
        Checks for ``If-none-match`` and ``If-modified-since`` headers and compares
        to the etag and timestamp of this response. If the content was not modified
        the repsonse will changed to HTTP 304 Not Modified.
        """
        if req is None:
            return
        environ = req.environ

        not_modified = False


        if self.etag == environ.get('HTTP_IF_NONE_MATCH', -1):
            not_modified = True
        elif self._timestamp is not None:
            date = environ.get('HTTP_IF_MODIFIED_SINCE', None)
            timestamp = parse_httpdate(date)
            if timestamp is not None and self._timestamp <= timestamp:
                not_modified = True

        if not_modified:
            self.status = 304
            self.response = []
            if 'Content-type' in self.headers:
                del self.headers['Content-type']

    @property
    def content_length(self):
        return int(self.headers.get('Content-length', 0))

    @property
    def content_type(self):
        return self.headers['Content-type']

    @property
    def data(self):
        if hasattr(self.response, 'read'):
            return self.response.read()
        else:
            return b''.join(chunk.encode() for chunk in self.response)

    @property
    def fixed_headers(self):
        headers = []
        for key, value in iteritems(self.headers):
            if type(value) != text_type:
                # for str subclasses like ImageFormat
                value = str(value)
            if PY2 and isinstance(value, unicode):
                value = value.encode('utf-8')
            headers.append((key, value))
        return headers

    def __call__(self, environ, start_response):
        if hasattr(self.response, 'read'):
            if ((not hasattr(self.response, 'ok_to_seek') or
                self.response.ok_to_seek) and
               (hasattr(self.response, 'seek') and
                hasattr(self.response, 'tell'))):
                self.response.seek(0, 2) # to EOF
                self.headers['Content-length'] = str(self.response.tell())
                self.response.seek(0)
            if 'wsgi.file_wrapper' in environ:
                resp_iter = environ['wsgi.file_wrapper'](self.response, self.block_size)
            else:
                resp_iter = iter(lambda: self.response.read(self.block_size), b'')
        elif not self.response:
            resp_iter = iter([])
        elif isinstance(self.response, text_type):
            self.response = self.response.encode(self.charset)
            self.headers['Content-length'] = str(len(self.response))
            resp_iter = iter([self.response])
        elif isinstance(self.response, bytes):
            self.headers['Content-length'] = str(len(self.response))
            resp_iter = iter([self.response])
        else:
            resp_iter = self.response

        start_response(self.status, self.fixed_headers)
        return resp_iter

    def iter_encode(self, chunks):
        for chunk in chunks:
            if isinstance(chunk, text_type):
                chunk = chunk.encode(self.charset)
            yield chunk


# http://www.faqs.org/rfcs/rfc2616.html
_status_codes = {
    100: 'Continue',
    101: 'Switching Protocols',
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    307: 'Temporary Redirect',
    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Time-out',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request-URI Too Large',
    415: 'Unsupported Media Type',
    416: 'Requested range not satisfiable',
    417: 'Expectation Failed',
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Time-out',
    505: 'HTTP Version not supported',
}

def status_code(code):
    return str(code) + ' ' + _status_codes[code]
