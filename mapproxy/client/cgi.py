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
HTTP client that directly calls CGI executable.
"""

import errno
import os
import re
import time

from mapproxy.source import SourceError
from mapproxy.image import ImageSource
from mapproxy.client.http import HTTPClientError
from mapproxy.client.log import log_request
from mapproxy.util.async import import_module
from StringIO import StringIO
from urlparse import urlparse

subprocess = import_module('subprocess')

def split_cgi_response(data):
    headers = []
    prev_n = 0
    while True:
        next_n = data.find('\n', prev_n)
        if next_n < 0:
            break 
        next_line_begin = data[next_n+1:next_n+3]
        headers.append(data[prev_n:next_n].rstrip('\r'))
        if next_line_begin[0] == '\n':
            return headers_dict(headers), data[next_n+2:]
        elif next_line_begin == '\r\n':
            return headers_dict(headers), data[next_n+3:]
        prev_n = next_n+1
    return {}, data

def headers_dict(header_lines):
    headers = {}
    for line in header_lines:
        if ':' in line:
            key, value = line.split(':', 1)
            value = value.strip()
        else:
            key = line
            value = None
        key = key[0].upper() + key[1:].lower()
        headers[key] = value
    return headers

class CGIClient(object):
    def __init__(self, script, no_headers=False, working_directory=None):
        self.script = script
        self.working_directory = working_directory
        self.no_headers = no_headers
    
    def open(self, url, data=None):
        assert data is None, 'POST requests not supported by CGIClient'
        
        parsed_url = urlparse(url)
        environ = {
            'QUERY_STRING': parsed_url.query,
            'REQUEST_METHOD': 'GET',
            'GATEWAY_INTERFACE': 'CGI/1.1',
            'SERVER_ADDR': '127.0.0.1',
            'SERVER_NAME': 'localhost',
            'SERVER_PROTOCOL': 'HTTP/1.0',
            'SERVER_SOFTWARE': 'MapProxy',
        }
        
        start_time = time.time()
        try:
            p = subprocess.Popen([self.script], env=environ,
                stdout=subprocess.PIPE,
                cwd=self.working_directory or os.path.dirname(self.script)
            )
        except OSError, ex:
            if ex.errno == errno.ENOENT:
                raise SourceError('CGI script not found (%s)' % (self.script,))
            elif ex.errno == errno.EACCES:
                raise SourceError('No permission for CGI script (%s)' % (self.script,))
            else:
                raise
            
        stdout = p.communicate()[0]
        ret = p.wait()
        if ret != 0:
            raise HTTPClientError('Error during CGI call (exit code: %d)' 
                                              % (ret, ))
        
        if self.no_headers:
            content = stdout
            headers = dict()
        else:
            headers, content = split_cgi_response(stdout)
        
        status_match = re.match('(\d\d\d) ', headers.get('Status', ''))
        if status_match:
            status_code = status_match.group(1)
        else:
            status_code = '-'
        size = len(content)
        content = StringIO(content)
        content.headers = headers
        
        log_request('%s:%s' % (self.script, parsed_url.query),
            status_code, size=size, method='CGI', duration=time.time()-start_time)
        return content
    
    def open_image(self, url, data=None):
        resp = self.open(url, data=data)
        if 'Content-type' in resp.headers:
            if not resp.headers['Content-type'].lower().startswith('image'):
                raise HTTPClientError('response is not an image: (%s)' % (resp.read()))
        return ImageSource(resp)

