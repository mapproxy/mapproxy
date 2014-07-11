from __future__ import print_function, division

import errno
import os
import sqlite3
import time
from contextlib import contextmanager
from functools import partial
from mapproxy.compat.itertools import groupby
from six.moves import map
from six.moves import zip


from mapproxy.compat import BytesIO
from mapproxy.image import ImageSource, is_single_color_image
from mapproxy.cache.base import tile_buffer
from mapproxy.cache.base import TileCacheBase


class Metadata(object):
    def __init__(self, db, layer_name, tile_grid, file_ext):
        self.layer_id = layer_name
        self.grid = tile_grid
        self.file_ext = file_ext
        self.db = db
        self.table_name = "metadata"

    def _create_metadata_table(self):
        cursor = self.db.cursor()
        stmt = """CREATE TABLE IF NOT EXISTS %s (
            layer_id TEXT NOT NULL,
            matrix_id TEXT NOT NULL,
            matrix_set_id TEXT NOT NULL,
            table_name TEXT NOT NULL,
            bbox TEXT,
            srs TEXT,
            format TEXT,
            min_tile_col INTEGER,
            max_tile_col INTEGER,
            min_tile_row INTEGER,
            max_tile_row INTEGER,
            tile_width INTEGER,
            tile_height INTEGER,
            matrix_width INTEGER,
            matrix_height INTEGER,
            CONSTRAINT unique_rows UNIQUE (layer_id, matrix_id, matrix_set_id, table_name)
            )""" % (self.table_name)
        cursor.execute(stmt)
        self.db.commit()

    def store(self, tile_set):
        self.tile_set_table_name(tile_set)
        params = self._tile_set_params_dict(tile_set)
        cursor = self.db.cursor()
        stmt = """CREATE TABLE IF NOT EXISTS %s (
            x INTEGER,
            y INTEGER,
            data BLOB,
            date_added INTEGER,
            unique_tile TEXT
            )""" % (tile_set.table_name)
        cursor.execute(stmt)
        stmt = """CREATE UNIQUE INDEX IF NOT EXISTS idx_%s_xy ON %s (x, y)""" % (tile_set.table_name, tile_set.table_name)
        cursor.execute(stmt)
        stmt = """INSERT INTO %s (layer_id, bbox, srs, format, min_tile_col, max_tile_col, min_tile_row,
            max_tile_row, tile_width, tile_height, matrix_width, matrix_height, matrix_id, matrix_set_id, table_name)
            VALUES (:layer_id, :bbox, :srs, :format, :min_tile_col, :max_tile_col, :min_tile_row, :max_tile_row,
                    :tile_width, :tile_height, :matrix_width, :matrix_height, :matrix_id,
                    :matrix_set_name, :table_name)""" % (self.table_name)
        try:
            cursor.execute(stmt, params)
        except sqlite3.IntegrityError as e:
            pass
        self.db.commit()

    def _tile_set_params_dict(self, tile_set):
        level = tile_set.level
        tile_width, tile_height = self.grid.tile_size
        matrix_width, matrix_height = self.grid.grid_sizes[level]
        params = {
        'layer_id' : self.layer_id,
        'bbox' : ', '.join(map(str, [v for v in self.grid.bbox])),
        'srs' : self.grid.srs.srs_code,
        'format' : self.file_ext,
        'min_tile_col' : tile_set.grid[0],
        'max_tile_col' : tile_set.grid[2],
        'min_tile_row' : tile_set.grid[1],
        'max_tile_row' : tile_set.grid[3],
        'tile_width' : tile_width,
        'tile_height' : tile_height,
        'matrix_width' : matrix_width,
        'matrix_height' : matrix_height,
        'matrix_id' : level,
        'matrix_set_name' : self.grid.name,
        'table_name' : tile_set.table_name
        }
        return params

    def tile_set_table_name(self, tile_set):
        if tile_set.table_name:
            return tile_set.table_name

        level = tile_set.level
        grid = tile_set.grid
        query = " AND ".join(["layer_id = ?",
                "min_tile_col = ?",
                "min_tile_row = ?",
                "max_tile_col = ?",
                "max_tile_row = ?",
                "matrix_id = ?",
                "matrix_set_id = ?"])
        cursor = self.db.cursor()
        stmt = "SELECT table_name FROM %s WHERE %s" % (self.table_name, query)
        cursor.execute(stmt, (self.layer_id, grid[0], grid[1], grid[2], grid[3], level, self.grid.name))
        result = cursor.fetchone()
        if result is not None:
            table_name = result['table_name']
        else:
            x0, y0, x1, y1 = tile_set.grid
            table_name = "tileset_%s_%s_%d_%d_%d_%d_%d" % (self.layer_id, self.grid.name, tile_set.level, x0, y0, x1, y1)

        tile_set.table_name = table_name
        return table_name


