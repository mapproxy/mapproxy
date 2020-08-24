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

from __future__ import print_function


import re
import threading
import sys
import socket
import errno
import time
import base64
from contextlib import contextmanager
from mapproxy.util.py import reraise
from mapproxy.compat import iteritems, PY2
from mapproxy.compat.modules import urlparse, parse_qsl
if PY2:
    from cStringIO import StringIO
else:
    from io import StringIO

if PY2:
    from BaseHTTPServer import HTTPServer as HTTPServer_, BaseHTTPRequestHandler
else:
    from http.server import HTTPServer as HTTPServer_, BaseHTTPRequestHandler

class RequestsMismatchError(AssertionError):
    def __init__(self, assertions):
        self.assertions = assertions

    def __str__(self):
        assertions = []
        for assertion in self.assertions:
            assertions.append(text_indent(str(assertion), '    ', ' -  '))
        return 'requests mismatch:\n' + '\n'.join(assertions)

class RequestError(str):
    pass

def text_indent(text, indent, first_indent=None):
    if first_indent is None:
        first_indent = indent

    text = first_indent + text
    return text.replace('\n', '\n' + indent)

class RequestMismatch(object):
    def __init__(self, msg, expected, actual):
        self.msg = msg
        self.expected = expected
        self.actual = actual

    def __str__(self):
        return ('requests mismatch (%s), expected:\n' % self.msg +
            text_indent(str(self.expected), '    ') +
            '\n  got:\n' + text_indent(str(self.actual), '    '))

class HTTPServer(HTTPServer_):
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        _exc_class, exc, _tb = sys.exc_info()
        if isinstance(exc, socket.error):
            if exc.errno == errno.EPIPE:
                # suppres 'Broken pipe' errors raised in timeout tests
                return
        HTTPServer_.handle_error(self, request, client_address)

class ThreadedStopableHTTPServer(threading.Thread):
    def __init__(self, address, requests_responses, unordered=False, query_comparator=None):
        threading.Thread.__init__(self, **{'group': None})
        self.requests_responses = requests_responses
        self.daemon = True
        self.sucess = False
        self.shutdown = False
        self.httpd = HTTPServer(address,mock_http_handler(requests_responses,
            unordered=unordered, query_comparator=query_comparator))
        self.httpd.timeout = 1.0
        self.assertions = self.httpd.assertions = []

    @property
    def http_port(self):
        return self.httpd.socket.getsockname()[1]

    def run(self):
        while self.requests_responses:
            if self.shutdown: break
            self.httpd.handle_request()
        if self.requests_responses:
            missing_req = [req for req, resp in self.requests_responses]
            self.assertions.append(
                RequestError('missing requests: ' + ','.join(map(str, missing_req)))
            )
        if not self.assertions:
            self.sucess = True
        # force socket close so next test can bind to same address
        self.httpd.socket.close()

class ThreadedSingleRequestHTTPServer(threading.Thread):
    def __init__(self, address, request_handler):
        threading.Thread.__init__(self, **{'group': None})
        self.daemon = True
        self.sucess = False
        self.shutdown = False
        self.httpd = HTTPServer(address, request_handler)
        self.httpd.timeout = 1.0
        self.assertions = self.httpd.assertions = []

    def run(self):
        self.httpd.handle_request()
        if not self.assertions:
            self.sucess = True
        # force socket close so next test can bind to same address
        self.httpd.socket.close()


