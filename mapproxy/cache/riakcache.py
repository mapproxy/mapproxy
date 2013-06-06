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

from __future__ import with_statement

import time

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
    def __init__(self, host, bucket, port, prefix):
        if riak is None:
            raise ImportError("Riak backend requires 'riak' package.")

        self.client = None
        self.bucket = None
        try:
            self.client = riak.RiakClient(host=host)
            self.bucket = self.client.bucket(bucket)
        except Exception, e:
            log.warn('Unable to initialize RiakClient: %s', e)

    def _get_object(self, coord):
        (x, y, z) = coord
        key = "%(z)d_%(x)d_%(y)d" % locals()
        try:
            return self.bucket.new_binary(key, None);
        except Exception, e:
            log.warn('error while requesting %s: %s', key, e)
            
    def _get_timestamp(self, obj):
        metadata = obj.get_usermeta()
        try:
            timestamp = int(metadata["timestamp"])
        except Exception:
            timestamp = int(time.time())
            obj.set_usermeta({"timestamp":timestamp})
            
        return timestamp

    def is_cached(self, tile):
        if tile.is_missing():
            res = self._get_object(tile.coord)
            res.reload()
            if res.exists():
                tile.timestamp = self._get_timestamp(res)
                tile.size = len(res.get_data())
                return True
            else:
                return False
        
        return True

    def _store_bulk(self, tiles):
        for tile in tiles:
            res = self._get_object(tile.coord)
            with tile_buffer(tile) as buf:
                data = buf.read()
            res.set_data(data)
            res.set_usermeta({"timestamp":int(time.time())})
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
