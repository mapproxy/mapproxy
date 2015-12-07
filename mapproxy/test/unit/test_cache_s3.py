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

from __future__ import with_statement

import os
import random

from nose.plugins.skip import SkipTest

from mapproxy.cache.s3 import S3Cache
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase


class TestS3Cache(TileCacheTestBase):
    always_loads_metadata = True

    def setup(self):
        if not os.environ.get('MAPPROXY_TEST_S3'):
            raise SkipTest()

        bucket_name = os.environ['MAPPROXY_TEST_S3']
        dir_name = 'mapproxy/test_%d' % random.randint(0, 100000)

        TileCacheTestBase.setup(self)

        self.cache = S3Cache(dir_name, file_ext='png', directory_layout='tms',
                             lock_timeout=10, bucket_name=bucket_name, profile_name=None)

    def teardown(self):
        TileCacheTestBase.teardown(self)
