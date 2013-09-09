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
import threading
import hashlib

from cStringIO import StringIO

from mapproxy.image import ImageSource
from mapproxy.cache.tile import Tile
from mapproxy.cache.base import (
    TileCacheBase, FileBasedLocking,
    tile_buffer, CacheBackendError,)

try:
    import riak
except ImportError:
    riak = None

import logging
log = logging.getLogger(__name__)

class UnexpectedResponse(CacheBackendError):
    pass

class RiakCache(TileCacheBase, FileBasedLocking):
    def __init__(self, nodes, protocol, bucket, tile_grid, lock_dir, use_secondary_index=False):
        if riak is None:
            raise ImportError("Riak backend requires 'riak' package.")

        self.nodes = nodes
        self.protocol = protocol

        self.lock_cache_id = 'riak-' + hashlib.md5(nodes[0]['host'] + bucket).hexdigest()
        self.lock_dir = lock_dir
        self.lock_timeout = 60
        self.bucket_name = bucket
        self.tile_grid = tile_grid
        self.use_secondary_index = use_secondary_index
        self._db_conn_cache = threading.local()

    @property
    def connection(self):
        if not getattr(self._db_conn_cache, 'connection', None):
            self._db_conn_cache.connection = riak.RiakClient(protocol=self.protocol, nodes=self.nodes)
        return self._db_conn_cache.connection

    @property
    def bucket(self):
        return self.connection.bucket(self.bucket_name)

    def _get_object(self, coord):
        (x, y, z) = coord
        key = '%(z)d_%(x)d_%(y)d' % locals()
        try:
            return self.bucket.get(key, r=1, timeout=self.lock_timeout)
        except Exception, e:
            log.warn('error while requesting %s: %s', key, e)

    def _get_timestamp(self, obj):
        metadata = obj.usermeta
        timestamp = metadata.get('timestamp')
        if timestamp == None:
            timestamp = float(time.time())
            obj.usermeta = {'timestamp':str(timestamp)}

        return float(timestamp)

    def is_cached(self, tile):
        if tile.coord is None or tile.source:
            return True
        res = self._get_object(tile.coord)
        if not res.exists:
            return False

        tile.timestamp = self._get_timestamp(res)
        tile.size = len(res.encoded_data)

        return True

    def _store_bulk(self, tiles):
        for tile in tiles:
            res = self._get_object(tile.coord)
            with tile_buffer(tile) as buf:
                data = buf.read()
            res.encoded_data = data
            res.usermeta = {
                'timestamp': str(tile.timestamp),
                'size': str(tile.size),
            }
            if self.use_secondary_index:
                x, y, z = tile.coord
                res.add_index('tile_coord_bin', '%02d-%07d-%07d' % (z, x, y))
            res.store(return_body=False)

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
        if res.exists:
            tile_data = StringIO(res.encoded_data)
            tile.source = ImageSource(tile_data)
            if with_metadata:
                tile.timestamp = self._get_timestamp(res)
                tile.size = len(res.encoded_data)
            return True

        return False

    def remove_tile(self, tile):
        if tile.coord is None:
            return True

        res = self._get_object(tile.coord)
        if not res.exists:
            # already removed
            return True

        res.delete()
        return True

    def _fill_metadata_from_obj(self, obj, tile):
        tile_md = obj.usermeta
        timestamp = tile_md.get('timestamp')
        if timestamp:
            tile.timestamp = float(timestamp)

    def _key_iterator(self, level):
        """
        Generator for all tile keys in `level`.
        """
        # index() returns a list of all keys so we check for tiles in
        # batches of `chunk_size`*`chunk_size`.
        grid_size = self.tile_grid.grid_sizes[level]
        chunk_size = 256
        for x in xrange(grid_size[0]/chunk_size):
            start_x = x * chunk_size
            end_x = start_x + chunk_size - 1
            for y in xrange(grid_size[1]/chunk_size):
                start_y = y * chunk_size
                end_y = start_y + chunk_size - 1
                query = self.bucket.get_index('tile_coord_bin',
                    '%02d-%07d-%07d' % (level, start_x, start_y),
                    '%02d-%07d-%07d' % (level, end_x, end_y))
                for link in query.run():
                    yield link.get_key()

    def remove_tiles_for_level(self, level, before_timestamp=None):
        bucket = self.bucket
        client = self.connection
        for key in self._key_iterator(level):
            if before_timestamp:
                obj = self.bucket.get(key, r=1)
                dummy_tile = Tile((0, 0, 0))
                self._fill_metadata_from_obj(obj, dummy_tile)
                if dummy_tile.timestamp < before_timestamp:
                    obj.delete()
            else:
                riak.RiakObject(client, bucket, key).delete()
