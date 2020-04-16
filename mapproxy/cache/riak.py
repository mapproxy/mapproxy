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

from __future__ import absolute_import

import threading
import hashlib

from io import BytesIO

from mapproxy.image import ImageSource
from mapproxy.cache.tile import Tile
from mapproxy.cache.base import TileCacheBase, tile_buffer, CacheBackendError

try:
    import riak
except ImportError:
    riak = None
except TypeError:
    import warnings
    warnings.warn("riak version not compatible with this Python version")
    riak = None

import logging
log = logging.getLogger(__name__)

class UnexpectedResponse(CacheBackendError):
    pass

class RiakCache(TileCacheBase):
    def __init__(self, nodes, protocol, bucket, tile_grid, use_secondary_index=False, timeout=60):
        if riak is None:
            raise ImportError("Riak backend requires 'riak' package.")

        self.nodes = nodes
        self.protocol = protocol
        self.lock_cache_id = 'riak-' + hashlib.md5(bucket.encode('utf-8')).hexdigest()
        self.request_timeout = timeout * 1000
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
        if not getattr(self._db_conn_cache, 'bucket', None):
            self._db_conn_cache.bucket = self.connection.bucket(self.bucket_name)
        return self._db_conn_cache.bucket

    def _get_object(self, coord):
        (x, y, z) = coord
        key = '%(z)d_%(x)d_%(y)d' % locals()
        obj = False
        try:
            obj = self.bucket.get(key, r=1, timeout=self.request_timeout)
        except Exception as e:
            log.warning('error while requesting %s: %s', key, e)

        if not obj:
            obj = self.bucket.new(key=key, data=None, content_type='application/octet-stream')
        return obj

    def _get_timestamp(self, obj):
        metadata = obj.usermeta
        timestamp = metadata.get('timestamp')
        if timestamp != None:
            return float(timestamp)

        obj.usermeta = {'timestamp': '0'}
        return 0.0

    def is_cached(self, tile):
        return self.load_tile(tile, True)

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

            try:
                res.store(w=1, dw=1, pw=1, return_body=False, timeout=self.request_timeout)
            except riak.RiakError as ex:
                log.warning('unable to store tile: %s', ex)
                return False

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
        self.load_tile(tile, True)

    def load_tile(self, tile, with_metadata=False):
        if tile.timestamp is None:
            tile.timestamp = 0
        if tile.source or tile.coord is None:
            return True

        res = self._get_object(tile.coord)
        if res.exists:
            tile_data = BytesIO(res.encoded_data)
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

        try:
            res.delete(w=1, r=1, dw=1, pw=1, timeout=self.request_timeout)
        except riak.RiakError as ex:
            log.warning('unable to remove tile: %s', ex)
            return False
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
        for x in range(grid_size[0]/chunk_size):
            start_x = x * chunk_size
            end_x = start_x + chunk_size - 1
            for y in range(grid_size[1]/chunk_size):
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
