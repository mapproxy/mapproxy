# This file is part of the MapProxy project.
# Copyright (C) 2012 Omniscale <http://omniscale.de>
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

from mapproxy.test.image import tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "tilesource_minmax_res.yaml"


class TestTileSourceMinMaxRes(SysTest):

    def test_get_tile_res_a(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {"path": r"/tiles_a/06/000/000/000/000/000/001.png"},
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                resp = app.get("/tiles/tms_cache/6/0/1.png")
                assert resp.content_type == "image/png"
        assert cache_dir.join(
            "tms_cache_EPSG900913/06/000/000/000/000/000/001.png"
        ).check()

    def test_get_tile_res_b(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {"path": r"/tiles_b/07/000/000/000/000/000/001.png"},
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                resp = app.get("/tiles/tms_cache/7/0/1.png")
                assert resp.content_type == "image/png"
        assert cache_dir.join(
            "tms_cache_EPSG900913/07/000/000/000/000/000/001.png"
        ).check()
