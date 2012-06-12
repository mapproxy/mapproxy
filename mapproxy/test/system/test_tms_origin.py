# This file is part of the MapProxy project.
# Copyright (C) 2010-2012 Omniscale <http://omniscale.de>
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
from mapproxy.test.image import is_jpeg
from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config
from nose.tools import eq_

test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    module_setup(test_config, 'tileservice_origin.yaml', with_cache_data=True)

def teardown_module():
    module_teardown(test_config)

class TestTileServicesOrigin(SystemTest):
    config = test_config

    ###
    # tile 0/0/1 is cached, check if we can access it with different URLs

    def test_get_cached_tile_tms(self):
        resp = self.app.get('/tms/1.0.0/wms_cache/0/0/1.jpeg')
        eq_(resp.content_type, 'image/jpeg')
        assert is_jpeg(resp.body)
 
    def test_get_cached_tile_service_origin(self):
        resp = self.app.get('/tiles/wms_cache/1/0/0.jpeg')
        eq_(resp.content_type, 'image/jpeg')
        assert is_jpeg(resp.body)

    def test_get_cached_tile_request_origin(self):
        resp = self.app.get('/tiles/wms_cache/1/0/1.jpeg?origin=sw')
        eq_(resp.content_type, 'image/jpeg')
        assert is_jpeg(resp.body)



