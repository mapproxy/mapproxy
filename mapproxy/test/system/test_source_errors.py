# This file is part of the MapProxy project.
# Copyright (C) 2010-2014 Omniscale <http://omniscale.de>
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

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.test.image import (
    is_transparent,
    create_tmp_image,
    bgcolor_ratio,
    img_from_buf,
    assert_colors_equal,
)
from mapproxy.test.http import (
    assert_no_cache,
    mock_httpd
)
from mapproxy.test.system import SysTest
from mapproxy.test.system.test_wms import is_111_exception


transp = create_tmp_image((200, 200), mode="RGBA", color=(0, 0, 0, 0))


class TestWMS(SysTest):

    @pytest.fixture(scope="class")
    def config_file(self):
        return "source_errors.yaml"

    def setup(self):
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="9,50,10,51",
                width="200",
                height="200",
                layers="online",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
                transparent=True,
            ),
        )

    def test_online(self, app):
        common_params = (
            r"?SERVICE=WMS&FORMAT=image%2Fpng"
            "&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles="
            "&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0"
            "&WIDTH=200&transparent=True"
        )

        expected_req = [
            (
                {"path": "/service_a" + common_params + "&layers=a_one"},
                {"body": transp, "headers": {"content-type": "image/png"}},
            )
        ]

        with mock_httpd(("localhost", 42423), expected_req):
            self.common_map_req.params.layers = "online"
            resp = app.get(self.common_map_req)
            assert "Cache-Control" not in resp.headers
            assert resp.content_type == "image/png"
            assert is_transparent(resp.body)

    def test_mixed_layer_source(self, app):
        common_params = (
            r"?SERVICE=WMS&FORMAT=image%2Fpng"
            "&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles="
            "&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0"
            "&WIDTH=200&transparent=True"
        )

        expected_req = [
            (
                {"path": "/service_a" + common_params + "&layers=a_one"},
                {"body": transp, "headers": {"content-type": "image/png"}},
            )
        ]

        with mock_httpd(("localhost", 42423), expected_req):
            self.common_map_req.params.layers = "mixed"
            resp = app.get(self.common_map_req)
            assert_no_cache(resp)
            assert resp.content_type == "image/png"
            assert 0.99 > bgcolor_ratio(resp.body) > 0.95

    def test_mixed_sources(self, app):
        common_params = (
            r"?SERVICE=WMS&FORMAT=image%2Fpng"
            "&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles="
            "&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0"
            "&WIDTH=200&transparent=True"
        )

        expected_req = [
            (
                {"path": "/service_a" + common_params + "&layers=a_one"},
                {"body": transp, "headers": {"content-type": "image/png"}},
            )
        ]

        with mock_httpd(("localhost", 42423), expected_req):
            self.common_map_req.params.layers = "online,all_offline"
            resp = app.get(self.common_map_req)
            assert_no_cache(resp)
            assert resp.content_type == "image/png"
            assert 0.99 > bgcolor_ratio(resp.body) > 0.95
            # open('/tmp/foo.png', 'wb').write(resp.body)

    def test_all_offline(self, app):
        self.common_map_req.params.layers = "all_offline"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        is_111_exception(resp.lxml, re_msg="no response from url")


class TestWMSRaise(SysTest):

    @pytest.fixture(scope="class")
    def config_file(self):
        return "source_errors_raise.yaml"

    def setup(self):
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="9,50,10,51",
                width="200",
                height="200",
                layers="online",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
                transparent=True,
            ),
        )

    def test_mixed_layer_source(self, app):
        common_params = (
            r"?SERVICE=WMS&FORMAT=image%2Fpng"
            "&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles="
            "&VERSION=1.1.1&BBOX=9.0,50.0,10.0,51.0"
            "&WIDTH=200&transparent=True"
        )

        expected_req = [
            (
                {"path": "/service_a" + common_params + "&layers=a_one"},
                {"body": transp, "headers": {"content-type": "image/png"}},
            )
        ]

        with mock_httpd(("localhost", 42423), expected_req):
            self.common_map_req.params.layers = "mixed"
            resp = app.get(self.common_map_req)
            is_111_exception(resp.lxml, re_msg="no response from url")

    def test_all_offline(self, app):
        self.common_map_req.params.layers = "all_offline"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        is_111_exception(resp.lxml, re_msg="no response from url")


