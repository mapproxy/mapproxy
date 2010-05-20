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
import logging
log = logging.getLogger(__name__)

from mapproxy.core.app import version
from mapproxy.core.utils import reraise_exception
from mapproxy.core.config import base_config, abspath

import socket
socket.setdefaulttimeout(base_config().http_client_timeout)

class HTTPClientError(Exception):
    pass
    

try:
    import ssl
except ImportError:
    ssl = None


class HTTPClient(object):
    log = logging.getLogger(__name__ + '.http')
    log_fmt = '%(host)s - - [%(date)s] "GET %(path)s HTTP/1.1" %(status)d %(size)s "-" ""'
    log_datefmt = '%d/%b/%Y:%H:%M:%S %z'
    
    def __init__(self, url=None, username=None, password=None):
        handlers = []
        if url and url.startswith('https'):
            if not base_config().http.ssl.insecure:
                if ssl is None:
                    raise ImportError('No ssl module found. SSL certificate '
                        'verification requires Python 2.6 or ssl module. Upgrade '
                        'or disable verification with http.ssl.insecure option.')
                if base_config().http.ssl.ca_certs is None:
                    raise HTTPClientError('No ca_certs file set (http.ssl.ca_certs). '
                        'Set file or disable verification with http.ssl.insecure option.')
                https_handler = VerifiedHTTPSHandler()
                handlers.append(https_handler)
        if url is not None and username is not None and password is not None:
            passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
            passman.add_password(None, url, username, password)
            authhandler = urllib2.HTTPBasicAuthHandler(passman)
            handlers.append(authhandler)
        
        self.default_opener = urllib2.build_opener(*handlers)
        self.default_opener.addheaders = [('User-agent', 'MapProxy-%s' % (version,))]
    
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
    
    def open(self, url, *args, **kw):
        try:
            code = 500
            result = None
            result = self.default_opener.open(url, *args, **kw)
            code = result.code
            return result
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
        finally:
            self._log(url, code, result)

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

class TMSClient(object):
    def __init__(self, url, format='png'):
        self.url = url
        self.format = format
    
    def get_tile(self, tile_coord):
        x, y, z = tile_coord
        url = '%s/%d/%d/%d.%s' % (self.url, z, x, y, self.format)
        return retrieve_image(url)
    
    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.url, self.format)

class TileClient(object):
    def __init__(self, url_template):
        self.url_template = url_template
        self.url = url_template.template + url_template.format
    def get_tile(self, tile_coord):
        url = self.url_template.substitute(tile_coord)
        return retrieve_image(url)
    
    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.url_template)

class TileURLTemplate(object):
    """
    >>> t = TileURLTemplate('http://foo/tiles/%(z)s/%(x)d/%(y)s.png')
    >>> t.substitute((7, 4, 3))
    'http://foo/tiles/3/7/4.png'

    >>> t = TileURLTemplate('http://foo/tiles/%(z)s/%(x)d/%(y)s.png')
    >>> t.substitute((7, 4, 3))
    'http://foo/tiles/3/7/4.png'

    >>> t = TileURLTemplate('http://foo/tiles/%(tc_path)s.png')
    >>> t.substitute((7, 4, 3))
    'http://foo/tiles/03/000/000/007/000/000/004.png'
    """
    def __init__(self, template, format='png'):
        self.template= template
        self.format = format
        self.with_quadkey = True if '%(quadkey)' in template else False
        self.with_tc_path = True if '%(tc_path)' in template else False
    
    def substitute(self, tile_coord):
        x, y, z = tile_coord
        data = dict(x=x, y=y, z=z, format=self.format)
        if self.with_quadkey:
            data['quadkey'] = quadkey(tile_coord)
        if self.with_tc_path:
            data['tc_path'] = tilecache_path(tile_coord)
        return self.template % data
    
    def __repr__(self):
        return '%s(%r, format=%r)' % (
            self.__class__.__name__, self.template, self.format)

def tilecache_path(tile_coord):
    """
    >>> tilecache_path((1234567, 87654321, 9))
    '09/001/234/567/087/654/321'
    """
    x, y, z = tile_coord
    parts = ("%02d" % z,
             "%03d" % int(x / 1000000),
             "%03d" % (int(x / 1000) % 1000),
             "%03d" % (int(x) % 1000),
             "%03d" % int(y / 1000000),
             "%03d" % (int(y / 1000) % 1000),
             "%03d" % (int(y) % 1000))
    return '/'.join(parts)

def quadkey(tile_coord):
    """
    >>> quadkey((0, 0, 1))
    '0'
    >>> quadkey((1, 0, 1))
    '1'
    >>> quadkey((1, 2, 2))
    '21'
    """
    x, y, z = tile_coord
    quadKey = ""
    for i in range(z,0,-1):
        digit = 0
        mask = 1 << (i-1)
        if (x & mask) != 0:
            digit += 1
        if (y & mask) != 0:
            digit += 2
        quadKey += str(digit)
    return quadKey


_http_client = HTTPClient()
def open_url(url):
    return _http_client.open(url)

retrieve_url = open_url

def retrieve_image(url):
    """
    Retrive an image from `url`.
    
    :return: the image as a file object (with url .header and .info)
    :raise HTTPClientError: if response content-type doesn't start with image
    """
    resp = open_url(url)
    if not resp.headers['content-type'].startswith('image'):
        raise HTTPClientError('response is not an image: (%s)' % (resp.read()))
    return resp


class VerifiedHTTPSConnection(httplib.HTTPSConnection):
    def connect(self):
        # overrides the version in httplib so that we do
        #    certificate verification
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        
        # wrap the socket using verification with the root
        #    certs in base_config().http.ca_cert
        self.sock = ssl.wrap_socket(sock,
                                    self.key_file,
                                    self.cert_file,
                                    cert_reqs=ssl.CERT_REQUIRED,
                                    ca_certs=abspath(base_config().http.ssl.ca_certs))

class VerifiedHTTPSHandler(urllib2.HTTPSHandler):
    def __init__(self, connection_class=VerifiedHTTPSConnection):
        self.specialized_conn_class = connection_class
        urllib2.HTTPSHandler.__init__(self)

    def https_open(self, req):
        return self.do_open(self.specialized_conn_class, req)