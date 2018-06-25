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

import pytest

from mapproxy.test.image import is_jpeg
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "tileservice_origin.yaml"


@pytest.mark.usefixtures("fixture_cache_data")
class TestTileServicesOrigin(SysTest):

    ###
    # tile 0/0/1 is cached, check if we can access it with different URLs

    def test_get_cached_tile_tms(self, app):
        resp = app.get("/tms/1.0.0/wms_cache/0/0/1.jpeg")
        assert resp.content_type == "image/jpeg"
        assert is_jpeg(resp.body)

    def test_get_cached_tile_service_origin(self, app):
        resp = app.get("/tiles/wms_cache/1/0/0.jpeg")
        assert resp.content_type == "image/jpeg"
        assert is_jpeg(resp.body)

    def test_get_cached_tile_request_origin(self, app):
        resp = app.get("/tiles/wms_cache/1/0/1.jpeg?origin=sw")
        assert resp.content_type == "image/jpeg"
        assert is_jpeg(resp.body)