def mock_http_handler(requests_responses, unordered=False, query_comparator=None):
    if query_comparator is None:
        query_comparator = query_eq
    class MockHTTPHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.query_data = self.path
            return self.do_mock_request('GET')

        def do_POST(self):
            length = int(self.headers['content-length'])
            self.query_data = self.path + '?' + self.rfile.read(length).decode('utf-8')
            return self.do_mock_request('POST')

        def _matching_req_resp(self):
            if len(requests_responses) == 0:
                return None, None
            if unordered:
                for req_resp in requests_responses:
                    req, resp = req_resp
                    if query_comparator(req['path'], self.query_data):
                        requests_responses.remove(req_resp)
                        return req, resp
                return None, None
            else:
                return requests_responses.pop(0)

        def do_mock_request(self, method):
            req, resp = self._matching_req_resp()
            if not req:
                self.server.assertions.append(
                    RequestError('got unexpected request: %s' % self.query_data)
                )
                return
            if 'method' in req:
                if req['method'] != method:
                    self.server.assertions.append(
                        RequestMismatch('unexpected method', req['method'], method)
                    )
                    self.server.shutdown = True
            if req.get('require_basic_auth', False):
                if 'Authorization' not in self.headers:
                    requests_responses.insert(0, (req, resp)) # push back
                    self.send_response(401)
                    self.send_header('WWW-Authenticate', 'Basic realm="Secure Area"')
                    self.end_headers()
                    self.wfile.write(b'no access')
                    return
            if req.get('headers'):
                for k, v in req['headers'].items():
                    if k not in self.headers:
                        self.server.assertions.append(
                            RequestMismatch('missing header', k, self.headers)
                        )
                    elif self.headers[k] != v:
                        self.server.assertions.append(
                            RequestMismatch('header mismatch', '%s: %s' % (k, v), self.headers)
                        )
            if not query_comparator(req['path'], self.query_data):
                self.server.assertions.append(
                    RequestMismatch('requests differ', req['path'], self.query_data)
                )
                query_actual = set(query_to_dict(self.query_data).items())
                query_expected = set(query_to_dict(req['path']).items())
                self.server.assertions.append(
                    RequestMismatch('requests params differ', query_expected - query_actual, query_actual - query_expected)
                )
                self.server.shutdown = True
            if 'req_assert_function' in req:
                if not req['req_assert_function'](self):
                    self.server.assertions.append(
                        RequestError('req_assert_function failed')
                    )
                    self.server.shutdown = True
            if 'duration' in resp:
                time.sleep(float(resp['duration']))
            self.start_response(resp)
            if resp.get('body_file'):
                with open(resp['body_file'], 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(resp['body'])
            if not requests_responses:
                self.server.shutdown = True
            return
        def start_response(self, resp):
            self.send_response(int(resp.get('status', '200')))
            if 'headers' in resp:
                for key, value in iteritems(resp['headers']):
                    self.send_header(key, value)
            self.end_headers()
        def log_request(self, code, size=None):
            pass

    return MockHTTPHandler

class MockServ(object):
    def __init__(self, port=0, host='localhost', unordered=False, bbox_aware_query_comparator=False):
        self._requested_port = port
        self.port = port
        self.host = host
        self.requests_responses = []
        self.unordered = unordered
        self.query_comparator = None
        if bbox_aware_query_comparator:
            self.query_comparator = wms_query_eq
        self._init_thread()

    def _init_thread(self):
        self._thread = ThreadedStopableHTTPServer((self.host, self._requested_port),
            [], unordered=self.unordered, query_comparator=self.query_comparator)
        if self._requested_port == 0:
            self.port = self._thread.http_port
        self.address = (self.host, self.port)

    def reset(self):
        self._init_thread()

    @property
    def base_url(self):
        return 'http://localhost:%d' % (self.port, )

    def expects(self, path, method='GET', headers=None):
        headers = headers or ()
        self.requests_responses.append(
            (dict(path=path, method=method, headers=headers), {'body': b''}))
        return self

    def returns(self, body=None, body_file=None, status_code=200, headers=None):
        assert body or body_file
        headers = headers or {}
        self.requests_responses[-1][1].update(
            body=body, body_file=body_file, status=status_code, headers=headers)
        return self

    def __enter__(self):
        # copy request_responses to be able to reuse it after .reset()
        self._thread.requests_responses[:] = self.requests_responses
        self._thread.start()

    def __exit__(self, type, value, traceback):
        self._thread.shutdown = True
        self._thread.join(30)

        if not self._thread.sucess and value:
            print('requests to mock httpd did not '
            'match expectations:\n %s' % RequestsMismatchError(self._thread.assertions))
        if value:
            raise reraise((type, value, traceback))
        if not self._thread.sucess:
            raise RequestsMismatchError(self._thread.assertions)

def wms_query_eq(expected, actual):
    """
    >>> wms_query_eq('bAR=baz&foo=bizz&bbOX=0,0,100000,100000', 'foO=bizz&BBOx=-.0001,0.01,99999.99,100000.09&bar=baz')
    True
    >>> wms_query_eq('bAR=baz&foo=bizz&bbOX=0,0,100000,100000', 'foO=bizz&BBOx=-.0001,0.01,99999.99,100000.11&bar=baz')
    False
    >>> wms_query_eq('/service?bar=baz&fOO=bizz', 'foo=bizz&bar=baz')
    False
    >>> wms_query_eq('/1/2/3.png', '/1/2/3.png')
    True
    >>> wms_query_eq('/1/2/3.png', '/1/2/0.png')
    False
    """
    from mapproxy.srs import bbox_equals
    if path_from_query(expected) != path_from_query(actual):
        return False

    expected = query_to_dict(expected)
    actual = query_to_dict(actual)

    if 'bbox' in expected and 'bbox' in actual:
        expected = expected.copy()
        expected_bbox = [float(x) for x in expected.pop('bbox').split(',')]
        actual = actual.copy()
        actual_bbox = [float(x) for x in actual.pop('bbox').split(',')]
        if expected != actual:
            return False
        if not bbox_equals(expected_bbox, actual_bbox):
            return False
    else:
        if expected != actual:
            return False

    return True

numbers_only = re.compile(r'^-?\d+\.\d+(,-?\d+\.\d+)*$')

def query_eq(expected, actual):
    """
    >>> query_eq('bAR=baz&foo=bizz', 'foO=bizz&bar=baz')
    True
    >>> query_eq('/service?bar=baz&fOO=bizz', 'foo=bizz&bar=baz')
    False
    >>> query_eq('/1/2/3.png', '/1/2/3.png')
    True
    >>> query_eq('/1/2/3.png', '/1/2/0.png')
    False
    >>> query_eq('/map?point=2.9999999999,1.00000000001', '/map?point=3.0,1.0')
    True
    """

    if path_from_query(expected) != path_from_query(actual):
        return False

    expected = query_to_dict(expected)
    actual = query_to_dict(actual)

    if set(expected.keys()) != set(actual.keys()):
        return False

    for ke, ve in expected.items():
        if numbers_only.match(ve):
            if not float_string_almost_eq(ve, actual[ke]):
                return False
        else:
            if ve != actual[ke]:
                return False

    return True

def float_string_almost_eq(expected, actual):
    """
    Compares if two strings with comma-separated floats are almost equal.
    Strings must contain floats.

    >>> float_string_almost_eq('12345678900', '12345678901')
    False
    >>> float_string_almost_eq('12345678900.0', '12345678901.0')
    True

    >>> float_string_almost_eq('12345678900.0,-3.0', '12345678901.0,-2.9999999999')
    True
    """
    if not numbers_only.match(expected) or not numbers_only.match(actual):
        return False

    expected_nums = [float(x) for x in expected.split(',')]
    actual_nums = [float(x) for x in actual.split(',')]

    if len(expected_nums) != len(actual_nums):
        return False

    for e, a in zip(expected_nums, actual_nums):
        if abs(e - a) > abs((e+a)/2)/10e9:
            return False

    return True

def assert_query_eq(expected, actual, fuzzy_number_compare=False):
    path_actual = path_from_query(actual)
    path_expected = path_from_query(expected)
    assert path_expected == path_actual, path_expected + '!=' + path_actual

    query_actual = set(query_to_dict(actual).items())
    query_expected = set(query_to_dict(expected).items())

    if fuzzy_number_compare:
        equal = query_eq(expected, actual)
    else:
        equal = query_expected == query_actual
    assert equal, '%s != %s\t%s|%s' % (
        expected, actual, query_expected - query_actual, query_actual - query_expected)

def path_from_query(query):
    """
    >>> path_from_query('/service?foo=bar')
    '/service'
    >>> path_from_query('/1/2/3.png')
    '/1/2/3.png'
    >>> path_from_query('foo=bar')
    ''
    """
    if not ('&' in query or '=' in query):
        return query
    if '?' in query:
        return query.split('?', 1)[0]
    return ''

def query_to_dict(query):
    """
    >>> sorted(query_to_dict('/service?bar=baz&foo=bizz').items())
    [('bar', 'baz'), ('foo', 'bizz')]
    >>> sorted(query_to_dict('bar=baz&foo=bizz').items())
    [('bar', 'baz'), ('foo', 'bizz')]
    """
    if not ('&' in query or '=' in query):
        return {}
    d = {}
    if '?' in query:
        query = query.split('?', 1)[-1]
    for key, value in parse_qsl(query):
        d[key.lower()] = value
    return d

def assert_url_eq(url1, url2):
    parts1 = urlparse.urlsplit(url1)
    parts2 = urlparse.urlsplit(url2)

    assert parts1[0] == parts2[0], '%s != %s (%s)' % (url1, url2, 'schema')
    assert parts1[1] == parts2[1], '%s != %s (%s)' % (url1, url2, 'location')
    assert parts1[2] == parts2[2], '%s != %s (%s)' % (url1, url2, 'path')
    assert query_eq(parts1[3], parts2[3]), '%s != %s (%s)' % (url1, url2, 'query')
    assert parts1[4] == parts2[4], '%s != %s (%s)' % (url1, url2, 'fragment')

@contextmanager
def mock_httpd(address, requests_responses, unordered=False, bbox_aware_query_comparator=False):
    if bbox_aware_query_comparator:
        query_comparator = wms_query_eq
    else:
        query_comparator = query_eq
    t = ThreadedStopableHTTPServer(address, requests_responses, unordered=unordered,
        query_comparator=query_comparator)
    t.start()
    try:
        yield
    except:
        if not t.sucess:
            print(str(RequestsMismatchError(t.assertions)))
        raise
    finally:
        t.shutdown = True
        t.join(30)
    if not t.sucess:
        raise RequestsMismatchError(t.assertions)

@contextmanager
def mock_single_req_httpd(address, request_handler):
    t = ThreadedSingleRequestHTTPServer(address, request_handler)
    t.start()
    try:
        yield
    except:
        if not t.sucess:
            print(str(RequestsMismatchError(t.assertions)))
        raise
    finally:
        t.shutdown = True
        t.join(30)
    if not t.sucess:
        raise RequestsMismatchError(t.assertions)


def make_wsgi_env(query_string, extra_environ={}):
        env = {'QUERY_STRING': query_string,
               'wsgi.url_scheme': 'http',
               'HTTP_HOST': 'localhost',
              }
        env.update(extra_environ)
        return env

def basic_auth_value(username, password):
    return base64.b64encode(('%s:%s' % (username, password)).encode('utf-8'))

def assert_no_cache(resp):
    assert resp.headers["Pragma"] == "no-cache"
    assert resp.headers["Expires"] == "-1"
    assert resp.cache_control.no_store == True
