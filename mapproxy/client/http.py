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
Tile retrieval (WMS, TMS, etc.).
"""
import sys
import httplib
import urllib2
from urllib2 import URLError, HTTPError
from urlparse import urlsplit
from datetime import datetime
import warnings
import logging
log = logging.getLogger(__name__)

from mapproxy.version import version
from mapproxy.image import ImageSource
from mapproxy.util import reraise_exception

import socket

class HTTPClientError(Exception):
    pass
    

if sys.version_info >= (2, 6):
    _urllib2_has_timeout = True
else:
    _urllib2_has_timeout = False

_max_set_timeout = None

try:
    import ssl
    ssl # prevent pyflakes warnings
except ImportError:
    ssl = None


def _set_global_socket_timeout(timeout):
    global _max_set_timeout
    if _max_set_timeout is None:
        _max_set_timeout = timeout
    elif _max_set_timeout != timeout:
        _max_set_timeout = max(_max_set_timeout, timeout)
        warnings.warn("Python >=2.6 required for individual HTTP timeouts. Setting global timeout to %.1f." %
                     _max_set_timeout)
    socket.setdefaulttimeout(_max_set_timeout)


class _URLOpenerCache(object):
    """
    Creates custom URLOpener with BasicAuth and HTTPS handler.
    
    Caches and reuses opener if possible (i.e. if they share the same
    ssl_ca_certs).
    """
    def __init__(self):
        self._opener = {}
    
    def __call__(self, ssl_ca_certs, url, username, password):
        if ssl_ca_certs not in self._opener:
            handlers = []
            if ssl_ca_certs:
                connection_class = verified_https_connection_with_ca_certs(ssl_ca_certs)
                https_handler = VerifiedHTTPSHandler(connection_class=connection_class)
                handlers.append(https_handler)
            passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
            authhandler = urllib2.HTTPBasicAuthHandler(passman)
            handlers.append(authhandler)

            opener = urllib2.build_opener(*handlers)
            opener.addheaders = [('User-agent', 'MapProxy-%s' % (version,))]
            
            self._opener[ssl_ca_certs] = (opener, passman)
        else:
            opener, passman = self._opener[ssl_ca_certs]
        
        if url is not None and username is not None and password is not None:
            passman.add_password(None, url, username, password)
        
        return opener
    
create_url_opener = _URLOpenerCache()

class HTTPClient(object):
    log = logging.getLogger(__name__ + '.http')
    log_fmt = '%(host)s - - [%(date)s] "GET %(path)s HTTP/1.1" %(status)d %(size)s "-" ""'
    log_datefmt = '%d/%b/%Y:%H:%M:%S %z'
    
    def __init__(self, url=None, username=None, password=None, insecure=False,
                 ssl_ca_certs=None, timeout=None, headers=None):
        if _urllib2_has_timeout:
            self._timeout = timeout
        else:
            self._timeout = None
            _set_global_socket_timeout(timeout)
        handlers = []
        if url and url.startswith('https'):
            if insecure:
                ssl_ca_certs = None
            else:
                if ssl is None:
                    raise ImportError('No ssl module found. SSL certificate '
                        'verification requires Python 2.6 or ssl module. Upgrade '
                        'or disable verification with http.ssl_no_cert_checks option.')
                if ssl_ca_certs is None:
                    raise HTTPClientError('No ca_certs file set (http.ssl_ca_certs). '
                        'Set file or disable verification with http.ssl_no_cert_checks option.')
        
        self.opener = create_url_opener(ssl_ca_certs, url, username, password)
        self.header_list = headers.items() if headers else []
        
    def _log(self, url, status, result):
        if not self.log.isEnabledFor(logging.INFO):
            return
        _scheme, host, path, query, _frag = urlsplit(url)
        if query:
            path = path + '?' + query
        date = datetime.now().strftime(self.log_datefmt)
        size = 0
        if result is not None:
            size = result.headers.get('Content-length', '-')
        log_msg = self.log_fmt % dict(date=date, size=size, host=host,
                                      status=status, path=path)
        self.log.info(log_msg)
    
    def open(self, url, data=None):
        code = 500
        result = None
        req = urllib2.Request(url, data=data)
        for key, value in self.header_list:
            req.add_header(key, value)
        try:
            if self._timeout is not None:
                result = self.opener.open(req, timeout=self._timeout)
            else:
                result = self.opener.open(req)
        except HTTPError, e:
            code = e.code
            reraise_exception(HTTPClientError('HTTP Error (%.30s...): %d' 
                                              % (url, e.code)), sys.exc_info())
        except URLError, e:
            if ssl and isinstance(e.reason, ssl.SSLError):
                e = HTTPClientError('Could not verify connection to URL (%.30s...): %s'
                                     % (url, e.reason.args[1]))
                reraise_exception(e, sys.exc_info())
            try:
                reason = e.reason.args[1]
            except (AttributeError, IndexError):
                reason = e.reason
            reraise_exception(HTTPClientError('No response from URL (%.30s...): %s'
                                              % (url, reason)), sys.exc_info())
        except ValueError, e:
            reraise_exception(HTTPClientError('URL not correct (%.30s...): %s' 
                                              % (url, e.args[0])), sys.exc_info())
        except Exception, e:
            reraise_exception(HTTPClientError('Internal HTTP error (%.30s...): %r'
                                              % (url, e)), sys.exc_info())
        else:
            code = getattr(result, 'code', 200)
            return result
        finally:
            self._log(url, code, result)
    
    def open_image(self, url, data=None):
        resp = self.open(url, data=data)
        if 'content-type' in resp.headers:
            if not resp.headers['content-type'].lower().startswith('image'):
                raise HTTPClientError('response is not an image: (%s)' % (resp.read()))
        return ImageSource(resp)

def auth_data_from_url(url):
    """
    >>> auth_data_from_url('http://localhost/bar')
    ('http://localhost/bar', (None, None))
    >>> auth_data_from_url('http://bar@localhost/bar')
    ('http://localhost/bar', ('bar', None))
    >>> auth_data_from_url('http://bar:baz@localhost/bar')
    ('http://localhost/bar', ('bar', 'baz'))
    """
    username = password = None
    if '@' in url:
        scheme, host, path, query, frag = urlsplit(url)
        if '@' in host:
            auth_data, host = host.split('@', 2)
            url = url.replace(auth_data+'@', '', 1)
            if ':' in auth_data:
                username, password = auth_data.split(':', 2)
            else:
                username = auth_data
    return url, (username, password)


_http_client = HTTPClient()
def open_url(url):
    return _http_client.open(url)

retrieve_url = open_url

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


class VerifiedHTTPSConnection(httplib.HTTPSConnection):
    def __init__(self, *args, **kw):
        self._ca_certs = kw.pop('ca_certs', None)
        httplib.HTTPSConnection.__init__(self, *args, **kw)
        
    def connect(self):
        # overrides the version in httplib so that we do
        #    certificate verification
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        
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