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
import os
import sqlite3
import threading
from cStringIO import StringIO

from mapproxy.image import ImageSource
from mapproxy.cache.base import TileCacheBase, FileBasedLocking, tile_buffer
from mapproxy.util.times import parse_httpdate
from mapproxy.util.lock import FileLock

import logging
log = logging.getLogger(__name__)

class MBTilesCache(TileCacheBase, FileBasedLocking):
    def __init__(self, mbtile_file):
        self.lock_cache_id = mbtile_file
        self.lock_dir = mbtile_file + '.locks'
        self.lock_timeout = 60
        self.mbtile_file = mbtile_file
        self.ensure_mbtile()
        self._db_cache = threading.local()
    
    @property
    def db(self):
        if not hasattr(self._db_cache, 'db'):
            self.ensure_mbtile()
            self._db_cache.db = sqlite3.connect(self.mbtile_file)
        return self._db_cache.db
    
    def ensure_mbtile(self):
        if not os.path.exists(self.mbtile_file):
            with FileLock(os.path.join(self.lock_dir, 'init.lck'),
                timeout=self.lock_timeout,
                remove_on_unlock=True):
                if not os.path.exists(self.mbtile_file):
                    self._initialize_mbtile()
    
    def _initialize_mbtile(self):
        log.info('initializing MBTile file %s', self.mbtile_file)
        db  = sqlite3.connect(self.mbtile_file)
        db.execute("""
            CREATE TABLE tiles (
                zoom_level integer,
                tile_column integer,
                tile_row integer,
                tile_data blob);
        """)
        db.execute("""
            CREATE UNIQUE INDEX idx_tile on tiles
                (zoom_level, tile_column, tile_row);
        """)
        db.commit()
        db.close()
    
    def is_cached(self, tile):
        if tile.coord is None:
            return True
        if tile.source:
            return True
        
        cur = self.db.cursor()
        cur.execute('''SELECT 1 FROM tiles
            WHERE tile_column = ? AND
                  tile_row = ? AND
                  zoom_level = ?''', tile.coord)
        if cur.fetchone():
            return True
        else:
            return False
    
    def store_tile(self, tile):
        if tile.stored:
            return True
        with tile_buffer(tile) as buf:
            content = buffer(buf.read())
            x, y, level = tile.coord
            cursor = self.db.cursor()
            stmt = "INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?,?,?,?)"
            try:
                cursor.execute(stmt, (level, x, y, buffer(content)))
                self.db.commit()
            except (sqlite3.IntegrityError, sqlite3.OperationalError), e:
                #tile is already present, updating data
                stmt = """UPDATE tiles SET tile_data = ?
                    WHERE tile_column = ? AND
                          tile_row = ? AND
                          zoom_level = ?"""
                try:
                    cursor.execute(stmt, (buffer(content), x, y, level))
                    self.db.commit()
                except sqlite3.OperationalError, e:
                    #database is locked
                    print e
                    return False
            return True
    
    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return
        
        cur = self.db.cursor()
        cur.execute('''SELECT tile_data FROM tiles
            WHERE tile_column = ? AND
                  tile_row = ? AND
                  zoom_level = ?''', tile.coord)
        content = cur.fetchone()
        if content:
            tile.source = ImageSource(StringIO(content[0]))
            return True
        else:
            return False
    
    def load_tiles_(self, tiles, with_metadata=False):
        #associate the right tiles with the cursor
        tile_dict = {}
        coords = []
        for tile in tiles:
            if tile.source or tile.coord is None:
                continue
            x, y, level = tile.coord
            coords.append(level)
            coords.append(x)
            coords.append(y)
            tile_dict[(x, y)] = tile

        stmt = "SELECT tile_column, tile_row, tile_data FROM tiles WHERE " 
        stmt += ' OR '.join(['(zoom_level = ? AND tile_column = ? AND tile_row = ?)'] * (len(coords)//3))

        cursor = self.db.cursor()
        cursor.execute(stmt, coords)
        
        for row in cursor:
            tile = tile_dict[(row[0], row[1])]
            data = row[2]
            tile.size = len(data)
            tile.source = ImageSource(StringIO(data), size=tile.size)
        cursor.close()
        return tiles
    
    def remove_tile(self, tile):
        cursor = self.db.cursor()
        cursor.execute(
            "DELETE FROM tiles WHERE (zoom_level = ? AND tile_column = ? AND tile_row = ?)",
            tile.coord)
        if cursor.rowcount:
            return True
        return False