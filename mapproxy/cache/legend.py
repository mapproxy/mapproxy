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

from __future__ import with_statement

import os
import hashlib

from mapproxy.image import ImageSource
from mapproxy.cache.file import _create_dir

import logging
log = logging.getLogger(__name__)

def legend_identifier(legends):
    """
    >>> legend_identifier([("http://example/?", "foo"), ("http://example/?", "bar")])
    'http://example/?foohttp://example/?bar'
    
    :param legends: list of legend URL and layer tuples
    """
    parts = []
    for url, layer in legends:
        parts.append(url)
        if layer:
            parts.append(layer)
    return ''.join(parts)

def legend_hash(identifier, scale):
    md5 = hashlib.md5()
    md5.update(identifier)
    md5.update(str(scale))
    return md5.hexdigest()

class LegendCache(object):
    def __init__(self, cache_dir=None, file_ext='png'):
        self.cache_dir = cache_dir
        self.file_ext = file_ext
        
    def store(self, legend):
        if legend.stored:
            return
        
        if legend.location is None:
            hash = legend_hash(legend.id, legend.scale)
            legend.location = os.path.join(self.cache_dir, hash) + '.' + self.file_ext
            _create_dir(legend.location)
        
        data = legend.source.as_buffer(format=self.file_ext, seekable=True)
        data.seek(0)
        with open(legend.location, 'wb') as f:
            log.debug('writing to %s' % (legend.location))
            f.write(data.read())
        data.seek(0)
        legend.stored = True
    
    def load(self, legend):
        hash = legend_hash(legend.id, legend.scale)
        legend.location = os.path.join(self.cache_dir, hash) + '.' + self.file_ext
        
        if os.path.exists(legend.location):
            legend.source = ImageSource(legend.location)
            return True
        return False
    
class Legend(object):
    def __init__(self, source=None, id=None, scale=None):
        self.source = source
        self.stored = None
        self.location = None
        self.id = id
        self.scale = scale
