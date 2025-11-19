# This file is part of the MapProxy project.
# Copyright (C) 2011-2013 Omniscale <http://omniscale.de>

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


from datetime import timezone, datetime
import hashlib
import logging
import os
import re
import threading
import time
from io import BytesIO
from itertools import groupby

from mapproxy.cache.tile import Tile
from mapproxy.cache.base import TileCacheBase, tile_buffer, REMOVE_ON_UNLOCK
from mapproxy.image import ImageSource
from mapproxy.srs import get_epsg_num
from mapproxy.util.fs import ensure_directory
from mapproxy.util.lock import FileLock
from mapproxy.util.sqlite3 import sqlite3


log = logging.getLogger(__name__)


class GeopackageCache(TileCacheBase):
    supports_timestamp = False

    def __init__(
            self, geopackage_file, tile_grid, table_name, with_timestamps=False, timeout=30, wal=False, coverage=None,
            directory_permissions=None, file_permissions=None):
        super(GeopackageCache, self).__init__(coverage)
        self.tile_grid = tile_grid
        self.table_name = self._check_table_name(table_name)
        md5 = hashlib.new('md5', geopackage_file.encode('utf-8'), usedforsecurity=False)
        self.lock_cache_id = 'gpkg' + md5.hexdigest()
        self.geopackage_file = geopackage_file
        self.directory_permissions = directory_permissions
        self.file_permissions = file_permissions

        if coverage:
            self.bbox = coverage.transform_to(self.tile_grid.srs).bbox
        else:
            self.bbox = self.tile_grid.bbox
        # XXX timestamps not implemented
        self.supports_timestamp = with_timestamps
        self.timeout = timeout
        self.wal = wal
        self.ensure_gpkg()
        self._db_conn_cache = threading.local()

    @property
    def db(self):
        if not getattr(self._db_conn_cache, 'db', None):
            self.ensure_gpkg()
            self._db_conn_cache.db = sqlite3.connect(self.geopackage_file, timeout=self.timeout)
        return self._db_conn_cache.db

    def uncached_db(self):
        return sqlite3.connect(self.geopackage_file, timeout=self.timeout)

    def cleanup(self):
        """
        Close all open connection and remove them from cache.
        """
        if getattr(self._db_conn_cache, 'db', None):
            self._db_conn_cache.db.close()
        self._db_conn_cache.db = None

    @staticmethod
    def _check_table_name(table_name):
        """
        >>> GeopackageCache._check_table_name("test")
        'test'
        >>> GeopackageCache._check_table_name("test_2")
        'test_2'
        >>> GeopackageCache._check_table_name("test-2")
        'test-2'
        >>> GeopackageCache._check_table_name("test3;")
        Traceback (most recent call last):
        ...
        ValueError: The table_name test3; contains unsupported characters.
        >>> GeopackageCache._check_table_name("table name")
        Traceback (most recent call last):
        ...
        ValueError: The table_name table name contains unsupported characters.

        @param table_name: A desired name for an geopackage table.
        @return: The name of the table if it is good, otherwise an exception.
        """
        # Regex string indicating table names which will be accepted.
        regex_str = '^[a-zA-Z0-9_-]+$'
        if re.match(regex_str, table_name):
            return table_name
        else:
            msg = ("The table name may only contain alphanumeric characters, an underscore, "
                   "or a dash: {}".format(regex_str))
            log.info(msg)
            raise ValueError("The table_name {0} contains unsupported characters.".format(table_name))

    def ensure_gpkg(self):
        if not os.path.isfile(self.geopackage_file):
            with FileLock(self.geopackage_file + '.init.lck', remove_on_unlock=REMOVE_ON_UNLOCK,
                          directory_permissions=self.directory_permissions, file_permissions=self.file_permissions):
                ensure_directory(self.geopackage_file, self.directory_permissions)
                self._initialize_gpkg()
        else:
            if not self.check_gpkg():
                ensure_directory(self.geopackage_file, self.directory_permissions)
                self._initialize_gpkg()

    def check_gpkg(self):
        if not self._verify_table():
            return False
        if not self._verify_gpkg_contents():
            return False
        if not self._verify_tile_size():
            return False
        return True

    def _verify_table(self):
        with self.uncached_db() as db:
            cur = db.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name=?""",
                             (self.table_name,))
            content = cur.fetchone()
            if not content:
                # Table doesn't exist _initialize_gpkg will create a new one.
                return False
            return True

    def _verify_gpkg_contents(self):
        with self.uncached_db() as db:
            cur = db.execute("""SELECT * FROM gpkg_contents WHERE table_name = ?""", (self.table_name,))

            results = cur.fetchone()
            if not results:
                # Table doesn't exist in gpkg_contents _initialize_gpkg will add it.
                return False
            gpkg_data_type = results[1]
            gpkg_srs_id = results[9]
            cur = db.execute("""SELECT * FROM gpkg_spatial_ref_sys WHERE srs_id = ?""", (gpkg_srs_id,))

            gpkg_coordsys_id = cur.fetchone()[3]
            if gpkg_data_type.lower() != "tiles":
                log.info("The geopackage table name already exists for a data type other than tiles.")
                raise ValueError("table_name is improperly configured.")
            if gpkg_coordsys_id != get_epsg_num(self.tile_grid.srs.srs_code):
                log.info(
                    f"The geopackage {self.geopackage_file} table name {self.table_name} already exists and has an SRS"
                    f" of {gpkg_coordsys_id}, which does not match the configured Mapproxy SRS of"
                    f" {get_epsg_num(self.tile_grid.srs.srs_code)}.")
                raise ValueError("srs is improperly configured.")
            return True

    def _verify_tile_size(self):
        with self.uncached_db() as db:
            cur = db.execute(
                """SELECT * FROM gpkg_tile_matrix WHERE table_name = ?""",
                (self.table_name,))

            results = cur.fetchall()
            results = results[0]
            tile_size = self.tile_grid.tile_size

            if not results:
                # There is no tile conflict. Return to allow the creation of new tiles.
                return True

            gpkg_table_name, gpkg_zoom_level, gpkg_matrix_width, gpkg_matrix_height, gpkg_tile_width, \
                gpkg_tile_height, gpkg_pixel_x_size, gpkg_pixel_y_size = results
            resolution = self.tile_grid.resolution(gpkg_zoom_level)
            if gpkg_tile_width != tile_size[0] or gpkg_tile_height != tile_size[1]:
                log.info(
                    f"The geopackage {self.geopackage_file} table name {self.table_name} already exists and has tile"
                    f" sizes of ({gpkg_tile_width},{gpkg_tile_height}) which is different than the configure tile sizes"
                    f" of ({tile_size[0]},{tile_size[1]}).")
                log.info("The current mapproxy configuration is invalid for this geopackage.")
                raise ValueError("tile_size is improperly configured.")
            if not is_close(gpkg_pixel_x_size, resolution) or not is_close(gpkg_pixel_y_size, resolution):
                log.info(
                    f"The geopackage {self.geopackage_file} table name {self.table_name} already exists and level"
                    f" {gpkg_zoom_level} a resolution of ({gpkg_pixel_x_size:.13f},{gpkg_pixel_y_size:.13f})"
                    f" which is different than the configured resolution of ({resolution:.13f},{resolution:.13f}).")
                log.info("The current mapproxy configuration is invalid for this geopackage.")
                raise ValueError("res is improperly configured.")
            return True

    def _initialize_gpkg(self):
        log.info('initializing Geopackage file %s', self.geopackage_file)
        with sqlite3.connect(self.geopackage_file, timeout=self.timeout) as db:

            if self.wal:
                db.execute('PRAGMA journal_mode=wal')

            proj = get_epsg_num(self.tile_grid.srs.srs_code)

            db.execute(create_gpkg_contents_statement)
            db.execute(create_spatial_ref_sys_statment)
            db.execute(create_tile_matrix_statement)
            db.execute(create_tile_matrix_set_statement)
            db.execute(create_table_statement.format(self.table_name))

            db.execute("PRAGMA foreign_keys = 1;")

            # List of WKT execute statements and data.("""
            wkt_statement = """
                INSERT OR REPLACE INTO gpkg_spatial_ref_sys (
                    srs_id,
                    organization,
                    organization_coordsys_id,
                    srs_name,
                    definition)
                VALUES (?, ?, ?, ?, ?)
            """
            wkt_entries = [
                (3857, 'epsg', 3857, 'WGS 84 / Pseudo-Mercator', proj_string_3857),
                (4326, 'epsg', 4326, 'WGS 84', proj_string_4326),
                (-1, 'NONE', -1, ' ', 'undefined'),
                (0, 'NONE', 0, ' ', 'undefined')
            ]

            if get_epsg_num(self.tile_grid.srs.srs_code) not in [4326, 3857]:
                wkt_entries.append((proj, 'epsg', proj, 'Not provided', "Added via Mapproxy."))
            db.commit()

            # Add geopackage version to the header (1.0)
            db.execute("PRAGMA application_id = 1196437808;")
            db.commit()

            for wkt_entry in wkt_entries:
                try:
                    db.execute(wkt_statement, wkt_entry)
                except sqlite3.IntegrityError:
                    log.info("srs_id already exists.")
            db.commit()

            last_change = datetime.fromtimestamp(
                int(os.environ.get('SOURCE_DATE_EPOCH', time.time())),
                timezone.utc
            )

            # Ensure that tile table exists here, don't overwrite a valid entry.
            try:
                db.execute("""
                    INSERT INTO gpkg_contents (
                        table_name,
                        data_type,
                        identifier,
                        description,
                        last_change,
                        min_x,
                        max_x,
                        min_y,
                        max_y,
                        srs_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (self.table_name,
                          "tiles",
                          self.table_name,
                          "Created with Mapproxy.",
                          last_change,
                          self.bbox[0],
                          self.bbox[2],
                          self.bbox[1],
                          self.bbox[3],
                          proj))
            except sqlite3.IntegrityError:
                pass
            db.commit()

            # Ensure that tile set exists here, don't overwrite a valid entry.
            try:
                db.execute("""
                    INSERT INTO gpkg_tile_matrix_set (table_name, srs_id, min_x, max_x, min_y, max_y)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (
                    self.table_name, proj, self.bbox[0], self.bbox[2], self.bbox[1], self.bbox[3]))
            except sqlite3.IntegrityError:
                pass
            db.commit()

            tile_size = self.tile_grid.tile_size
            for grid, resolution, level in zip(self.tile_grid.grid_sizes,
                                               self.tile_grid.resolutions, range(20)):
                db.execute("""
                    INSERT OR REPLACE INTO gpkg_tile_matrix (table_name, zoom_level, matrix_width,
                        matrix_height, tile_width, tile_height, pixel_x_size, pixel_y_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """, (self.table_name, level, grid[0], grid[1], tile_size[0], tile_size[1], resolution, resolution))
            db.commit()

        if self.file_permissions is not None:
            permission = int(self.file_permissions, base=8)
            log.info("setting file permissions on GeoPackage: ", permission)
            os.chmod(self.geopackage_file, permission)

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
                records.append((level, x, y, content))

        cursor = self.db.cursor()
        try:
            stmt = (f"INSERT OR REPLACE INTO [{self.table_name}] (zoom_level, tile_column, tile_row, tile_data)"
                    f" VALUES (?,?,?,?)")
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
        cur.execute("""SELECT tile_data FROM [{0}]
                WHERE tile_column = ? AND
                      tile_row = ? AND
                      zoom_level = ?""".format(self.table_name), tile.coord)

        content = cur.fetchone()
        if content:
            tile.source = ImageSource(BytesIO(content[0]))
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

        stmt_base = "SELECT tile_column, tile_row, tile_data FROM [{0}] WHERE ".format(self.table_name)

        loaded_tiles = 0

        # SQLite is limited to 1000 args -> split into multiple requests if more arguments are needed
        while coords:
            cur_coords = coords[:999]

            stmt = stmt_base + ' OR '.join(
                ['(tile_column = ? AND tile_row = ? AND zoom_level = ?)'] * (len(cur_coords) // 3))

            cursor = self.db.cursor()
            cursor.execute(stmt, cur_coords)

            for row in cursor:
                loaded_tiles += 1
                tile = tile_dict[(row[0], row[1])]
                data = row[2]
                tile.size = len(data)
                tile.source = ImageSource(BytesIO(data))
            cursor.close()

            coords = coords[999:]

        return loaded_tiles == len(tile_dict)

    def remove_tile(self, tile, dimensions=None):
        cursor = self.db.cursor()
        cursor.execute(
            "DELETE FROM [{0}] WHERE (tile_column = ? AND tile_row = ? AND zoom_level = ?)".format(self.table_name),
            tile.coord)
        self.db.commit()
        if cursor.rowcount:
            return True
        return False

    def remove_level_tiles_before(self, level, timestamp=None, remove_all=False):
        if remove_all:
            cursor = self.db.cursor()
            cursor.execute(
                "DELETE FROM [{0}] WHERE (zoom_level = ?)".format(self.table_name), (level,))
            self.db.commit()
            log.info("Cursor rowcount = {0}".format(cursor.rowcount))
            if cursor.rowcount:
                return True
            return False

    def load_tile_metadata(self, tile, dimensions=None):
        if not self.supports_timestamp:
            # GPKG specification does not include tile timestamps.
            # This sets the timestamp of the tile to epoch (1970s)
            tile.timestamp = -1
        else:
            self.load_tile(tile, dimensions=dimensions)


class GeopackageLevelCache(TileCacheBase):

    def __init__(self, geopackage_dir, tile_grid, table_name, timeout=30, wal=False, coverage=None,
                 directory_permissions=None, file_permissions=None):
        super(GeopackageLevelCache, self).__init__(coverage)
        md5 = hashlib.new('md5', geopackage_dir.encode('utf-8'), usedforsecurity=False)
        self.lock_cache_id = 'gpkg-' + md5.hexdigest()
        self.cache_dir = geopackage_dir
        self.tile_grid = tile_grid
        self.table_name = table_name
        self.timeout = timeout
        self.wal = wal
        self._geopackage = {}
        self._geopackage_lock = threading.Lock()
        self.directory_permissions = directory_permissions
        self.file_premissions = file_permissions

    def _get_level(self, level):
        if level in self._geopackage:
            return self._geopackage[level]

        with self._geopackage_lock:
            if level not in self._geopackage:
                geopackage_filename = os.path.join(self.cache_dir, '%s.gpkg' % level)
                self._geopackage[level] = GeopackageCache(
                    geopackage_filename,
                    self.tile_grid,
                    self.table_name,
                    with_timestamps=False,
                    timeout=self.timeout,
                    wal=self.wal,
                    coverage=self.coverage,
                    directory_permissions=self.directory_permissions,
                    file_permissions=self.file_premissions
                )

        return self._geopackage[level]

    def cleanup(self):
        """
        Close all open connection and remove them from cache.
        """
        with self._geopackage_lock:
            for gp in self._geopackage.values():
                gp.cleanup()

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

        return self._get_level(tile.coord[2]).remove_tile(tile, dimensions=dimensions)

    def remove_level_tiles_before(self, level, timestamp=None, remove_all=False):
        level_cache = self._get_level(level)
        if remove_all:
            level_cache.cleanup()
            os.unlink(level_cache.geopackage_file)
            return True
        else:
            return level_cache.remove_level_tiles_before(level, timestamp)

    def load_tile_metadata(self, tile, dimensions=None):
        return self._get_level(tile.coord[2]).load_tile_metadata(tile, dimensions=dimensions)


def is_close(a, b, rel_tol=1e-09, abs_tol=0.0):
    """
    See PEP 485, added here for legacy versions.

    >>> is_close(0.0, 0.0)
    True
    >>> is_close(1, 1.0)
    True
    >>> is_close(0.01, 0.001)
    False
    >>> is_close(0.0001001, 0.0001, rel_tol=1e-02)
    True
    >>> is_close(0.0001001, 0.0001)
    False

    @param a: An int or float.
    @param b: An int or float.
    @param rel_tol: Relative tolerance - maximumed allow difference between two numbers.
    @param abs_tol: Absolute tolerance - minimum absolute tolerance.
    @return: True if the values a and b are close.

    """
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


create_gpkg_contents_statement = """
    CREATE TABLE IF NOT EXISTS gpkg_contents(
        table_name  TEXT     NOT NULL PRIMARY KEY,
            -- The name of the tiles, or feature table
        data_type   TEXT     NOT NULL,
            -- Type of data stored in the table: "features" per clause Features
            -- (http://www.geopackage.org/spec/#features), "tiles" per clause Tiles
            -- (http://www.geopackage.org/spec/#tiles), or an implementer-defined value for other data
            -- tables per clause in an Extended GeoPackage
        identifier  TEXT     UNIQUE,
            -- A human-readable identifier (e.g. short name) for the table_name content
        description TEXT     DEFAULT '',
            -- A human-readable description for the table_name content
        last_change DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            -- Timestamp value in ISO 8601 format as defined by the strftime function %Y-%m-%dT%H:%M:%fZ
            -- format string applied to the current time
        min_x       DOUBLE,
            -- Bounding box minimum easting or longitude for all content in table_name
        min_y       DOUBLE,
            -- Bounding box minimum northing or latitude for all content in table_name
        max_x       DOUBLE,
            -- Bounding box maximum easting or longitude for all content in table_name
        max_y       DOUBLE,
            -- Bounding box maximum northing or latitude for all content in table_name
        srs_id      INTEGER,
            -- Spatial Reference System ID: gpkg_spatial_ref_sys.srs_id; when data_type is features,
            -- SHALL also match gpkg_geometry_columns.srs_id; When data_type is tiles, SHALL also match
            -- gpkg_tile_matrix_set.srs.id
        CONSTRAINT fk_gc_r_srs_id FOREIGN KEY (srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id))
"""

create_spatial_ref_sys_statment = """
    CREATE TABLE IF NOT EXISTS gpkg_spatial_ref_sys(
        srs_name                 TEXT    NOT NULL,
          -- Human readable name of this SRS (Spatial Reference System)
        srs_id                   INTEGER NOT NULL PRIMARY KEY,
          -- Unique identifier for each Spatial Reference System within a GeoPackage
        organization             TEXT    NOT NULL,
          -- Case-insensitive name of the defining organization e.g. EPSG or epsg
        organization_coordsys_id INTEGER NOT NULL,
          -- Numeric ID of the Spatial Reference System assigned by the organization
        definition               TEXT    NOT NULL,
          -- Well-known Text representation of the Spatial Reference System
        description              TEXT)
"""

create_tile_matrix_statement = """
    CREATE TABLE IF NOT EXISTS gpkg_tile_matrix
         (table_name    TEXT    NOT NULL, -- Tile Pyramid User Data Table Name
          zoom_level    INTEGER NOT NULL, -- 0 <= zoom_level <= max_level for table_name
          matrix_width  INTEGER NOT NULL, -- Number of columns (>= 1) in tile matrix at this zoom level
          matrix_height INTEGER NOT NULL, -- Number of rows (>= 1) in tile matrix at this zoom level
          tile_width    INTEGER NOT NULL, -- Tile width in pixels (>= 1) for this zoom level
          tile_height   INTEGER NOT NULL, -- Tile height in pixels (>= 1) for this zoom level
          pixel_x_size  DOUBLE  NOT NULL, -- In t_table_name srid units or default meters for srid 0 (>0)
          pixel_y_size  DOUBLE  NOT NULL, -- In t_table_name srid units or default meters for srid 0 (>0)
          CONSTRAINT pk_ttm PRIMARY KEY (table_name, zoom_level),
          CONSTRAINT fk_tmm_table_name FOREIGN KEY (table_name) REFERENCES gpkg_contents(table_name))
"""

create_tile_matrix_set_statement = """
    CREATE TABLE IF NOT EXISTS gpkg_tile_matrix_set(
        table_name TEXT    NOT NULL PRIMARY KEY,
            -- Tile Pyramid User Data Table Name
        srs_id     INTEGER NOT NULL,
            -- Spatial Reference System ID: gpkg_spatial_ref_sys.srs_id
        min_x      DOUBLE  NOT NULL,
            -- Bounding box minimum easting or longitude for all content in table_name
        min_y      DOUBLE  NOT NULL,
            -- Bounding box minimum northing or latitude for all content in table_name
        max_x      DOUBLE  NOT NULL,
            -- Bounding box maximum easting or longitude for all content in table_name
        max_y      DOUBLE  NOT NULL,
            -- Bounding box maximum northing or latitude for all content in table_name
        CONSTRAINT fk_gtms_table_name FOREIGN KEY (table_name) REFERENCES gpkg_contents(table_name),
        CONSTRAINT fk_gtms_srs FOREIGN KEY (srs_id) REFERENCES gpkg_spatial_ref_sys (srs_id))
"""

create_table_statement = """
    CREATE TABLE IF NOT EXISTS [{0}]
        (id          INTEGER PRIMARY KEY AUTOINCREMENT, -- Autoincrement primary key
         zoom_level  INTEGER NOT NULL,                  -- min(zoom_level) <= zoom_level <= max(zoom_level)
            -- for t_table_name
         tile_column INTEGER NOT NULL,                  -- 0 to tile_matrix matrix_width - 1
         tile_row    INTEGER NOT NULL,                  -- 0 to tile_matrix matrix_height - 1
         tile_data   BLOB    NOT NULL,                  -- Of an image MIME type specified in clauses Tile
            -- Encoding PNG, Tile Encoding JPEG, Tile Encoding WEBP
         UNIQUE (zoom_level, tile_column, tile_row))
"""

proj_string_3857 = """
    PROJCS["WGS 84 / Pseudo-Mercator",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,\
    AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],\
    UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],\
    PROJECTION["Mercator_1SP"],PARAMETER["central_meridian",0],PARAMETER["scale_factor",1],PARAMETER["false_easting",0],\
    PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["X",EAST],AXIS["Y",NORTH],\
    AUTHORITY["EPSG","3857"]]\
"""

proj_string_4326 = """
    GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],\
    AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,\
    AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]\
"""
