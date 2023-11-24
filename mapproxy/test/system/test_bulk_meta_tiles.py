# This file is part of the MapProxy project.
# Copyright (C) 2016 Omniscale <http://omniscale.de>
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

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.test.image import tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "cache_bulk_meta_tiles.yaml"


class TestCacheSource(SysTest):

    def test_tms_capabilities(self, app):
        resp = app.get("/tms/1.0.0/")
        xml = resp.lxml

        assert xml.xpath("count(//TileMap)") == 1

    def test_get_map(self, app):
        # request single tile via WMS and check that
        map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                width="100",
                height="100",
                bbox="0,0,100000,100000",
                layers="bulk",
                srs="EPSG:3857",
                format="image/png",
                styles="",
                request="GetMap",
            ),
        )

        expected_reqs = []
        with tmp_image((256, 256), format="jpeg") as img:
            img = img.read()
            # bulk_cache has meta_size of [2, 2]
            for tile in [(128, 128, 8), (128, 129, 8), (129, 128, 8), (129, 129, 8)]:
                expected_reqs.append(
                    (
                        {
                            "path": r"/tiles/%02d/000/000/%03d/000/000/%03d.png"
                            % (tile[2], tile[0], tile[1])
                        },
                        {"body": img, "headers": {"content-type": "image/png"}},
                    )
                )
            with mock_httpd(("localhost", 42423), expected_reqs, unordered=True):
                resp = app.get(map_req)
                assert resp.content_type == "image/png"

    def test_get_tile(self, app, cache_dir):
        expected_reqs = []
        with tmp_image((256, 256), format="jpeg") as img:
            # bulk_cache has meta_size of [2, 2]
            for tile in [(4, 3, 5), (5, 3, 5), (4, 2, 5), (5, 2, 5)]:
                expected_reqs.append(
                    (
                        {
                            "path": r"/tiles/%02d/000/000/%03d/000/000/%03d.png"
                            % (tile[2], tile[0], tile[1])
                        },
                        {"body": img.read(), "headers": {"content-type": "image/png"}},
                    )
                )
            with mock_httpd(("localhost", 42423), expected_reqs, unordered=True):
                resp = app.get("/tiles/1.0.0/bulk/EPSG900913/5/4/3.png")
                assert resp.content_type == "image/png"

        assert cache_dir.join(
            "bulk_cache_EPSG900913/05/000/000/004/000/000/002.png"
        ).check()
        assert cache_dir.join(
            "bulk_cache_EPSG900913/05/000/000/004/000/000/003.png"
        ).check()
        assert cache_dir.join(
            "bulk_cache_EPSG900913/05/000/000/005/000/000/002.png"
        ).check()
        assert cache_dir.join(
            "bulk_cache_EPSG900913/05/000/000/005/000/000/003.png"
        ).check()

        # access tile cached by previous bulk_meta_tile request
        resp = app.get("/tiles/1.0.0/bulk/EPSG900913/5/5/3.png")
        assert resp.content_type == "image/png"
