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
import errno
import json
import time
import requests
import hashlib

from mapproxy.client.log import log_request
from mapproxy.source import SourceError

class RenderdClient(object):
    def __init__(self, renderd_address, priority=100):
        self.renderd_address = renderd_address
        self.priority = priority

    def send_and_receive(self, tile_mgr, tiles):
        if tile_mgr.meta_grid and len(tiles) == 1:
            # use main_tile_coord as tile_id so that mapproxy-renderd can combine requests
            meta_tile = tile_mgr.meta_grid.meta_tile(tiles[0].coord)
            tile_id = meta_tile.main_tile_coord
        else:
            tile_id = None

        tile_coords = [t.coord for t in tiles if t.coord]
        cache_identifier = tile_mgr.identifier
        return self.send_tile_request(cache_identifier, tile_coords, tile_id=tile_id)

    def send_tile_request(self, cache_identifier, tile_coords, tile_id=None):
        identifier = hashlib.sha1(str((cache_identifier, tile_id or tile_coords))).hexdigest()
        message = {
            'command': 'tile',
            'id': identifier,
            'tiles': tile_coords,
            'cache_identifier': cache_identifier,
            'priority': self.priority
        }
        resp = requests.post(self.renderd_address, data=json.dumps(message))
        return resp.json()

class RenderdTileCreator(object):
    def __init__(self, renderd_address, tile_mgr, dimensions=None, priority=100):
        self.tile_mgr = tile_mgr
        self.dimensions = dimensions
        self.renderd_address = renderd_address
        self.renderd_client = RenderdClient(renderd_address, priority)

    def create_tiles(self, tiles):
        start_time = time.time()
        result = self.renderd_client.send_and_receive(self.tile_mgr, tiles)
        duration = time.time()-start_time

        address = '%s:%s:%r' % (self.renderd_address,
            self.tile_mgr.identifier, [t.coord for t in tiles])

        if result['status'] == 'error':
            log_request(address, 500, None, duration=duration, method='RENDERD')
            raise SourceError(result.get('error_message', 'unknown error from renderd'))

        log_request(address, 200, None, duration=duration, method='RENDERD')

        self.tile_mgr.cache.load_tiles(tiles)
        return tiles

