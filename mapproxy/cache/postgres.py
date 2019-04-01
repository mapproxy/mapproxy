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

import os
import sys
import psycopg2
import time


from mapproxy.cache.base import TileCacheBase


class CacheBackendError(Exception):
    pass


class TileCachePostgres(TileCacheBase):
    """
    Postgres implementation of a tile cache.
    """

    supports_timestamp = True

    def __init__(self, url, db_name, tile_grid, tile_id_template, db_initialised, req_session):
        """
        Initiate the database and the associated attributes for a Postgres database
        with postgis extension based cache.
        :param url: url for the database
        :param db_name: name of database
        :param tile_grid: tile set for cache
        :param tile_id_template: template for tile ids contianing x, y, z, and grid_name
        :param db_initialised: whether the database has been created yet
        :param req_session: the request session for the database
        """

    def init_db(self):
        """
        Create and connect to database
        :return: True in the event that it succeeds
        """
        return None

    def load_tile(self, tile, with_metadata=False):
        """
        Load a single tile from the Postgres database
        :param tile: The tile to be retrieved from the cache
        :param with_metadata: Boolean for whether metadata should be retrieved as well
        :return: True if load succeeds False if it does not
        """
        return None

    def load_tiles(self, tiles, with_metadata=False):
        """
        Load a single tile in a Postgres database
        :param tiles: The tiles that will be loaded from the Postgres database
        :param with_metadata: Boolean for whether metadata should be retrieved as well
        :return: True if the input succeeds and False if it fails
        """
        return None

    def store_tile(self, tile):
        """
        Store a single tile in a Postgres database
        :param tile: The tile that will be inserted into the Postgres database
        :return: True if the input succeeds and False if it fails
        """
        return None

    def store_tiles(self, tiles):
        """
        Likely to be removed but is the insertion of multiple tiles into the Postgres based cache
        :param tiles: tiles to be inserted into the Postgres database
        :return: True if all succeed else False
        """
        return None

    def remove_tile(self, tile):
        """
        Remove a single tile from a Postgres database
        :param tile: The tile to be removed from the cache
        :return: True if the remove is successful and False if it fails for any reason
        """
        return None

    # probably remove
    def remove_tiles(self, tiles):
        """
        Likely to be removed but is the removal of multiple tiles from the cache
        :param tiles: the tiles to be removed from the cache
        :return: True if successful and False otherwise
        """
        return None

    def remove_tiles_before(self, timestamp):
        """
        Remove all tiles cached before a given time
        :param timestamp: tiles before this timestamp are removed
        :return: True if tiles were successfully removed False otherwise
        """
        return None

    def is_cached(self, tile):
        """
        Checks to see if the tile is cached in the Postgres database
        :param tile: the tile to be searched for in the cache
        :return: True if the tile is cached.
        """
        return None

    def load_tile_metadata(self, tile):
        """
        retrieve the metadata associated with a given tile from a Postgres database
        Other implementations seem to just load teh tile??

        :param tile: The tile who's metadata needs to be retrieved
        :return: The requested metadata
        """
        return None


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



