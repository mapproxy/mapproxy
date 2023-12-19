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

import os

import pytest

try:
    from mapproxy.cache.azureblob import AzureBlobCache
except ImportError:
    AzureBlobCache = None

from mapproxy.test.unit.test_cache_tile import TileCacheTestBase


@pytest.mark.skipif(not AzureBlobCache or not os.environ.get('MAPPROXY_TEST_AZURE_BLOB'),
                    reason="azure-storage-blob package and MAPPROXY_TEST_AZURE_BLOB env required")
class TestAzureBlobCache(TileCacheTestBase):
    always_loads_metadata = True
    uses_utc = True

    def setup_method(self):
        TileCacheTestBase.setup_method(self)

        self.container = 'mapproxy-azure-unit-test'
        self.base_path = '/mycache/webmercator'
        self.file_ext = 'png'

        # Use default storage account of Azurite emulator
        self.host = os.environ['MAPPROXY_TEST_AZURE_BLOB']
        self.connection_string = 'DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=' \
                                 'Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr' \
                                 '/KBHBeksoGMGw==;BlobEndpoint=' + self.host + '/devstoreaccount1;'

        self.cache = AzureBlobCache(
            base_path=self.base_path,
            file_ext=self.file_ext,
            container_name=self.container,
            connection_string=self.connection_string,
        )

        self.container_client = self.cache.container_client
        self.container_client.create_container()

    def teardown_method(self):
        TileCacheTestBase.teardown_method(self)
        self.container_client.delete_container()
    
    def test_default_coverage(self):
        assert self.cache.coverage is None

    @pytest.mark.parametrize('layout,tile_coord,key', [
        ['mp', (12345, 67890, 2), 'mycache/webmercator/02/0001/2345/0006/7890.png'],
        ['mp', (12345, 67890, 12), 'mycache/webmercator/12/0001/2345/0006/7890.png'],

        ['tc', (12345, 67890, 2), 'mycache/webmercator/02/000/012/345/000/067/890.png'],
        ['tc', (12345, 67890, 12), 'mycache/webmercator/12/000/012/345/000/067/890.png'],

        ['tms', (12345, 67890, 2), 'mycache/webmercator/2/12345/67890.png'],
        ['tms', (12345, 67890, 12), 'mycache/webmercator/12/12345/67890.png'],

        ['reverse_tms', (12345, 67890, 2), 'mycache/webmercator/67890/12345/2.png'],
        ['reverse_tms', (12345, 67890, 12), 'mycache/webmercator/67890/12345/12.png'],

        ['quadkey', (0, 0, 0), 'mycache/webmercator/.png'],
        ['quadkey', (0, 0, 1), 'mycache/webmercator/0.png'],
        ['quadkey', (1, 1, 1), 'mycache/webmercator/3.png'],
        ['quadkey', (12345, 67890, 12), 'mycache/webmercator/200200331021.png'],

        ['arcgis', (1, 2, 3), 'mycache/webmercator/L03/R00000002/C00000001.png'],
        ['arcgis', (9, 2, 3), 'mycache/webmercator/L03/R00000002/C00000009.png'],
        ['arcgis', (10, 2, 3), 'mycache/webmercator/L03/R00000002/C0000000a.png'],
        ['arcgis', (12345, 67890, 12), 'mycache/webmercator/L12/R00010932/C00003039.png'],
    ])
    def test_tile_key(self, layout, tile_coord, key):
        cache = AzureBlobCache(
            base_path=self.base_path,
            file_ext=self.file_ext,
            container_name=self.container,
            connection_string=self.connection_string,
            directory_layout=layout
        )
        cache.store_tile(self.create_tile(tile_coord))

        assert self.container_client.get_blob_client(key).exists()
