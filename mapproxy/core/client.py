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
import urllib2
from urllib2 import URLError, HTTPError
from urlparse import urlsplit
from datetime import datetime
import logging
log = logging.getLogger(__name__)

from mapproxy.core.app import version
from mapproxy.core.utils import reraise_exception
from mapproxy.core.config import base_config

import socket
socket.setdefaulttimeout(base_config().http_client_timeout)

class HTTPClientError(Exception):
    pass

class HTTPClient(object):
    log = logging.getLogger(__name__ + '.http')
    log_fmt = '%(host)s - - [%(date)s] "GET %(path)s HTTP/1.1" %(status)d %(size)s "-" ""'
    log_datefmt = '%d/%b/%Y:%H:%M:%S %z'
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', 'MapProxy-%s' % (version,))]
    
    def _log(self, url, result):
        if not self.log.isEnabledFor(logging.INFO):
            return
        _scheme, host, path, query, _frag = urlsplit(url)
        if query:
            path = path + '?' + query
        date = datetime.now().strftime(self.log_datefmt)
        status = result.code
        size = result.headers.get('Content-length', '-')
        log_msg = self.log_fmt % locals()
        self.log.info(log_msg)
    
    def open(self, url, *args, **kw):
        try:
            result = self.opener.open(url, *args, **kw)
            self._log(url, result)
            return result
        except HTTPError, e:
            reraise_exception(HTTPClientError('HTTP Error (%.30s...): %d' 
                                              % (url, e.code)), sys.exc_info())
        except URLError, e:
            try:
                reason = e.reason.args[1]
            except (AttributeError, IndexError):
                reason = e.reason
            reraise_exception(HTTPClientError('No response from URL (%.30s...): %s'
                                              % (url, reason)), sys.exc_info())
        except ValueError, e:
            reraise_exception(HTTPClientError('URL not correct (%.30s...): %s' 
                                              % (url, e.message)), sys.exc_info())
        except Exception, e:
            reraise_exception(HTTPClientError('Internal HTTP error (%.30s...): %r'
                                              % (url, e)), sys.exc_info())


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
