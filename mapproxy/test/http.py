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

import threading
import sys
import cgi
import socket
import errno
from cStringIO import StringIO
from urlparse import urlsplit
from BaseHTTPServer import HTTPServer as HTTPServer_, BaseHTTPRequestHandler
from contextlib import contextmanager

class HTTPServer(HTTPServer_):
    allow_reuse_address = True
    
    def handle_error(self, request, client_address):
        _exc_class, exc, _tb = sys.exc_info()
        if isinstance(exc, socket.error):
            if (hasattr(exc, 'errno') and exc.errno == errno.EPIPE
              or exc.args[0] == errno.EPIPE): # exc.errno since py2.6
                # suppres 'Broken pipe' errors raised in timeout tests
                return
        HTTPServer_.handle_error(self, request, client_address)

class ThreadedStopableHTTPServer(threading.Thread):
    def __init__(self, address, requests_responses):
        threading.Thread.__init__(self, **{'group': None})
        self.requests_responses = requests_responses
        self.sucess = False
        self.shutdown = False
        self.httpd = HTTPServer(address, mock_http_handler(requests_responses))
        self.httpd.timeout = 1.0
        self.out = self.httpd.out = StringIO()
    def run(self):
        while self.requests_responses:
            if self.shutdown: break
            self.httpd.handle_request()
        if self.requests_responses:
            missing_req = [req for req, resp in self.requests_responses]
            print >>self.out, 'missing requests: ' + ','.join(map(str, missing_req))
        if self.out.tell() > 0: # errors written
            self.out.seek(0)
        else:
            self.sucess = True
        # force socket close so next test can bind to same address
        self.httpd.socket.close()

def mock_http_handler(requests_responses):
    class MockHTTPHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.query_data = self.path
            return self.do_mock_request('GET')
            
        def do_POST(self):
            length = int(self.headers['content-length'])
            self.query_data = self.path + '?' + self.rfile.read(length)
            return self.do_mock_request('POST')

        def do_mock_request(self, method):
            assert len(requests_responses) > 0, 'got unexpected request (%s)' % self.query_data
            req, resp = requests_responses.pop(0)
            if 'method' in req:
                if req['method'] != method:
                    print >>self.server.out, 'expected %s request, got %s' % (req['method'], method)
                    self.server.shutdown = True
            if req.get('require_basic_auth', False):
                if 'Authorization' not in self.headers:
                    requests_responses.insert(0, (req, resp)) # push back
                    self.send_response(401)
                    self.send_header('WWW-Authenticate', 'Basic realm="Secure Area"')
                    self.end_headers()
                    self.wfile.write('no access')
                    return
            if not query_eq(req['path'], self.query_data):
                print >>self.server.out, 'got request      ', self.query_data
                print >>self.server.out, 'expected request ', req['path']
                query_actual = set(query_to_dict(self.query_data).items())
                query_expected = set(query_to_dict(req['path']).items())
                print >>self.server.out, 'param diff  %s|%s' % (
                    query_actual - query_expected, query_expected - query_actual)
                self.server.shutdown = True
            if 'req_assert_function' in req:
                if not req['req_assert_function'](self):
                    print >>self.server.out, 'req_assert_function failed'
                    self.server.shutdown = True
            self.start_response(resp)
            self.wfile.write(resp['body'])
            if not requests_responses:
                self.server.shutdown = True
            return
        def start_response(self, resp):
            self.send_response(int(resp.get('status', '200')))
            if 'headers' in resp:
                for key, value in resp['headers'].iteritems():
                    self.send_header(key, value)
            self.end_headers()
        def log_request(self, code, size=None):
            pass
    return MockHTTPHandler

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
    """
    return (query_to_dict(expected) == query_to_dict(actual) and
            path_from_query(expected) == path_from_query(actual))

def assert_query_eq(expected, actual):
    path_actual = path_from_query(actual)
    path_expected = path_from_query(expected)
    assert path_expected == path_actual, path_expected + '!=' + path_actual

    query_actual = set(query_to_dict(actual).items())
    query_expected = set(query_to_dict(expected).items())

    assert query_expected == query_actual, '%s != %s\t%s|%s' % (
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
    for key, value in cgi.parse_qsl(query):
        d[key.lower()] = value
    return d

def assert_url_eq(url1, url2):
    parts1 = urlsplit(url1)
    parts2 = urlsplit(url2)
    
    assert parts1[0] == parts2[0], '%s != %s (%s)' % (url1, url2, 'schema')
    assert parts1[1] == parts2[1], '%s != %s (%s)' % (url1, url2, 'location')
    assert parts1[2] == parts2[2], '%s != %s (%s)' % (url1, url2, 'path')
    assert query_eq(parts1[3], parts2[3]), '%s != %s (%s)' % (url1, url2, 'query')
    assert parts1[4] == parts2[4], '%s != %s (%s)' % (url1, url2, 'fragment')

@contextmanager
def mock_httpd(address, requests_responses):
    t = ThreadedStopableHTTPServer(address, requests_responses)
    t.start()
    try:
        yield
    finally:
        t.shutdown = True
        t.join(1)
    assert t.sucess, 'requests to mock httpd did not match expectations:\n' + t.out.read()

def make_wsgi_env(query_string, extra_environ={}):
        env = {'QUERY_STRING': query_string,
               'wsgi.url_scheme': 'http',
               'HTTP_HOST': 'localhost',
              }
        env.update(extra_environ)
        return env