class TileSet(object):

    def __init__(self, db, level, file_ext, grid, unique_tiles):
        self.db = db
        self.table_name = None
        self.file_ext = file_ext
        self._metadata_stored = False
        self.grid = grid
        self.level = level
        self.unique_tiles = unique_tiles

    def get_tiles(self, tiles):
        stmt = "SELECT x, y, data, date_added, unique_tile FROM %s WHERE " % (self.table_name)
        stmt += ' OR '.join(['(x = ? AND y = ?)'] * len(tiles))

        coords = []
        for tile in tiles:
            x, y, level = tile.coord
            coords.append(x)
            coords.append(y)

        cursor = self.db.cursor()
        try:
            cursor.execute(stmt, coords)
        except sqlite3.OperationalError as e:
            print(e)

        #associate the right tiles with the cursor
        tile_dict = {}
        for tile in tiles:
            x, y, level = tile.coord
            tile_dict[(x, y)] = tile

        for row in cursor:
            tile = tile_dict[(row['x'], row['y'])]
            #TODO get unique tiles if row['data'] == null
            data = row['data'] if row['data'] is not None else self.unique_tiles.get_data(row['unique_tile'])
            tile.timestamp = row['date_added']
            tile.size = len(data)
            tile.source = ImageSource(BytesIO(data), size=tile.size)
        cursor.close()
        return tiles

    def is_cached(self, tile):
        x, y, level = tile.coord
        cursor = self.db.cursor()
        stmt = "SELECT date_added from %s WHERE x = ? AND y = ?" % (self.table_name)
        try:
            cursor.execute(stmt, (x, y))
        except sqlite3.OperationalError as e:
            #table does not exist
            #print e
            pass
        result = cursor.fetchone()
        if result is not None:
            return True
        return False

    def set_tile(self, tile):
        x, y, z = tile.coord
        assert self.grid[0] <= x < self.grid[2]
        assert self.grid[1] <= y < self.grid[3]


        color = is_single_color_image(tile.source.as_image())

        with tile_buffer(tile) as buf:
            _data = buffer(buf.read())

        if color:
            data = None
            _color = ''.join('%02x' % v for v in color)
            self.unique_tiles.set_data(_data, _color)
        else:
            #get value of cStringIO-Object and store it to a buffer
            data = _data
            _color = None

        timestamp = int(time.time())
        cursor = self.db.cursor()
        stmt = "INSERT INTO %s (x, y, data, date_added, unique_tile) VALUES (?,?,?,?,?)" % (self.table_name)
        try:
            cursor.execute(stmt, (x, y, data, timestamp, _color))
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as e:
            #tile is already present, updating data
            stmt = "UPDATE %s SET data = ?, date_added = ?, unique_tile = ? WHERE x = ? AND y = ?" % (self.table_name)
            try:
                cursor.execute(stmt, (data, timestamp, _color, x, y))
            except sqlite3.OperationalError as e:
                #database is locked
                print(e)
                return False
        return True

    def set_tiles(self, tiles):
        result = all([self.set_tile(t) for t in tiles])
        self.db.commit()
        return result

    def remove_tiles(self, tiles):
        cursor = self.db.cursor()
        stmt = "DELETE FROM %s WHERE" % (self.table_name)
        stmt += ' OR '.join(['(x = ? AND y = ?)'] * len(tiles))
        coords = []
        for t in tiles:
            x, y, level = t.coord
            coords.append(x)
            coords.append(y)
        try:
            cursor.execute(stmt, coords)
            self.db.commit()
        except sqlite3.OperationalError as e:
            #no such table
            #print e
            pass
        if cursor.rowcount < 1:
            return False
        return True


class TileSetManager(object):
    def __init__(self, db, subgrid_size, file_ext, metadata, unique_tiles):
        self.db = db
        self.subgrid_size = subgrid_size
        self.file_ext = file_ext
        self.md = metadata
        self.unique_tiles = unique_tiles
        self._tile_sets = {}

    def store(self, tiles):
        return all(tile_set.set_tiles(list(tile_set_tiles))
            for tile_set, tile_set_tiles
                in groupby(tiles, partial(self._get_tile_set, create_db_entry=True)))

    def load(self, tiles):
        for tile_set, tile_set_tiles in groupby(tiles, self._get_tile_set):
            tile_set.get_tiles(list(tile_set_tiles))

        for tile in tiles:
            if tile.source is None:
                return False
        return True

    def remove(self, tiles):
        return all(tile_set.remove_tiles(list(tile_set_tiles))
            for tile_set, tile_set_tiles in groupby(tiles, self._get_tile_set))

    def is_cached(self, tile):
        tile_set = self._get_tile_set(tile)
        return tile_set.is_cached(tile)

    def _get_tile_set(self, tile, create_db_entry=False):
        x, y, level = tile.coord
        x0, y0 = self.subgrid_size
        x_pos = x//x0
        y_pos = y//y0
        key = (x0 * x_pos, y0 * y_pos)
        if key not in self._tile_sets:
            grid = [x0 * x_pos, y0 * y_pos, x0 * x_pos + x0, y0 * y_pos + y0]
            tile_set = TileSet(self.db, level, self.file_ext, grid, self.unique_tiles)
            tile_set.table_name = self.md.tile_set_table_name(tile_set)
            self._tile_sets[key] = tile_set
        else:
            tile_set = self._tile_sets[key]
        if create_db_entry and not tile_set._metadata_stored:
            self.md.store(tile_set)
            tile_set._metadata_stored = True
        return tile_set

