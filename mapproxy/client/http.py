# This file is part of the MapProxy project.
# Copyright (C) 2010-2017 Omniscale <http://omniscale.de>
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
Tile retrieval (WMS, TMS, etc.).
"""
import sys
import time
import warnings

from mapproxy.version import version
from mapproxy.image import ImageSource
from mapproxy.util.py import reraise_exception
from mapproxy.client.log import log_request
from mapproxy.compat import PY2
from mapproxy.compat.modules import urlparse

if PY2:
    import urllib2
    from urllib2 import URLError, HTTPError, HTTPCookieProcessor
    import httplib
    from cookielib import CookieJar
else:
    from urllib import request as urllib2
    from urllib.error import URLError, HTTPError
    from urllib.request import HTTPCookieProcessor
    from http import client as httplib
    from http.cookiejar import CookieJar

import socket
import ssl

supports_ssl_default_context = False
if hasattr(ssl, 'create_default_context'):
    # Python >=2.7.9 and >=3.4.0
    supports_ssl_default_context = True

class HTTPClientError(Exception):
    def __init__(self, arg, response_code=None, full_msg=None):
        Exception.__init__(self, arg)
        self.response_code = response_code
        self.full_msg = full_msg


def build_https_handler(ssl_ca_certs, insecure):
    if supports_ssl_default_context:
        # python >=2.7.9 and >=3.4 supports ssl context in
        # HTTPSHandler use this
        if insecure:
            ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            ctx.verify_mode = ssl.CERT_NONE
        elif ssl_ca_certs:
            ctx = ssl.create_default_context(cafile=ssl_ca_certs)
        else:
            ctx = ssl.create_default_context()
        return urllib2.HTTPSHandler(context=ctx)
    else:
        if insecure:
            return None
        else:
            connection_class = verified_https_connection_with_ca_certs(
                ssl_ca_certs)
            return VerifiedHTTPSHandler(connection_class=connection_class)


class VerifiedHTTPSConnection(httplib.HTTPSConnection):
    def __init__(self, *args, **kw):
        self._ca_certs = kw.pop('ca_certs', None)
        httplib.HTTPSConnection.__init__(self, *args, **kw)

    def connect(self):
        # overrides the version in httplib so that we do
        #    certificate verification

        if hasattr(socket, 'create_connection') and hasattr(self, 'source_address'):
            sock = socket.create_connection((self.host, self.port),
                                            self.timeout, self.source_address)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))

        if hasattr(self, '_tunnel_host') and self._tunnel_host:
            # for Python >= 2.6 with proxy support
            self.sock = sock
            self._tunnel()

        # wrap the socket using verification with the root
        #    certs in self.ca_certs_path
        self.sock = ssl.wrap_socket(sock,
                                    self.key_file,
                                    self.cert_file,
                                    cert_reqs=ssl.CERT_REQUIRED,
                                    ca_certs=self._ca_certs)


def verified_https_connection_with_ca_certs(ca_certs):
    """
    Creates VerifiedHTTPSConnection classes with given ca_certs file.
    """
    def wrapper(*args, **kw):
        kw['ca_certs'] = ca_certs
        return VerifiedHTTPSConnection(*args, **kw)
    return wrapper


class VerifiedHTTPSHandler(urllib2.HTTPSHandler):
    def __init__(self, connection_class=VerifiedHTTPSConnection):
        self.specialized_conn_class = connection_class
        urllib2.HTTPSHandler.__init__(self)

    def https_open(self, req):
        return self.do_open(self.specialized_conn_class, req)


class _URLOpenerCache(object):
    """
    Creates custom URLOpener with BasicAuth and HTTPS handler.

    Caches and reuses opener if possible (i.e. if they share the same
    ssl_ca_certs).
    """
    def __init__(self):
        self._opener = {}

    def __call__(self, ssl_ca_certs, url, username, password, insecure=False, manage_cookies=False):
        cache_key = (ssl_ca_certs, insecure, manage_cookies)
        if cache_key not in self._opener:
            handlers = []
            https_handler = build_https_handler(ssl_ca_certs, insecure)
            if https_handler:
                handlers.append(https_handler)
            passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
            authhandler = urllib2.HTTPBasicAuthHandler(passman)
            handlers.append(authhandler)
            authhandler = urllib2.HTTPDigestAuthHandler(passman)
            handlers.append(authhandler)
            if manage_cookies:
                cj = CookieJar()
                handlers.append(HTTPCookieProcessor(cj))

            opener = urllib2.build_opener(*handlers)

            opener.addheaders = [('User-agent', 'MapProxy-%s' % (version,))]

            self._opener[cache_key] = (opener, passman)
        else:
            opener, passman = self._opener[cache_key]

        if url is not None and username is not None and password is not None:
            passman.add_password(None, url, username, password)

        return opener

create_url_opener = _URLOpenerCache()

class HTTPClient(object):
    def __init__(self, url=None, username=None, password=None, insecure=False,
                 ssl_ca_certs=None, timeout=None, headers=None, hide_error_details=False,
                 manage_cookies=False):
        self._timeout = timeout
        if url and url.startswith('https'):
            if insecure:
                ssl_ca_certs = None
            elif ssl_ca_certs is None and not supports_ssl_default_context:
                    raise HTTPClientError('No ca_certs file set (http.ssl_ca_certs). '
                        'Set file or disable verification with http.ssl_no_cert_checks option.')

        self.opener = create_url_opener(ssl_ca_certs, url, username, password, insecure=insecure, manage_cookies=manage_cookies)
        self.header_list = headers.items() if headers else []
        self.hide_error_details = hide_error_details

    def open(self, url, data=None):
        code = None
        result = None
        try:
            req = urllib2.Request(url, data=data)
        except ValueError as e:
            err = self.handle_url_exception(url, 'URL not correct', e.args[0])
            reraise_exception(err, sys.exc_info())
        for key, value in self.header_list:
            req.add_header(key, value)
        try:
            start_time = time.time()
            if self._timeout is not None:
                result = self.opener.open(req, timeout=self._timeout)
            else:
                result = self.opener.open(req)
        except HTTPError as e:
            code = e.code
            err = self.handle_url_exception(url, 'HTTP Error', str(code), response_code=code)
            reraise_exception(err, sys.exc_info())
        except URLError as e:
            if isinstance(e.reason, ssl.SSLError):
                err = self.handle_url_exception(url, 'Could not verify connection to URL', e.reason.args[1])
                reraise_exception(err, sys.exc_info())
            try:
                reason = e.reason.args[1]
            except (AttributeError, IndexError):
                reason = e.reason
            err = self.handle_url_exception(url, 'No response from URL', reason)
            reraise_exception(err, sys.exc_info())
        except ValueError as e:
            err = self.handle_url_exception(url, 'URL not correct', e.args[0])
            reraise_exception(err, sys.exc_info())
        except Exception as e:
            err = self.handle_url_exception(url, 'Internal HTTP error', repr(e))
            reraise_exception(err, sys.exc_info())
        else:
            code = getattr(result, 'code', 200)
            if code == 204:
                raise HTTPClientError('HTTP Error "204 No Content"', response_code=204)
            return result
        finally:
            log_request(url, code, result, duration=time.time()-start_time, method=req.get_method())

    def open_image(self, url, data=None):
        resp = self.open(url, data=data)
        if 'content-type' in resp.headers:
            if not resp.headers['content-type'].lower().startswith('image'):
                raise HTTPClientError('response is not an image: (%s)' % (resp.read()))
        return ImageSource(resp)

    def handle_url_exception(self, url, message, reason, response_code=None):
        full_msg = '%s "%s": %s' % (message, url, reason)
        if self.hide_error_details:
            return HTTPClientError(
                '{} (see logs for URL and reason).'.format(message),
                response_code=response_code,
                full_msg=full_msg,
            )
        else:
            return HTTPClientError(
                full_msg,
                response_code=response_code,
            )

def auth_data_from_url(url):
    """
    >>> auth_data_from_url('invalid_url')
    ('invalid_url', (None, None))
    >>> auth_data_from_url('http://localhost/bar')
    ('http://localhost/bar', (None, None))
    >>> auth_data_from_url('http://bar@localhost/bar')
    ('http://localhost/bar', ('bar', None))
    >>> auth_data_from_url('http://bar:baz@localhost/bar')
    ('http://localhost/bar', ('bar', 'baz'))
    >>> auth_data_from_url('http://bar:b:az@@localhost/bar')
    ('http://localhost/bar', ('bar', 'b:az@'))
    >>> auth_data_from_url('http://bar foo; foo@bar:b:az@@localhost/bar')
    ('http://localhost/bar', ('bar foo; foo@bar', 'b:az@'))
    >>> auth_data_from_url('https://bar:foo#;%$@localhost/bar')
    ('https://localhost/bar', ('bar', 'foo#;%$'))
    >>> auth_data_from_url('http://localhost/bar@2x')
    ('http://localhost/bar@2x', (None, None))
    >>> auth_data_from_url('http://bar@localhost/bar@2x')
    ('http://localhost/bar@2x', ('bar', None))
    >>> auth_data_from_url('http://bar:baz@localhost/bar@2x')
    ('http://localhost/bar@2x', ('bar', 'baz'))
    >>> auth_data_from_url('https://bar@localhost/bar/0/0/0@2x.png')
    ('https://localhost/bar/0/0/0@2x.png', ('bar', None))
    >>> auth_data_from_url('http://bar:baz@localhost/bar@2x.png')
    ('http://localhost/bar@2x.png', ('bar', 'baz'))
    """
    if not url or '://' not in url:
        # be silent for invalid URLs
        return url, (None, None)

    schema, url = url.split('://', 1)
    if '/' in url:
        host, request = url.split('/', 1)
    else:
        host, request = url, ''

    username = password = None
    if '@' in host:
        auth_data, host = host.rsplit('@', 1)
        if ':' in auth_data:
            username, password = auth_data.split(':', 1)
        else:
            username = auth_data
    url = schema + "://" + host + "/" + request
    return url, (username, password)


def open_url(url):
    url, (username, password) = auth_data_from_url(url)
    http_client = HTTPClient(url, username, password)
    return http_client.open(url)

def retrieve_image(url, client=None):
    """
    Retrive an image from `url`.

    :return: the image as a file object (with url .header and .info)
    :raise HTTPClientError: if response content-type doesn't start with image
    """
    resp = open_url(url)
    if not resp.headers['content-type'].startswith('image'):
        raise HTTPClientError('response is not an image: (%s)' % (resp.read()))
    return ImageSource(resp)

