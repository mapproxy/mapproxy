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


import os
import hashlib

from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.util.fs import ensure_directory, write_atomic

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
    md5.update(identifier.encode('utf-8'))
    md5.update(str(scale).encode('ascii'))
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
            ensure_directory(legend.location)

        data = legend.source.as_buffer(ImageOptions(format='image/' + self.file_ext), seekable=True)
        data.seek(0)
        log.debug('writing to %s' % (legend.location))
        write_atomic(legend.location, data.read())
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
