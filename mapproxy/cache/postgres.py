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

import psycopg2
import datetime

from mapproxy.cache.base import TileCacheBase
from mapproxy.compat import BytesIO
from mapproxy.image import ImageSource


class CacheBackendError(Exception):
    pass


class TileCachePostgres(TileCacheBase):
    """
    Postgres implementation of a tile cache.
    """

    supports_timestamp = True

    def __init__(self, db_name, db_initialised, req_session):
        """
        Initiate the database and the associated attributes for a Postgres database
        with postgis extension based cache.
        :param db_name: name of database
        :param db_initialised: whether the database has been created yet
        :param req_session: the request session for the database
        """
        self.db_name = db_name
        self.db_initialised = db_initialised
        self.req_session = req_session
        connect = psycopg2.connect(database=db_name, user="postgres", password="postgres")  # need attributes
        self.conn = connect
        self.cursor = self.conn.cursor
        self.table_name = 'postgres'
        self.cursor.execute('''CREATE TABLE postgres (zoom_level INTEGER, tile_column INTEGER NOT NULL, 
                            tile_row INTEGER NOT NULL, tile_data BLOB NOT NULL, time_stamp TIMESTAMP )''')
        self.cursor.execute('''CREATE EXTENSION postgis''')
        self.cursor.execute('''CREATE INDEX zoom_index ON postgres''')

    def load_tile(self, tile, with_metadata=False):
        """
        Load a single tile from the Postgres database
        :param tile: The tile to be retrieved from the cache
        :param with_metadata: Boolean for whether metadata should be retrieved as well
        :return: True if load succeeds False if it does not
        """
        x, y, z = tile.coord
        try:
            self.cursor.execute('''SELECT tile_data FROM postgres WHERE zoom_level = ? 
                                AND tile_row = ? 
                                AND tile_column = ?
                                ''',
                                x, y, z)
            content = self.cursor.fetchone()
            if content:
                tile.source = ImageSource(BytesIO(content[0]))
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            return False
        if with_metadata:
            self.load_tile_metadata(tile)
        return True

    def store_tile(self, tile):
        """
        Store a single tile in a Postgres database
        :param tile: The tile that will be inserted into the Postgres database
        :return: True if the input succeeds and False if it fails
        """
        try:
            if not tile.stored:
                x, y, z = tile.coord
                stamp = datetime.datetime.today()
                self.cursor.execute('''
                                    INSERT INTO postgres (tile_data, tile_column, tile_row, zoom_level, time_stamp)
                                    VALUES (?, ?, ?, ?, ?)
                                    ''', tile.source, x, y, z, stamp)
                tile.timestap = stamp
            tile.stored = True
            self.cursor.commit()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            return False
        return True

    def remove_tile(self, tile):
        """
        Remove a single tile from a Postgres database
        :param tile: The tile to be removed from the cache
        :return: True if the remove is successful and False if it fails for any reason
        """
        try:
            self.cursor.execute('''DELETE * FROM postgres WHERE ''')
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            return False
        return True

    def remove_tiles_before(self, time_stamp):
        """
        Remove all tiles cached before a given time
        :param time_stamp: tiles before this timestamp are removed
        :return: True if tiles were successfully removed False otherwise
        """
        try:
            self.cursor.execute('''DELETE * FROM postgres WHERE timestamp < ?''', time_stamp)
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            return False
        return True

    def is_cached(self, tile):
        """
        Checks to see if the tile is cached in the Postgres database
        :param tile: the tile to be searched for in the cache
        :return: True if the tile is cached.
        """
        try:
            x, y, z = tile.coord
            self.cursor.execute(
                '''SELECT time_stamp FROM postgres WHERE tile_row = ? AND tile_column = ? AND zoom_level = ?''', x, y, z
            )
            content = self.cursor.fetchone()
            if not content:
                return False
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            return False
        return True

    def load_tile_metadata(self, tile):
        """
        Retrieve the metadata associated with a given tile from a Postgres database
        and fills in attributes in the tile

        :param tile: The tile who's metadata needs to be retrieved
        :return: True if successful False otherwise
        """
        try:
            self.cursor.execute('''SELECT time_stamp FROM ? WHERE ? = ?''')
            content = self.cursor.fetchone()
            if content:
                tile.timestamp = content[0]
                return True
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            return False
        return False


class PostgresMDTemplate(object):
    def __init__(self, attributes):
        """
        Initiation of a Postgres metadata template
        :param attributes: attributes included in metadata
        """

    def doc(self):
        """
        Creates a JSON document for the metadata of a tile
        :return: JSON document for tile
        """
        return None
