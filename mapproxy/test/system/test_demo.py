# This file is part of the MapProxy project.
# Copyright (C) 2022 Even Rouault
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

import re
import pytest

from mapproxy.test.http import mock_httpd
from mapproxy.test.system import SysTest
from webtest import AppError


@pytest.fixture(scope="module")
def config_file():
    return "demo.yaml"


class TestDemo(SysTest):

    def test_basic(self, app):
        resp = app.get("/demo/", status=200)
        assert resp.content_type == "text/html"
        assert 'href="../service?REQUEST=GetCapabilities&SERVICE=WMS"' in resp
        assert 'href="../service?REQUEST=GetCapabilities&SERVICE=WMS&tiled=true"' in resp
        assert 'href="../demo/?wmts_layer=wms_cache&format=jpeg&srs=EPSG%3A900913"' in resp
        assert 'href="../demo/?tms_layer=wms_cache&format=jpeg&srs=EPSG%3A900913"' in resp

    def test_previewmap(self, app):
        resp = app.get("/demo/?srs=EPSG%3A3857&format=image%2Fpng&wms_layer=wms_cache", status=200)
        assert resp.content_type == "text/html"
        assert '<h2>Layer Preview - wms_cache</h2>' in resp

    def test_layers_sorted_by_name(self, app):
        resp = app.get("/demo/", status=200)

        patternTable = re.compile(r'<table class="code">.*?</table>', re.DOTALL)
        patternWMS = r'<td\s+rowspan="2">([\w\d-]+)</td>'
        patternWMTS_TBS = r'<td\s+rowspan="1">([\w\d-]+)</td>'
        tables = patternTable.findall(resp.text)

        layersWMS = re.findall(patternWMS, resp.text, re.IGNORECASE)
        layersWMTS = re.findall(patternWMTS_TBS, tables[1], re.IGNORECASE)
        layersTBS = re.findall(patternWMTS_TBS, tables[2], re.IGNORECASE)

        assert layersWMS == sorted(layersWMS)
        assert layersWMTS == sorted(layersWMTS)
        assert layersTBS == sorted(layersTBS)

    def test_external(self, app):
        expected_req = (
            {
                "path": r"/path/service?REQUEST=GetCapabilities&SERVICE=WMS"
            },
            {"body": b"test-string", "headers": {"content-type": "text/xml"}}
        )
        with mock_httpd(
                ("localhost", 42423), [expected_req]
        ):
            resp = app.get('/demo/?wms_capabilities&type=external', extra_environ={
                'HTTP_X_FORWARDED_HOST': 'localhost:42423/path'
            })
            content = resp.text
            assert 'test-string' in content
            assert 'http://localhost:42423/path/service?REQUEST=GetCapabilities&SERVICE=WMS' in content

    def test_external_xss_injection(self, app):
        expected_req = (
            {
                "path": r"/path/&gt;&lt;script&gt;alert(XSS)&lt;/script&gt;/service?REQUEST=GetCapabilities&SERVICE=WMS"
            },
            {"body": b"test-string", "headers": {"content-type": "text/xml"}}
        )

        with mock_httpd(
                ("localhost", 42423), [expected_req]
        ):
            resp = app.get('/demo/?wms_capabilities&type=external', extra_environ={
                'HTTP_X_FORWARDED_HOST': 'localhost:42423/path/"><script>alert(\'XSS\')</script>'
            })
        content = resp.text
        assert 'test-string' in content
        assert '"><script>alert(\'XSS\')' not in content
        assert '&gt;&lt;script&gt;alert(XSS)&lt;/script&gt;' in content

    def test_external_file_protocol(self, app):
        try:
            app.get('/demo/?wms_capabilities&type=external', extra_environ={
                'HTTP_X_FORWARDED_PROTO': 'file'
            })
        except AppError as e:
            assert '400 Bad Request' in e.args[0]

    def test_tms_layer_xss(self, app):
        expected_req = (
            {
                "path": r"/tms/1.0.0/osm&gt;&lt;script&gt;alert(XSS)&lt;/script&gt;/1.0.0"
            },
            {"body": b"test-string", "headers": {"content-type": "text/xml"}}
        )

        with mock_httpd(
                ("localhost", 42423), [expected_req]
        ):
            resp = app.get(
                '/demo/?tms_capabilities&layer=osm"><script>alert(\'XSS\')</script>&type=external&srs=1.0.0',
                extra_environ={
                    'HTTP_X_FORWARDED_HOST': 'localhost:42423'
                }
            )
        content = resp.text
        assert '"><script>alert(\'XSS\')' not in content
        assert '&gt;&lt;script&gt;alert(XSS)&lt;/script&gt;' in content
