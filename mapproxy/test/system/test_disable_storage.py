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

from mapproxy.test.image import is_png, tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config
from nose.tools import eq_

test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    module_setup(test_config, 'disable_storage.yaml', with_cache_data=False)

def teardown_module():
    module_teardown(test_config)

class TestDisableStorage(SystemTest):
    config = test_config
    
    def test_get_tile_without_caching(self):
        with tmp_image((256, 256), format='png') as img:
            expected_req = ({'path': r'/tile.png'},
                            {'body': img.read(), 'headers': {'content-type': 'image/png'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                resp = self.app.get('/tms/1.0.0/tiles/0/0/0.png')
                eq_(resp.content_type, 'image/png')
                is_png(resp.body)

        assert not os.path.exists(test_config['cache_dir'])
        
        with tmp_image((256, 256), format='png') as img:
            expected_req = ({'path': r'/tile.png'},
                            {'body': img.read(), 'headers': {'content-type': 'image/png'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                resp = self.app.get('/tms/1.0.0/tiles/0/0/0.png')
                eq_(resp.content_type, 'image/png')
                is_png(resp.body)
        