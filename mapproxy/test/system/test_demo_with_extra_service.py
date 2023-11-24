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

import pytest

from mapproxy.service.demo import extra_demo_server_handlers, extra_substitution_handlers, register_extra_demo_server_handler, register_extra_demo_substitution_handler
from mapproxy.test.system import SysTest

def demo_server_handler(demo_server, req):
    if 'my_service' in req.args:
        return 'my_return'
    return None


def demo_substitution_handler(demo_server, req, substitutions):
    substitutions['extra_services_html_beginning'] += '<h2>My extra service</h2>'

@pytest.fixture(scope="module")
def config_file():
    register_extra_demo_server_handler(demo_server_handler)
    register_extra_demo_substitution_handler(demo_substitution_handler)
    yield "demo.yaml"
    extra_demo_server_handlers.clear()
    extra_substitution_handlers.clear()


class TestDemoWithExtraService(SysTest):

    def test_basic(self, app):
        resp = app.get("/demo/", status=200)
        assert resp.content_type == "text/html"
        assert 'href="../service?REQUEST=GetCapabilities"' in resp
        assert 'href="../service?REQUEST=GetCapabilities&tiled=true"' in resp
        assert 'href="../demo/?wmts_layer=wms_cache&format=jpeg&srs=EPSG%3A900913"' in resp
        assert 'href="../demo/?tms_layer=wms_cache&format=jpeg&srs=EPSG%3A900913"' in resp
        assert '<h2>My extra service</h2>' in resp

    def test_my_service(self, app):
        resp = app.get("/demo/?my_service=bar", status=200)
        assert resp.content_type == "text/html"
        assert 'my_return' in resp
