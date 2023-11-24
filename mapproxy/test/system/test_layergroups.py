# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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

import pytest

from mapproxy.test.system import SysTest
from mapproxy.test.system.test_wms import (
    is_111_capa,
    is_110_capa,
    is_100_capa,
    is_130_capa,
    ns130,
)


TESTSERVER_ADDRESS = "localhost", 42423


class TestWMSWithRoot(SysTest):

    @pytest.fixture(scope="class")
    def config_file(self):
        return "layergroups_root.yaml"

    def _check_layernames(self, xml):
        assert xml.xpath("//Capability/Layer/Title/text()") == ["Root Layer"]
        assert xml.xpath("//Capability/Layer/Name/text()") == ["root"]
        assert xml.xpath("//Capability/Layer/Layer/Name/text()") == ["layer1", "layer2"]
        assert xml.xpath("//Capability/Layer/Layer[1]/Layer/Name/text()") == [
            "layer1a",
            "layer1b",
        ]

    def _check_layernames_with_namespace(self, xml, namespaces=None):
        assert xml.xpath(
            "//wms:Capability/wms:Layer/wms:Title/text()", namespaces=namespaces
        ) == ["Root Layer"]
        assert xml.xpath(
            "//wms:Capability/wms:Layer/wms:Name/text()", namespaces=namespaces
        ) == ["root"]
        assert xml.xpath(
            "//wms:Capability/wms:Layer/wms:Layer/wms:Name/text()",
            namespaces=namespaces,
        ) == ["layer1", "layer2"]
        assert xml.xpath(
            "//wms:Capability/wms:Layer/wms:Layer[1]/wms:Layer/wms:Name/text()",
            namespaces=namespaces,
        ) == ["layer1a", "layer1b"]

    def test_100_capa(self, app):
        resp = app.get("/service?request=GetCapabilities&service=WMS&wmtver=1.0.0")
        xml = resp.lxml
        assert is_100_capa(xml)
        self._check_layernames(xml)

    def test_110_capa(self, app):
        resp = app.get("/service?request=GetCapabilities&service=WMS&version=1.1.0")
        xml = resp.lxml
        assert is_110_capa(xml)
        self._check_layernames(xml)

    def test_111_capa(self, app):
        resp = app.get("/service?request=GetCapabilities&service=WMS&version=1.1.1")
        xml = resp.lxml
        assert is_111_capa(xml)
        self._check_layernames(xml)

    def test_130_capa(self, app):
        resp = app.get("/service?request=GetCapabilities&service=WMS&version=1.3.0")
        xml = resp.lxml
        assert is_130_capa(xml)
        self._check_layernames_with_namespace(xml, ns130)


class TestWMSWithoutRoot(SysTest):

    @pytest.fixture(scope="class")
    def config_file(self):
        return "layergroups.yaml"

    def _check_layernames(self, xml):
        assert xml.xpath("//Capability/Layer/Title/text()") == ["My WMS"]
        assert xml.xpath("//Capability/Layer/Name/text()") == []
        assert xml.xpath("//Capability/Layer/Layer/Name/text()") == ["layer1", "layer2"]
        assert xml.xpath("//Capability/Layer/Layer[1]/Layer/Name/text()") == [
            "layer1a",
            "layer1b",
        ]
        assert xml.xpath("//Capability/Layer/Layer[2]/Layer/Name/text()") == [
            "layer2a",
            "layer2b",
        ]
        assert xml.xpath("//Capability/Layer/Layer[2]/Layer/Layer[1]/Name/text()") == [
            "layer2b1"
        ]

    def _check_layernames_with_namespace(self, xml, namespaces=None):
        assert xml.xpath(
            "//wms:Capability/wms:Layer/wms:Title/text()", namespaces=namespaces
        ) == ["My WMS"]
        assert (
            xml.xpath(
                "//wms:Capability/wms:Layer/wms:Name/text()", namespaces=namespaces
            )
            == []
        )
        assert xml.xpath(
            "//wms:Capability/wms:Layer/wms:Layer/wms:Name/text()",
            namespaces=namespaces,
        ), ["layer1" == "layer2"]
        assert xml.xpath(
            "//wms:Capability/wms:Layer/wms:Layer[1]/wms:Layer/wms:Name/text()",
            namespaces=namespaces,
        ) == ["layer1a", "layer1b"]
        assert xml.xpath(
            "//wms:Capability/wms:Layer/wms:Layer[2]/wms:Layer/wms:Name/text()",
            namespaces=namespaces,
        ) == ["layer2a", "layer2b"]
        assert xml.xpath(
            "//wms:Capability/wms:Layer/wms:Layer[2]/wms:Layer/wms:Layer[1]/wms:Name/text()",
            namespaces=namespaces,
        ) == ["layer2b1"]

    def test_100_capa(self, app):
        resp = app.get("/service?request=GetCapabilities&service=WMS&wmtver=1.0.0")
        xml = resp.lxml
        assert is_100_capa(xml)
        self._check_layernames(xml)

    def test_110_capa(self, app):
        resp = app.get("/service?request=GetCapabilities&service=WMS&version=1.1.0")
        xml = resp.lxml
        assert is_110_capa(xml)
        self._check_layernames(xml)

    def test_111_capa(self, app):
        resp = app.get("/service?request=GetCapabilities&service=WMS&version=1.1.1")
        xml = resp.lxml
        assert is_111_capa(xml)
        self._check_layernames(xml)

    def test_130_capa(self, app):
        resp = app.get("/service?request=GetCapabilities&service=WMS&version=1.3.0")
        xml = resp.lxml
        assert is_130_capa(xml)
        self._check_layernames_with_namespace(xml, ns130)
