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

from __future__ import division

from mapproxy.test.system import SysTest
from mapproxy.test.system.test_wms import is_110_capa, is_111_capa, is_130_capa

import pytest


class TestLimitedWMSVersionsTest(SysTest):

    @pytest.fixture(scope="class")
    def config_file(self):
        return "wms_versions.yaml"

    def test_default_version_130(self, app):
        resp = app.get("http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities")
        assert is_111_capa(resp.lxml)

    def test_supported_version_110(self, app):
        resp = app.get(
            "http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities"
            "&VERSION=1.1.0"
        )
        assert is_110_capa(resp.lxml)

    def test_unknown_version_113(self, app):
        resp = app.get(
            "http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities"
            "&VERSION=1.1.3"
        )
        assert is_111_capa(resp.lxml)

    def test_unknown_version_090(self, app):
        resp = app.get(
            "http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities"
            "&WMTVER=0.9.0"
        )
        assert is_110_capa(resp.lxml)

    def test_unsupported_version_130(self, app):
        resp = app.get(
            "http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities"
            "&VERSION=1.3.0"
        )
        assert is_111_capa(resp.lxml)

    def test_unknown_version_200(self, app):
        resp = app.get(
            "http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities"
            "&VERSION=2.0.0"
        )
        assert is_111_capa(resp.lxml)


class TestWMSVersionsTest(SysTest):

    @pytest.fixture(scope="class")
    def config_file(self):
        return "layer.yaml"

    def test_default_version_130(self, app):
        resp = app.get("http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities")
        assert is_130_capa(resp.lxml)

    def test_unknown_version_200(self, app):
        resp = app.get(
            "http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities"
            "&VERSION=2.0.0"
        )
        assert is_130_capa(resp.lxml)
