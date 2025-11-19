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

import glob
import hashlib
import os
import threading
import time
from io import BytesIO
from itertools import groupby

from mapproxy.cache.tile import Tile
from mapproxy.image import ImageSource
from mapproxy.cache.base import TileCacheBase, tile_buffer, REMOVE_ON_UNLOCK
from mapproxy.util.fs import ensure_directory
from mapproxy.util.lock import FileLock
from mapproxy.util.sqlite3 import sqlite3

import logging
log = logging.getLogger(__name__)

if not hasattr(glob, 'escape'):
    import re

    def escape_str(pathname: str) -> str:
        return re.sub(r'([*?[])', r'[\1]', pathname)

    glob.escape = escape_str  # type: ignore[assignment]


def sqlite_datetime_to_timestamp(datetime):
    if datetime is None:
        return None
    d = time.strptime(datetime, "%Y-%m-%d %H:%M:%S")
    return time.mktime(d)


class MBTilesCache(TileCacheBase):
    supports_timestamp = False

    def __init__(self, mbtile_file, with_timestamps=False, timeout=30, wal=False, ttl=0, coverage=None,
                 directory_permissions=None, file_permissions=None):
        super(MBTilesCache, self).__init__(coverage)
        md5 = hashlib.new('md5', mbtile_file.encode('utf-8'), usedforsecurity=False)
        self.lock_cache_id = 'mbtiles-' + md5.hexdigest()
        self.mbtile_file = mbtile_file
        self.directory_permissions = directory_permissions
        self.file_permissions = file_permissions
        self.supports_timestamp = with_timestamps
        self.ttl = with_timestamps and ttl or 0
        self.timeout = timeout
        self.wal = wal
        self.ensure_mbtile()
        self._db_conn_cache = threading.local()

    @property
    def db(self):
        if not getattr(self._db_conn_cache, 'db', None):
            self.ensure_mbtile()
            self._db_conn_cache.db = sqlite3.connect(self.mbtile_file, self.timeout)
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
            with FileLock(self.mbtile_file + '.init.lck', remove_on_unlock=REMOVE_ON_UNLOCK,
                          directory_permissions=self.directory_permissions, file_permissions=self.file_permissions):
                if not os.path.exists(self.mbtile_file):
                    ensure_directory(self.mbtile_file, self.directory_permissions)
                    self._initialize_mbtile()

    def _initialize_mbtile(self):
        log.info('initializing MBTile file %s', self.mbtile_file)
        with sqlite3.connect(self.mbtile_file) as db:
            if self.wal:
                db.execute('PRAGMA journal_mode=wal')

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

        if self.file_permissions:
            permission = int(self.file_permissions, base=8)
            log.info("setting file permissions on MBTile file: %s", permission)
            os.chmod(self.mbtile_file, permission)

    def update_metadata(self, name='', description='', version=1, overlay=True, format='png'):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS metadata (name text, value text);
        """)
        self.db.execute("""DELETE FROM metadata;""")

        if overlay:
            layer_type = 'overlay'
        else:
            layer_type = 'baselayer'

        self.db.executemany("""
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
        self.db.commit()

    def is_cached(self, tile, dimensions=None):
        if tile.coord is None:
            return True
        if tile.source:
            return True

        return self.load_tile(tile, dimensions=dimensions)

    def store_tile(self, tile, dimensions=None):
        if tile.stored:
            return True
        return self._store_bulk([tile])

    def store_tiles(self, tiles, dimensions=None):
        tiles = [t for t in tiles if not t.stored]
        return self._store_bulk(tiles)

    def _store_bulk(self, tiles):
        records = []
        # tile_buffer (as_buffer) will encode the tile to the target format
        # we collect all tiles before, to avoid having the db transaction
        # open during this slow encoding
        for tile in tiles:
            with tile_buffer(tile) as buf:
                content = buf.read()
                x, y, level = tile.coord
                if self.supports_timestamp:
                    records.append((level, x, y, content, time.time()))
                else:
                    records.append((level, x, y, content))

        cursor = self.db.cursor()
        try:
            if self.supports_timestamp:
                stmt = ("INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data, last_modified)"
                        " VALUES (?,?,?,?, datetime(?, 'unixepoch', 'localtime'))")
                cursor.executemany(stmt, records)
            else:
                stmt = "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?,?,?,?)"
                cursor.executemany(stmt, records)
            self.db.commit()
        except sqlite3.OperationalError as ex:
            log.warning('unable to store tile: %s', ex)
            return False
        return True

    def load_tile(self, tile: Tile, with_metadata=False, dimensions=None) -> bool:
        if tile.source or tile.coord is None:
            return True

        cur = self.db.cursor()
        if self.supports_timestamp:
            stmt = '''SELECT tile_data, last_modified
                FROM tiles
                WHERE tile_column = ? AND
                      tile_row = ? AND
                      zoom_level = ?'''
        else:
            stmt = '''SELECT tile_data FROM tiles
                WHERE tile_column = ? AND
                      tile_row = ? AND
                      zoom_level = ?'''

        if self.ttl:
            stmt += " AND datetime('now', 'localtime', '%d seconds') < last_modified" % -self.ttl

        cur.execute(stmt, tile.coord)

        content = cur.fetchone()
        if content:
            tile.source = ImageSource(BytesIO(content[0]))
            if self.supports_timestamp:
                tile.timestamp = sqlite_datetime_to_timestamp(content[1])
            return True
        else:
            return False

    def load_tiles(self, tiles: list[Tile], with_metadata=False, dimensions=None) -> bool:
        # associate the right tiles with the cursor
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

        if not tile_dict:
            # all tiles loaded or coords are None
            return True

        if self.supports_timestamp:
            stmt_base = "SELECT tile_column, tile_row, tile_data, last_modified FROM tiles WHERE "
            if self.ttl:
                ttl_condition = "datetime('now', 'localtime', '%d seconds') < last_modified" % -self.ttl
                stmt_base += ttl_condition + ' AND '
        else:
            stmt_base = "SELECT tile_column, tile_row, tile_data FROM tiles WHERE "

        loaded_tiles = 0

        # SQLite is limited to 1000 args -> split into multiple requests if more arguments are needed
        while coords:
            cur_coords = coords[:999]

            stmt = stmt_base + '(' + ' OR '.join(
                ['(tile_column = ? AND tile_row = ? AND zoom_level = ?)'] * (len(cur_coords) // 3)) + ')'

            cursor = self.db.cursor()
            cursor.execute(stmt, cur_coords)

            for row in cursor:
                loaded_tiles += 1
                tile = tile_dict[(row[0], row[1])]
                data = row[2]
                tile.size = len(data)
                tile.source = ImageSource(BytesIO(data))
                if self.supports_timestamp:
                    tile.timestamp = sqlite_datetime_to_timestamp(row[3])
            cursor.close()

            coords = coords[999:]

        return loaded_tiles == len(tile_dict)

    def remove_tile(self, tile, dimensions=None):
        cursor = self.db.cursor()
        cursor.execute(
            "DELETE FROM tiles WHERE (tile_column = ? AND tile_row = ? AND zoom_level = ?)",
            tile.coord)
        self.db.commit()
        if cursor.rowcount:
            return True
        return False

    def remove_level_tiles_before(self, level, timestamp=None, remove_all=False):
        if remove_all:
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

    def load_tile_metadata(self, tile, dimensions=None):
        if not self.supports_timestamp:
            # MBTiles specification does not include timestamps.
            # This sets the timestamp of the tile to epoch (1970s)
            tile.timestamp = -1
        else:
            self.load_tile(tile, dimensions=dimensions)


class MBTilesLevelCache(TileCacheBase):
    supports_timestamp = True

    def __init__(self, mbtiles_dir, timeout=30, wal=False, ttl=0, coverage=None,
                 directory_permissions=None, file_permissions=None):
        super(MBTilesLevelCache, self).__init__(coverage)
        md5 = hashlib.new('md5', mbtiles_dir.encode('utf-8'), usedforsecurity=False)
        self.lock_cache_id = 'sqlite-' + md5.hexdigest()
        self.cache_dir = mbtiles_dir
        self.directory_permissions = directory_permissions
        self.file_permissions = file_permissions
        self._mbtiles = {}
        self.timeout = timeout
        self.wal = wal
        self.ttl = ttl
        self._mbtiles_lock = threading.Lock()

    def _get_level(self, level):
        if level in self._mbtiles:
            return self._mbtiles[level]

        with self._mbtiles_lock:
            if level not in self._mbtiles:
                mbtile_filename = os.path.join(self.cache_dir, '%s.mbtiles' % level)
                self._mbtiles[level] = MBTilesCache(
                    mbtile_filename,
                    with_timestamps=True,
                    timeout=self.timeout,
                    wal=self.wal,
                    ttl=self.ttl,
                    coverage=self.coverage,
                    directory_permissions=self.directory_permissions,
                    file_permissions=self.file_permissions
                )

        return self._mbtiles[level]

    def cleanup(self):
        """
        Close all open connection and remove them from cache.
        """
        with self._mbtiles_lock:
            for mbtile in self._mbtiles.values():
                mbtile.cleanup()

    def is_cached(self, tile, dimensions=None):
        if tile.coord is None:
            return True
        if tile.source:
            return True

        return self._get_level(tile.coord[2]).is_cached(tile, dimensions=dimensions)

    def store_tile(self, tile, dimensions=None):
        if tile.stored:
            return True

        return self._get_level(tile.coord[2]).store_tile(tile, dimensions=dimensions)

    def store_tiles(self, tiles, dimensions=None):
        failed = False
        for level, tiles in groupby(tiles, key=lambda t: t.coord[2]):
            tiles = [t for t in tiles if not t.stored]
            res = self._get_level(level).store_tiles(tiles, dimensions=dimensions)
            if not res:
                failed = True
        return failed

    def load_tile(self, tile, with_metadata=False, dimensions=None):
        if tile.source or tile.coord is None:
            return True

        return self._get_level(tile.coord[2]).load_tile(tile, with_metadata=with_metadata, dimensions=dimensions)

    def load_tiles(self, tiles, with_metadata=False, dimensions=None):
        level = None
        for tile in tiles:
            if tile.source or tile.coord is None:
                continue
            level = tile.coord[2]
            break

        if not level:
            return True

        return self._get_level(level).load_tiles(tiles, with_metadata=with_metadata, dimensions=dimensions)

    def remove_tile(self, tile, dimensions=None):
        if tile.coord is None:
            return True

        return self._get_level(tile.coord[2]).remove_tile(tile)

    def load_tile_metadata(self, tile, dimensions=None):
        self.load_tile(tile, dimensions=dimensions)

    def remove_level_tiles_before(self, level, timestamp=None, remove_all=False):
        level_cache = self._get_level(level)
        if remove_all:
            level_cache.cleanup()
            os.unlink(level_cache.mbtile_file)
            for file in glob.glob("%s-*" % glob.escape(level_cache.mbtile_file)):
                os.unlink(file)
            return True
        else:
            return level_cache.remove_level_tiles_before(level, timestamp)
