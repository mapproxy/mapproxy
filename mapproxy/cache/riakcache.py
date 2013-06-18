# This file is part of the MapProxy project.
# Copyright (C) 2013 Omniscale <http://omniscale.de>
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

from __future__ import with_statement, absolute_import

import time
import urlparse
import threading

from cStringIO import StringIO

from mapproxy.image import ImageSource
from mapproxy.cache.base import (
    TileCacheBase, DummyLock,
    tile_buffer, CacheBackendError,)

try:
    import riak
except ImportError:
    riak = None
    
import logging
log = logging.getLogger(__name__)

class UnexpectedResponse(CacheBackendError):
    pass

class RiakCache(TileCacheBase):
    def __init__(self, url, bucket, prefix, tile_grid):
        if riak is None:
            raise ImportError("Riak backend requires 'riak' package.")
        
        urlparts = urlparse.urlparse(url)
        if urlparts.scheme.lower() == 'http':
            self.transport_class = riak.RiakHttpTransport
        elif urlparts.scheme.lower() == 'pbc':
            self.transport_class = riak.RiakPbcTransport
        else:
            raise ValueError('unknown Riak URL: %s' % urlparts.scheme)
        
        self.host = urlparts.hostname
        self.port = urlparts.port
        self.prefix = prefix
        self.bucket_name = bucket
        self.tile_grid = tile_grid
        self._db_conn_cache = threading.local()

    @property
    def connection(self):
        if not getattr(self._db_conn_cache, 'connection', None):
            self._db_conn_cache.connection = riak.RiakClient(host=self.host, port=self.port,
                transport_class=self.transport_class, prefix=self.prefix)
        return self._db_conn_cache.connection

    @property
    def bucket(self):
        return self.connection.bucket(self.bucket_name)

    def _get_object(self, coord):
        (x, y, z) = coord
        key = '%(z)d_%(x)d_%(y)d' % locals()
        try:
            return self.bucket.get_binary(key)
        except Exception, e:
            log.warn('error while requesting %s: %s', key, e)
            
    def _get_timestamp(self, obj):
        metadata = obj.get_usermeta()
        timestamp = metadata.get('timestamp')
        if timestamp == None:
            timestamp = float(time.time())
            obj.set_usermeta({'timestamp':str(timestamp)})
            
        return float(timestamp)

    def is_cached(self, tile):
        if tile.coord is None or tile.source:
            return True
        res = self._get_object(tile.coord)
        if not res.exists():
            return False
            
        tile.timestamp = self._get_timestamp(res)
        tile.size = len(res.get_data())
        
        return True

    def _store_bulk(self, tiles):
        for tile in tiles:
            res = self._get_object(tile.coord)
            with tile_buffer(tile) as buf:
                data = buf.read()
            res.set_data(data)
            res.set_usermeta({
                'timestamp': str(tile.timestamp),
                'size': str(tile.size),
            })
            res.store()

        return True

    def store_tile(self, tile):
        if tile.stored:
            return True

        return self._store_bulk([tile])

    def store_tiles(self, tiles):
        tiles = [t for t in tiles if not t.stored]
        return self._store_bulk(tiles)

    def load_tile_metadata(self, tile):
        if tile.timestamp:
            return

        # is_cached loads metadata
        self.is_cached(tile)

    def load_tile(self, tile, with_metadata=False):
        if not tile.is_missing():
            return True
        
        res = self._get_object(tile.coord)
        res.reload()
        if res.exists():
            tile_data = StringIO(res.get_data())
            tile.source = ImageSource(tile_data)
            if with_metadata:
                tile.timestamp = self._get_timestamp(res)
                tile.size = len(res.get_data())
            return True
        
        return False

    def remove_tile(self, tile):
        if tile.coord is None:
            return True
        
        res = self._get_object(tile.coord)
        if not res.exists():
            # already removed
            return True
        
        res.delete()
        return True
    
    def lock(self, tile):
        return DummyLock()
