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

import errno
import json

from mapproxy.seed.seeder import TileProcessor
from mapproxy.cache.renderd import RenderdClient
from mapproxy.util.async import zmq_proc_context

class TileRenderdProcessor(TileProcessor):
    """
    Delegated tile processing to mapproxy-renderd.
    """
    def __init__(self, tile_manager, renderd_address, size=2, dry_run=False):
        TileProcessor.__init__(self, dry_run=dry_run)
        self.tile_manager = tile_manager
        self.max_in_process = size
        self.in_process = 0
        self.render_priority = 10
        context = zmq_proc_context()
        self.client = RenderdClient(context, renderd_address, self.render_priority)
    
    def process_tiles(self, tiles):
        if self.in_process >= self.max_in_process:
            result = self.client.receive_result()
            self.in_process -= 1
        
        # TODO handle errors in renderd
        
        cache_identifier = self.tile_manager.identifier
        self.client.send_tile_request(cache_identifier, tiles)

        self.in_process += 1
        
        try:
            while True:
                result = self.client.receive_result(block=False)
                if result is None:
                    break
                self.in_process -= 1
        except zmq.ZMQError, ex:
            if ex.errno != errno.EAGAIN:
                raise
    
    def stop(self):
        while self.in_process:
            result = self.client.receive_result()
            self.in_process -= 1