class TestTileErrors(SysTest):

    @pytest.fixture(scope="class")
    def config_file(self):
        return "source_errors.yaml"

    def setup(self):
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="0,-90,180,90",
                width="250",
                height="250",
                layers="tilesource",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
                transparent=True,
            ),
        )

        self.common_tile_req = "/tiles/tilesource/EPSG4326/1/1/0.png"

    def test_wms_uncached_response(self, app, cache_dir):
        expected_req = [
            (
                {"path": "/foo/1/1/0.png"},
                {
                    "body": b"not found",
                    "status": 404,
                    "headers": {"content-type": "text/plain"},
                },
            )
        ]

        with mock_httpd(("localhost", 42423), expected_req):
            resp = app.get(self.common_map_req)
            assert resp.content_type == "image/png"
            assert_no_cache(resp)
            img = img_from_buf(resp.body)
            assert img.getcolors() == [(250 * 250, (255, 0, 128))]
        assert not cache_dir.join(
            "tilesource_cache_EPSG4326/01/000/000/001/000/000/000.png"
        ).check()

    def test_wms_cached_response(self, app, cache_dir):
        expected_req = [
            (
                {"path": "/foo/1/1/0.png"},
                {
                    "body": b"no content",
                    "status": 204,
                    "headers": {"content-type": "text/plain"},
                },
            )
        ]

        with mock_httpd(("localhost", 42423), expected_req):
            resp = app.get(self.common_map_req)
            assert resp.content_type == "image/png"
            assert "Cache-Control" not in resp.headers
            img = img_from_buf(resp.body)
            assert_colors_equal(img, [(250 * 250, (100, 200, 50, 250))])
            assert cache_dir.join(
                "tilesource_cache_EPSG4326/01/000/000/001/000/000/000.png"
            ).check()

    def test_wms_unhandled_error_code(self, app):
        expected_req = [
            (
                {"path": "/foo/1/1/0.png"},
                {
                    "body": b"error",
                    "status": 500,
                    "headers": {"content-type": "text/plain"},
                },
            )
        ]

        with mock_httpd(("localhost", 42423), expected_req):
            resp = app.get(self.common_map_req)
            assert_no_cache(resp)
            assert resp.content_type == "application/vnd.ogc.se_xml"
            assert b"500" in resp.body

    def test_wms_catchall_error_no_image_response(self, app):
        expected_req = [
            (
                {"path": "/foo/1/1/0.png"},
                {
                    "body": b"error",
                    "status": 200,
                    "headers": {"content-type": "text/plain"},
                },
            )
        ]

        with mock_httpd(("localhost", 42423), expected_req):
            self.common_map_req.params["layers"] = "tilesource_catchall"
            resp = app.get(self.common_map_req)
            assert_no_cache(resp)
            assert resp.content_type == "image/png"
            img = img_from_buf(resp.body)
            assert img.getcolors() == [(250 * 250, (100, 50, 50))]

    def test_tile_uncached_response(self, app, cache_dir):
        expected_req = [
            (
                {"path": "/foo/1/1/0.png"},
                {
                    "body": b"not found",
                    "status": 404,
                    "headers": {"content-type": "text/plain"},
                },
            )
        ]

        with mock_httpd(("localhost", 42423), expected_req):
            resp = app.get(self.common_tile_req)
            assert_no_cache(resp)
            assert resp.content_type == "image/png"
            img = img_from_buf(resp.body)
            assert img.getcolors() == [(256 * 256, (255, 0, 128))]
            assert not cache_dir.join(
                "tilesource_cache_EPSG4326/01/000/000/001/000/000/000.png"
            ).check()

    def test_tile_cached_response(self, app, cache_dir):
        expected_req = [
            (
                {"path": "/foo/1/1/0.png"},
                {
                    "body": b"no content",
                    "status": 204,
                    "headers": {"content-type": "text/plain"},
                },
            )
        ]

        with mock_httpd(("localhost", 42423), expected_req):
            resp = app.get(self.common_tile_req)
            assert "public" in resp.headers["Cache-Control"]
            assert resp.content_type == "image/png"
            img = img_from_buf(resp.body)
            assert img.getcolors() == [(256 * 256, (100, 200, 50, 250))]
            assert cache_dir.join(
                "tilesource_cache_EPSG4326/01/000/000/001/000/000/000.png"
            ).check()

    def test_tile_unhandled_error_code(self, app):
        expected_req = [
            (
                {"path": "/foo/1/1/0.png"},
                {
                    "body": b"error",
                    "status": 500,
                    "headers": {"content-type": "text/plain"},
                },
            )
        ]

        with mock_httpd(("localhost", 42423), expected_req):
            resp = app.get(self.common_tile_req, status=500)
            assert_no_cache(resp)
            assert resp.content_type == "text/plain"
            assert b"500" in resp.body

    def test_tile_catchall_error_no_image_response(self, app):
        expected_req = [
            (
                {"path": "/foo/1/1/0.png"},
                {
                    "body": b"error",
                    "status": 200,
                    "headers": {"content-type": "text/plain"},
                },
            )
        ]

        with mock_httpd(("localhost", 42423), expected_req):
            resp = app.get(
                self.common_tile_req.replace("tilesource", "tilesource_catchall")
            )
            assert_no_cache(resp)
            assert resp.content_type == "image/png"
            img = img_from_buf(resp.body)
            assert img.getcolors() == [(256 * 256, (100, 50, 50))]
