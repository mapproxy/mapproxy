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

import pytest

try:
    import boto3
    from moto import mock_s3
except ImportError:
    boto3 = None
    mock_s3 = None

from mapproxy.cache.s3 import S3Cache
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase


@pytest.mark.skipif(not mock_s3 or not boto3,
                    reason="boto3 and moto required for S3 tests")
class TestS3Cache(TileCacheTestBase):
    always_loads_metadata = True
    uses_utc = True

    def setup(self):
        TileCacheTestBase.setup(self)

        self.mock = mock_s3()
        self.mock.start()

        self.bucket_name = "test"
        dir_name = 'mapproxy'

        boto3.client("s3").create_bucket(Bucket=self.bucket_name)

        self.cache = S3Cache(dir_name,
            file_ext='png',
            directory_layout='tms',
            bucket_name=self.bucket_name,
            profile_name=None,
            _concurrent_writer=1, # moto is not thread safe
        )

    def teardown(self):
        self.mock.stop()
        TileCacheTestBase.teardown(self)

    @pytest.mark.parametrize('layout,tile_coord,key', [
        ['mp', (12345, 67890,  2), 'mycache/webmercator/02/0001/2345/0006/7890.png'],
        ['mp', (12345, 67890, 12), 'mycache/webmercator/12/0001/2345/0006/7890.png'],

        ['tc', (12345, 67890,  2), 'mycache/webmercator/02/000/012/345/000/067/890.png'],
        ['tc', (12345, 67890, 12), 'mycache/webmercator/12/000/012/345/000/067/890.png'],

        ['tms', (12345, 67890,  2), 'mycache/webmercator/2/12345/67890.png'],
        ['tms', (12345, 67890, 12), 'mycache/webmercator/12/12345/67890.png'],

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
        cache = S3Cache('/mycache/webmercator', 'png', bucket_name=self.bucket_name, directory_layout=layout)
        cache.store_tile(self.create_tile(tile_coord))

        # raises, if key is missing
        boto3.client("s3").head_object(Bucket=self.bucket_name, Key=key)

