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

try:
    import boto
    from moto import mock_s3
except ImportError:
    boto = None
    mock_s3 = None

from nose.plugins.skip import SkipTest

from mapproxy.cache.s3 import S3Cache
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase


class TestS3Cache(TileCacheTestBase):
    always_loads_metadata = True

    def setup(self):
        if not mock_s3 or not boto:
            raise SkipTest("boto and moto required for S3 tests")

        TileCacheTestBase.setup(self)

        self.mock = mock_s3()
        self.mock.start()

        bucket_name = "test"
        dir_name = 'mapproxy'

        boto.connect_s3().create_bucket(bucket_name)

        self.cache = S3Cache(dir_name,
            file_ext='png',
            directory_layout='tms',
            lock_timeout=10,
            bucket_name=bucket_name,
            profile_name=None,
        )

    def teardown(self):
        self.mock.stop()
        TileCacheTestBase.teardown(self)
