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

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.test.image import tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "cache_source.yaml"


class TestCacheSource(SysTest):

    def test_tms_capabilities(self, app):
        resp = app.get("/tms/1.0.0/")
        assert "transformed tile source" in resp
        xml = resp.lxml

        assert xml.xpath("count(//TileMap)") == 3

    def test_get_map_through_cache(self, app):
        map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                width="100",
                height="100",
                bbox="432890.564641,5872387.45834,466833.867667,5928359.08814",
                layers="tms_transf",
                srs="EPSG:25832",
                format="image/png",
                styles="",
                request="GetMap",
            ),
        )

        expected_reqs = []
        with tmp_image((256, 256), format="jpeg") as img:
            img = img.read()
            # tms_cache_out has meta_size of [2, 2] but we need larger extent for transformation
            for tile in [
                (132, 172, 8),
                (133, 172, 8),
                (134, 172, 8),
                (132, 173, 8),
                (133, 173, 8),
                (134, 173, 8),
                (132, 174, 8),
                (133, 174, 8),
                (134, 174, 8),
            ]:
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

    def test_get_tile_through_cache(self, app, cache_dir):
        # request tile from tms_transf,
        # should get tile from tms_source via tms_cache_in/out
        expected_reqs = []
        with tmp_image((256, 256), format="jpeg") as img:
            for tile in [(8, 11, 4), (8, 10, 4)]:
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
                resp = app.get("/tms/1.0.0/tms_transf/EPSG25832/0/0/0.png")
                assert resp.content_type == "image/png"

        assert cache_dir.join(
            "tms_cache_out_EPSG25832/00/000/000/000/000/000/000.png"
        ).check()

    def test_get_tile_from_sub_grid(self, app, cache_dir):
        # create tile in old cache
        tile_filename = cache_dir.join(
            "old_cache_EPSG3857/01/000/000/001/000/000/000.png"
        )
        # use text to check that mapproxy does not access the tile as image
        tile_filename.write_binary(b"foo", ensure=True)

        # access new cache, should get existing tile from old cache
        resp = app.get("/tiles/new_cache_EPSG3857/0/0/0.png")
        assert resp.content_type == "image/png"
        assert resp.body == b"foo"

        assert cache_dir.join(
            "old_cache_EPSG3857/01/000/000/001/000/000/000.png"
        ).check()
        assert cache_dir.join(
            "new_cache_EPSG3857/00/000/000/000/000/000/000.png"
        ).check()

    def test_get_tile_combined_cache(self, app):
        # request from cache with two cache sources where only one
        # is compatible (supports tiled_only)
        expected_reqs = []
        with tmp_image((256, 256), format="jpeg") as img:
            img = img.read()
            for tile in [
                r"/tiles/04/000/000/008/000/000/011.png",
                r"/tiles/04/000/000/008/000/000/010.png",
                r"/tiles/utm/00/000/000/000/000/000/000.png",
            ]:
                expected_reqs.append(
                    (
                        {"path": tile},
                        {"body": img, "headers": {"content-type": "image/png"}},
                    )
                )

            with mock_httpd(("localhost", 42423), expected_reqs, unordered=True):
                resp = app.get("/tms/1.0.0/combined/EPSG25832/0/0/0.png")
                assert resp.content_type == "image/png"
