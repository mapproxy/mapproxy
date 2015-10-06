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

from mapproxy.image import ImageSource
from mapproxy.cache.tile import Tile
from mapproxy.cache.base import TileCacheBase

from pymongo import MongoClient

import gridfs
import hashlib

import logging
log = logging.getLogger(__name__)

class MongoDBCache(TileCacheBase):
    def __init__(self, url, name, grid):
        self.db = MongoClient(url)
        self.fs = gridfs.GridFS(self.db.mapproxy)
        self.name = name
        self.grid = grid
        self.lock_cache_id = 'mongodb-' + hashlib.md5((url + name + grid).encode('utf-8')).hexdigest()

    def is_cached(self, tile):
        if tile.source:
            return True
        return self.load_tile(tile)

    def store_tile(self, tile): 
        if tile.stored:
            return True
        x,y,z = tile.coord
        f = self.fs.new_file(x=x,y=y,z=z,name=self.name,grid=self.grid)
        f.write(tile.source_buffer())
        f.close()
        return True

    def _tile_doc(self, tile):
        return {
            'x': tile.coord[0],
            'y': tile.coord[1],
            'z': tile.coord[2],
            'name': self.name,
            'grid': self.grid
        }

    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True 
        tile_data = self.db.mapproxy.fs.files.find_one(self._tile_doc(tile))
        if tile_data is not None:
            tile_file = self.fs.get(tile_data['_id'])
            tile.source = ImageSource(tile_file)
            tile.timestamp = tile_file.upload_date
            return True
        x,y,z = tile.coord
        return False

    def remove_tile(self, tile):
        tile_data = self.db.mapproxy.fs.files.find_one(self._tile_doc(tile))
        if tile_data is None:
            return True
        if tile_data is not None:
            self.fs.delete(tile_data['_id'])
            return True
