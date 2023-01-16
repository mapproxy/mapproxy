# This file is part of the MapProxy project.
# Copyright (C) 2017 Omniscale <http://omniscale.de>
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

from __future__ import absolute_import

import hashlib

from mapproxy.image import ImageSource
from mapproxy.cache.base import (
    TileCacheBase,
    tile_buffer,
)
from mapproxy.compat import BytesIO

try:
    import redis
except ImportError:
    redis = None


import logging
log = logging.getLogger(__name__)


class RedisCache(TileCacheBase):
    def __init__(self, host, port, prefix, ttl=0, db=0):
        if redis is None:
            raise ImportError("Redis backend requires 'redis' package.")

        self.prefix = prefix
        self.lock_cache_id = 'redis-' + hashlib.md5((host + str(port) + prefix + str(db)).encode('utf-8')).hexdigest()
        self.ttl = ttl
        self.r = redis.StrictRedis(host=host, port=port, db=db)

    def _key(self, tile):
        x, y, z = tile.coord
        return self.prefix + '-%d-%d-%d' % (z, x, y)

    def is_cached(self, tile):
        if tile.coord is None or tile.source:
            return True

        return self.r.exists(self._key(tile))

    def store_tile(self, tile):
        if tile.stored:
            return True

        key = self._key(tile)

        with tile_buffer(tile) as buf:
            data = buf.read()

        r = self.r.set(key, data)
        if self.ttl:
            # use ms expire times for unit-tests
            self.r.pexpire(key, int(self.ttl * 1000))
        return r

    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True
        key = self._key(tile)
        tile_data = self.r.get(key)
        if tile_data:
            tile.source = ImageSource(BytesIO(tile_data))
            return True
        return False

    def remove_tile(self, tile):
        if tile.coord is None:
            return True

        key = self._key(tile)
        self.r.delete(key)
        return True
