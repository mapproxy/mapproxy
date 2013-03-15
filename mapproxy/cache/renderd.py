# This file is part of the MapProxy project.
# Copyright (C) 2010, 2011 Omniscale <http://omniscale.de>
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
import json
import time
import requests
import hashlib

from mapproxy.client.log import log_request
from mapproxy.cache.tile import TileCreator, Tile
from mapproxy.source import SourceError

class RenderdClient(object):
    def __init__(self, renderd_address, priority=100):
        self.renderd_address = renderd_address
        self.priority = priority

    def send_tile_request(self, cache_identifier, tile_coords):
        identifier = hashlib.sha1(str((cache_identifier, tile_coords))).hexdigest()
        message = {
            'command': 'tile',
            'id': identifier,
            'tiles': tile_coords,
            'cache_identifier': cache_identifier,
            'priority': self.priority
        }
        resp = requests.post(self.renderd_address, data=json.dumps(message))
        return resp.json()

class RenderdTileCreator(TileCreator):
    def __init__(self, renderd_address, tile_mgr, dimensions=None, priority=100, tile_locker=None):
        TileCreator.__init__(self, tile_mgr, dimensions)
        self.tile_locker = tile_locker.lock or self.tile_mgr.lock
        self.renderd_address = renderd_address
        self.renderd_client = RenderdClient(renderd_address, priority)

    def _create_single_tile(self, tile):
        with self.tile_locker(tile):
            if not self.is_cached(tile):
                self.renderd_client.send_tile_request(
                    self.tile_mgr.identifier, tile_coords=[tile.coord])
            self.cache.load_tile(tile)
        return [tile]

    def _create_meta_tile(self, meta_tile):
        main_tile = Tile(meta_tile.main_tile_coord)
        with self.tile_locker(main_tile):
            if not all(self.is_cached(t) for t in meta_tile.tiles if t is not None):
                self.renderd_client.send_tile_request(
                    self.tile_mgr.identifier, tile_coords=[main_tile.coord])

        tiles = [Tile(coord) for coord in meta_tile.tiles]
        self.cache.load_tiles(tiles)
        return tiles

    def _create_renderd_tile(self, tile_coord):
        start_time = time.time()
        result = self.renderd_client.send_and_receive(self.tile_mgr, [tile_coord])
        duration = time.time()-start_time

        address = '%s:%s:%r' % (self.renderd_address,
            self.tile_mgr.identifier, tile_coord)

        if result['status'] == 'error':
            log_request(address, 500, None, duration=duration, method='RENDERD')
            raise SourceError(result.get('error_message', 'unknown error from renderd'))

        log_request(address, 200, None, duration=duration, method='RENDERD')
