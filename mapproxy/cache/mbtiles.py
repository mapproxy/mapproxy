# This file is part of the MapProxy project.
# Copyright (C) 2011-2013 Omniscale <http://omniscale.de>
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
import time
import sqlite3
import threading
from cStringIO import StringIO

from mapproxy.image import ImageSource
from mapproxy.cache.base import TileCacheBase, FileBasedLocking, tile_buffer
from mapproxy.util.fs import ensure_directory
from mapproxy.util.lock import FileLock

import logging
log = logging.getLogger(__name__)

def sqlite_datetime_to_timestamp(datetime):
    if datetime is None:
        return None
    d = time.strptime(datetime, "%Y-%m-%d %H:%M:%S")
    return time.mktime(d)

class MBTilesCache(TileCacheBase, FileBasedLocking):
    supports_timestamp = False

    def __init__(self, mbtile_file, lock_dir=None, with_timestamps=False):
        if lock_dir:
            self.lock_dir = lock_dir
        else:
            self.lock_dir = mbtile_file + '.locks'
        self.lock_timeout = 60
        self.cache_dir = mbtile_file # for lock_id generation by FileBasedLocking
        self.mbtile_file = mbtile_file
        self.supports_timestamp = with_timestamps
        self.ensure_mbtile()
        self._db_conn_cache = threading.local()

    @property
    def db(self):
        if not getattr(self._db_conn_cache, 'db', None):
            self.ensure_mbtile()
            self._db_conn_cache.db = sqlite3.connect(self.mbtile_file)
        return self._db_conn_cache.db

    def cleanup(self):
        """
        Close all open connection and remove them from cache.
        """
        if getattr(self._db_conn_cache, 'db', None):
            self._db_conn_cache.db.close()
        self._db_conn_cache.db = None

    def ensure_mbtile(self):
        if not os.path.exists(self.mbtile_file):
            with FileLock(os.path.join(self.lock_dir, 'init.lck'),
                timeout=self.lock_timeout,
                remove_on_unlock=True):
                if not os.path.exists(self.mbtile_file):
                    ensure_directory(self.mbtile_file)
                    self._initialize_mbtile()

    def _initialize_mbtile(self):
        log.info('initializing MBTile file %s', self.mbtile_file)
        db  = sqlite3.connect(self.mbtile_file)
        stmt = """
            CREATE TABLE tiles (
                zoom_level integer,
                tile_column integer,
                tile_row integer,
                tile_data blob
        """

        if self.supports_timestamp:
            stmt += """
                , last_modified datetime DEFAULT (datetime('now','localtime'))
            """
        stmt += """
            );
        """
        db.execute(stmt)

        db.execute("""
            CREATE TABLE metadata (name text, value text);
        """)
        db.execute("""
            CREATE UNIQUE INDEX idx_tile on tiles
                (zoom_level, tile_column, tile_row);
        """)
        db.commit()
        db.close()

    def update_metadata(self, name='', description='', version=1, overlay=True, format='png'):
        db  = sqlite3.connect(self.mbtile_file)
        db.execute("""
            CREATE TABLE IF NOT EXISTS metadata (name text, value text);
        """)
        db.execute("""DELETE FROM metadata;""")

        if overlay:
            layer_type = 'overlay'
        else:
            layer_type = 'baselayer'

        db.executemany("""
            INSERT INTO metadata (name, value) VALUES (?,?)
            """,
            (
                ('name', name),
                ('description', description),
                ('version', version),
                ('type', layer_type),
                ('format', format),
            )
        )
        db.commit()
        db.close()

    def is_cached(self, tile):
        if tile.coord is None:
            return True
        if tile.source:
            return True

        return self.load_tile(tile)

    def store_tile(self, tile):
        if tile.stored:
            return True
        with tile_buffer(tile) as buf:
            content = buffer(buf.read())
            x, y, level = tile.coord
            cursor = self.db.cursor()
            if self.supports_timestamp:
                stmt = "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data, last_modified) VALUES (?,?,?,?, datetime(?, 'unixepoch', 'localtime'))"
                cursor.execute(stmt, (level, x, y, content, time.time()))
            else:
                stmt = "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?,?,?,?)"
                cursor.execute(stmt, (level, x, y, content))
            self.db.commit()
            return True

    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True

        cur = self.db.cursor()
        if self.supports_timestamp:
            cur.execute('''SELECT tile_data, last_modified
                FROM tiles
                WHERE tile_column = ? AND
                      tile_row = ? AND
                      zoom_level = ?''', tile.coord)
        else:
            cur.execute('''SELECT tile_data FROM tiles
                WHERE tile_column = ? AND
                      tile_row = ? AND
                      zoom_level = ?''', tile.coord)

        content = cur.fetchone()
        if content:
            tile.source = ImageSource(StringIO(content[0]))
            if self.supports_timestamp:
                tile.timestamp = sqlite_datetime_to_timestamp(content[1])
            return True
        else:
            return False

    def load_tiles(self, tiles, with_metadata=False):
        #associate the right tiles with the cursor
        tile_dict = {}
        coords = []
        for tile in tiles:
            if tile.source or tile.coord is None:
                continue
            x, y, level = tile.coord
            coords.append(x)
            coords.append(y)
            coords.append(level)
            tile_dict[(x, y)] = tile

        if self.supports_timestamp:
            stmt = "SELECT tile_column, tile_row, tile_data, last_modified FROM tiles WHERE "
        else:
            stmt = "SELECT tile_column, tile_row, tile_data FROM tiles WHERE "
        stmt += ' OR '.join(['(tile_column = ? AND tile_row = ? AND zoom_level = ?)'] * (len(coords)//3))

        cursor = self.db.cursor()
        cursor.execute(stmt, coords)

        loaded_tiles = 0
        for row in cursor:
            loaded_tiles += 1
            tile = tile_dict[(row[0], row[1])]
            data = row[2]
            tile.size = len(data)
            tile.source = ImageSource(StringIO(data))
            if self.supports_timestamp:
                tile.timestamp = sqlite_datetime_to_timestamp(row[3])
        cursor.close()
        return loaded_tiles == len(tile_dict)

    def remove_tile(self, tile):
        cursor = self.db.cursor()
        cursor.execute(
            "DELETE FROM tiles WHERE (tile_column = ? AND tile_row = ? AND zoom_level = ?)",
            tile.coord)
        self.db.commit()
        if cursor.rowcount:
            return True
        return False

    def remove_level_tiles_before(self, level, timestamp):
        if timestamp == 0:
            cursor = self.db.cursor()
            cursor.execute(
                "DELETE FROM tiles WHERE (zoom_level = ?)",
                (level, ))
            self.db.commit()
            if cursor.rowcount:
                return True
            return False

        if self.supports_timestamp:
            cursor = self.db.cursor()
            cursor.execute(
                "DELETE FROM tiles WHERE (zoom_level = ? AND last_modified < datetime(?, 'unixepoch', 'localtime'))",
                (level, timestamp))
            self.db.commit()
            if cursor.rowcount:
                return True
            return False

    def load_tile_metadata(self, tile):
        if not self.supports_timestamp:
            # MBTiles specification does not include timestamps.
            # This sets the timestamp of the tile to epoch (1970s)
            tile.timestamp = -1
        else:
            self.load_tile(tile)

class MBTilesLevelCache(TileCacheBase, FileBasedLocking):
    supports_timestamp = True

    def __init__(self, mbtiles_dir, lock_dir=None):
        if lock_dir:
            self.lock_dir = lock_dir
        else:
            self.lock_dir = mbtiles_dir + '.locks'
        self.lock_timeout = 60
        self.cache_dir = mbtiles_dir
        self._mbtiles = {}
        self._mbtiles_lock = threading.Lock()

    def _get_level(self, level):
        if level in self._mbtiles:
            return self._mbtiles[level]

        with self._mbtiles_lock:
            if level not in self._mbtiles:
                mbtile_filename = os.path.join(self.cache_dir, '%s.mbtile' % level)
                self._mbtiles[level] = MBTilesCache(
                    mbtile_filename,
                    lock_dir=self.lock_dir,
                    with_timestamps=True,
                )

        return self._mbtiles[level]

    def is_cached(self, tile):
        if tile.coord is None:
            return True
        if tile.source:
            return True

        return self._get_level(tile.coord[2]).is_cached(tile)

    def store_tile(self, tile):
        if tile.stored:
            return True

        return self._get_level(tile.coord[2]).store_tile(tile)

    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True

        return self._get_level(tile.coord[2]).load_tile(tile, with_metadata=with_metadata)

    def load_tiles(self, tiles, with_metadata=False):
        level = None
        for tile in tiles:
            if tile.source or tile.coord is None:
                continue
            level = tile.coord[2]
            break

        if not level:
            return True

        return self._get_level(level).load_tiles(tiles, with_metadata=with_metadata)

    def remove_tile(self, tile):
        if tile.coord is None:
            return True

        return self._get_level(tile.coord[2]).remove_tile(tile)

    def load_tile_metadata(self, tile):
        self.load_tile(tile)

    def remove_level_tiles_before(self, level, timestamp):
        level_cache = self._get_level(level)
        if timestamp == 0:
            level_cache.cleanup()
            os.unlink(level_cache.mbtile_file)
            return True
        else:
            return level_cache.remove_level_tiles_before(level, timestamp)

