# This file is part of the MapProxy project.
# Copyright (C) 2014 Omniscale <http://omniscale.de>
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

from __future__ import with_statement, division

from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config
from mapproxy.test.system.test_wms import is_110_capa, is_111_capa


test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    module_setup(test_config, 'wms_versions.yaml')

def teardown_module():
    module_teardown(test_config)

class TestWMSVersionsTest(SystemTest):
    config = test_config

    def test_supported_version_110(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&VERSION=1.1.0')
        assert is_110_capa(resp.lxml)

    def test_unknown_version_113(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&VERSION=1.1.3')
        assert is_111_capa(resp.lxml)

    def test_unknown_version_090(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&WMTVER=0.9.0')
        assert is_110_capa(resp.lxml)

    def test_unsupported_version_130(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&VERSION=1.3.0')
        assert is_111_capa(resp.lxml)

    def test_unknown_version_200(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&VERSION=2.0.0')
        assert is_111_capa(resp.lxml)