class UniqueTiles(object):
    def __init__(self, db):
        self.db = db
        self.table_name = "unique_tiles"

    def _create_unique_tiles_table(self):
        cursor = self.db.cursor()
        stmt = """CREATE TABLE IF NOT EXISTS %s (
            id TEXT PRIMARY KEY,
            data BLOB
            ) """ % (self.table_name)
        cursor.execute(stmt)
        self.db.commit()

    def set_data(self, data, color):
        cursor = self.db.cursor()
        stmt = "INSERT INTO %s (id, data) VALUES (?, ?)" % (self.table_name)
        try:
            cursor.execute(stmt, (color, data))
        except sqlite3.IntegrityError as e:
            #data already present
            pass
        #TODO check entry point for commit()
        self.db.commit()

    def get_data(self, color):
        #_color = tile.unique_tile
        cursor = self.db.cursor()
        stmt = "SELECT data FROM %s WHERE id = ?" % (self.table_name)
        try:
            cursor.execute(stmt, (color,))
        except sqlite3.OperationalError as e:
            #tile not present
            pass
        row = cursor.fetchone()
        #returning raw data here - an ImageSource-Object will be created within the TileSet-Class
        return row['data']

class DatabaseStore(TileCacheBase):
    def __init__(self, path, layer_name, grid, sub_grid, file_ext):
        self.cache_path = path
        self.layer_name = layer_name
        self._subgrid_size = sub_grid
        self.grid = grid
        self.file_ext = file_ext
        self._tile_set_mgr = {}
        self._db = sqlite3.connect(self.cache_path, timeout=3)
        self._db.row_factory = sqlite3.Row
        self._metadata = Metadata(self._db, self.layer_name, self.grid, self.file_ext)
        self._metadata._create_metadata_table()
        self._unique_tiles = UniqueTiles(self._db)
        self._unique_tiles._create_unique_tiles_table()

    @property
    def db(self):
        return self._db

    def _get_tile_set_mgr(self, tile):
        x, y, level = tile.coord
        if level not in self._tile_set_mgr:
            size = self.grid.grid_sizes[level]
            size = min(size[0], self._subgrid_size[0]), min(size[1], self._subgrid_size[1])
            self._tile_set_mgr[level] = TileSetManager(self.db, size, self.file_ext, self._metadata, self._unique_tiles)
        return self._tile_set_mgr[level]

    def store_tile(self, tile):
        mgr = self._get_tile_set_mgr(tile)
        return mgr.store([tile])

    def store_tiles(self, tiles):
        first_tile = None
        for t in tiles:
            if t.coord is not None:
                first_tile = t
                break
        else:
            return True
        mgr = self._get_tile_set_mgr(first_tile)
        return mgr.store(tiles)

    def load_tile(self, tile, with_metadata=False):
        if tile.coord is None:
            return True

        mgr = self._get_tile_set_mgr(tile)
        return mgr.load([tile])

    #TODO implement metadata query
    def load_tiles(self, tiles, with_metadata=False):
        first_tile = None
        for t in tiles:
            if t.coord is not None:
                first_tile = t
                break
        else:
            return True
        mgr = self._get_tile_set_mgr(first_tile)
        return mgr.load([t for t in tiles if t.source is None and t.coord is not None])

    def remove_tile(self, tile):
        mgr = self._get_tile_set_mgr(tile)
        return mgr.remove([tile])

    def remove_tiles(self, tiles):
        first_tile = None
        for t in tiles:
            if t.coord is not None:
                first_tile = t
                break
        else:
            return True
        mgr = self._get_tile_set_mgr(first_tile)
        return mgr.remove(tiles)

    def is_cached(self, tile):
        if tile.coord is None:
            return True
        mgr = self._get_tile_set_mgr(tile)
        return mgr.is_cached(tile)
