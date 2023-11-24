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

from __future__ import division

import pytest

from mapproxy.test.system import SysTest


class TestResponseHeaders(SysTest):
    """
    Check if the vary header is set for text / xml content like capabilities 
    """
    @pytest.fixture(scope='class')
    def config_file(self):
        return 'auth.yaml'

    def test_tms(self, app):
        resp = app.get('http://localhost/tms')
        assert resp.vary == ('X-Script-Name', 'X-Forwarded-Host', 'X-Forwarded-Proto')

    def test_wms(self, app):
        resp = app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&VERSION=1.1.0')
        assert resp.vary == ('X-Script-Name', 'X-Forwarded-Host', 'X-Forwarded-Proto')

    def test_wmts(self, app):
        resp = app.get('http://localhost/service?SERVICE=WMTS&REQUEST=GetCapabilities')
        assert resp.vary == ('X-Script-Name', 'X-Forwarded-Host', 'X-Forwarded-Proto')

    def test_restful_wmts(self, app):
        resp = app.get('http://localhost/wmts/1.0.0/WMTSCapabilities.xml')
        assert resp.vary == ('X-Script-Name', 'X-Forwarded-Host', 'X-Forwarded-Proto')

    def test_no_endpoint(self, app):
        resp = app.get('http://localhost/service?')
        assert resp.vary == ('X-Script-Name', 'X-Forwarded-Host', 'X-Forwarded-Proto')

    def test_image_response(self, app):
        resp = app.get('http://localhost/tms/1.0.0/layer1a/EPSG900913/0/0/0.png')
        assert resp.vary == None
