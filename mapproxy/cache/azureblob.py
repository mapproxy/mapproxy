# This file is part of the MapProxy project.
# Copyright (C) 2022 Omniscale <http://omniscale.de>
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


import calendar
import hashlib
import threading
from io import BytesIO

from mapproxy.cache.tile import Tile
from mapproxy.cache import path
from mapproxy.cache.base import tile_buffer, TileCacheBase
from mapproxy.image import ImageSource
from mapproxy.util import async_

try:
    from azure.storage.blob import BlobServiceClient, ContentSettings
    from azure.core.exceptions import AzureError
except ImportError:
    BlobServiceClient = None  # type: ignore
    ContentSettings = None  # type: ignore
    AzureError = None  # type: ignore

import logging
log = logging.getLogger('mapproxy.cache.azureblob')


class AzureBlobConnectionError(Exception):
    pass


class AzureBlobCache(TileCacheBase):

    def __init__(self, base_path, file_ext, directory_layout='tms', container_name='mapproxy',
                 _concurrent_writer=4, _concurrent_reader=4, connection_string=None, coverage=None):
        super(AzureBlobCache, self).__init__(coverage)
        if BlobServiceClient is None:
            raise ImportError("Azure Blob Cache requires 'azure-storage-blob' package")

        self.lock_cache_id = 'azureblob-' + hashlib.md5(base_path.encode('utf-8')
                                                        + container_name.encode('utf-8')).hexdigest()

        self.connection_string = connection_string
        self.container_name = container_name
        self._container_client_cache = threading.local()

        self.base_path = base_path
        self.file_ext = file_ext
        self._concurrent_writer = _concurrent_writer
        self._concurrent_reader = _concurrent_reader
        self._tile_location, _ = path.location_funcs(layout=directory_layout)

    @property
    def container_client(self):
        if not getattr(self._container_client_cache, 'client', None):
            container_client = BlobServiceClient.from_connection_string(self.connection_string) \
                .get_container_client(self.container_name)
            self._container_client_cache.client = container_client
        return self._container_client_cache.client

    def tile_key(self, tile):
        return self._tile_location(tile, self.base_path, self.file_ext).lstrip('/')

    def load_tile_metadata(self, tile, dimensions=None):
        if tile.timestamp:
            return
        self.is_cached(tile, dimensions=dimensions)

    @staticmethod
    def _set_metadata(properties, tile):
        tile.timestamp = calendar.timegm(properties.last_modified.timetuple())
        tile.size = properties.size

    def is_cached(self, tile, dimensions=None):
        if tile.is_missing():
            key = self.tile_key(tile)
            blob = self.container_client.get_blob_client(key)
            if not blob.exists():
                return False
            else:
                self._set_metadata(blob.get_blob_properties(), tile)

        return True

    def load_tiles(self, tiles, with_metadata=True, dimensions=None):
        p = async_.Pool(min(self._concurrent_reader, len(tiles)))
        return all(p.map(self.load_tile, tiles))

    def load_tile(self, tile: Tile, with_metadata: bool = True, dimensions=None):
        if not tile.cacheable:
            return False

        if not tile.is_missing():
            return True

        key = self.tile_key(tile)
        log.debug('AzureBlob:load_tile, loading key: %s' % key)

        try:
            r = self.container_client.download_blob(key)
            self._set_metadata(r.properties, tile)
            tile.source = ImageSource(BytesIO(r.readall()))
        except AzureError as e:
            log.debug("AzureBlob:load_tile unable to load key: %s" % key, e)
            tile.source = None
            return False

        log.debug("AzureBlob:load_tile loaded key: %s" % key)
        return True

    def remove_tile(self, tile, dimensions=None):
        key = self.tile_key(tile)
        log.debug('remove_tile, key: %s' % key)
        self.container_client.delete_blob(key)

    def store_tiles(self, tiles, dimensions=None):
        p = async_.Pool(min(self._concurrent_writer, len(tiles)))
        p.map(self.store_tile, tiles)

    def store_tile(self, tile, dimensions=None):
        if tile.stored:
            return

        key = self.tile_key(tile)
        log.debug('AzureBlob: store_tile, key: %s' % key)

        container_client = self.container_client
        with tile_buffer(tile) as buf:
            content_settings = ContentSettings(content_type='image/' + self.file_ext)
            container_client.upload_blob(
                name=key,
                data=buf,
                overwrite=True,
                content_settings=content_settings)
