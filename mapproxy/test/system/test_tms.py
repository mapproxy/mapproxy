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

import os
import hashlib

from io import BytesIO

import pytest

from mapproxy.compat.image import Image
from mapproxy.test.image import is_jpeg, tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "layer.yaml"


class TestTMS(SysTest):

    def test_tms_capabilities(self, app):
        resp = app.get("/tms/1.0.0/")
        assert "WMS Cache Layer" in resp
        assert "WMS Cache Multi Layer" in resp
        assert "TMS Cache Layer" in resp
        assert "TMS Cache Layer + FI" in resp
        xml = resp.lxml
        assert xml.xpath("count(//TileMap)") == 11

        # without trailing space
        resp2 = app.get("/tms/1.0.0")
        assert resp.body == resp2.body

    def test_tms_layer_capabilities(self, app):
        resp = app.get("/tms/1.0.0/wms_cache")
        assert "WMS Cache Layer" in resp
        xml = resp.lxml
        assert xml.xpath("count(//TileSet)") == 19

    def test_tms_root_resource(self, app):
        resp = app.get("/tms")
        resp2 = app.get("/tms/")
        assert "TileMapService" in resp and "TileMapService" in resp2
        xml = resp.lxml
        assert xml.xpath("//TileMapService/@version") == ["1.0.0"]

    def test_tms_get_out_of_bounds_tile(self, app):
        for coord in [(0, 0, -1), (-1, 0, 0), (0, -1, 0), (4, 2, 1), (1, 3, 0)]:
            x, y, z = coord
            url = "/tms/1.0.0/wms_cache/%d/%d/%d.jpeg" % (z, x, y)
            resp = app.get(url, status=404)
            xml = resp.lxml
            assert (
                "outside the bounding box"
                in xml.xpath("/TileMapServerError/Message/text()")[0]
            )

    def test_invalid_layer(self, app):
        resp = app.get("/tms/1.0.0/inVAlid/0/0/0.png", status=404)
        xml = resp.lxml
        assert (
            "unknown layer: inVAlid"
            in xml.xpath("/TileMapServerError/Message/text()")[0]
        )

    def test_invalid_format(self, app):
        resp = app.get("/tms/1.0.0/wms_cache/0/0/1.png", status=404)
        xml = resp.lxml
        assert "invalid format" in xml.xpath("/TileMapServerError/Message/text()")[0]

    def test_get_tile_tile_source_error(self, app):
        resp = app.get("/tms/1.0.0/wms_cache/0/0/0.jpeg", status=500)
        xml = resp.lxml
        assert (
            "No response from URL" in xml.xpath("/TileMapServerError/Message/text()")[0]
        )

    def test_get_cached_tile(self, app, fixture_cache_data):
        resp = app.get("/tms/1.0.0/wms_cache/0/0/1.jpeg")
        assert resp.content_type == "image/jpeg"
        assert resp.content_length == len(resp.body)
        data = BytesIO(resp.body)
        assert is_jpeg(data)

    def test_get_tile(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=-20037508.3428,-20037508.3428,0.0,0.0"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tms/1.0.0/wms_cache/0/0/0.jpeg")
                assert resp.content_type == "image/jpeg"
        assert cache_dir.join(
            "wms_cache_EPSG900913/01/000/000/000/000/000/000.jpeg"
        ).check()

    def test_get_tile_from_cache_with_tile_source(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {"path": r"/tiles/01/000/000/000/000/000/001.png"},
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                resp = app.get("/tms/1.0.0/tms_cache/0/0/1.png")
                assert resp.content_type == "image/png"
        assert cache_dir.join(
            "tms_cache_EPSG900913/01/000/000/000/000/000/001.png"
        ).check()

    def test_get_tile_with_watermark_cache(self, app):
        with tmp_image((256, 256), format="png", color=(0, 0, 0)) as img:
            expected_req = (
                {"path": r"/tiles/01/000/000/000/000/000/000.png"},
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(("localhost", 42423), [expected_req]):
                resp = app.get("/tms/1.0.0/watermark_cache/0/0/0.png")
                assert resp.content_type == "image/png"
                img = Image.open(BytesIO(resp.body))
                colors = img.getcolors()
                assert len(colors) >= 2
                assert sorted(colors)[-1][1] == (0, 0, 0)


class TestTileService(SysTest):

    def test_get_out_of_bounds_tile(self, app):
        for coord in [(0, 0, -1), (-1, 0, 0), (0, -1, 0), (4, 2, 1), (1, 3, 0)]:
            x, y, z = coord
            url = "/tiles/wms_cache/%d/%d/%d.jpeg" % (z, x, y)
            resp = app.get(url, status=404)
            assert "outside the bounding box" in resp

    def test_invalid_layer(self, app):
        resp = app.get("/tiles/inVAlid/0/0/0.png", status=404)
        assert resp.content_type == "text/plain"
        assert "unknown layer: inVAlid" in resp

    def test_invalid_format(self, app):
        resp = app.get("/tiles/wms_cache/0/0/1.png", status=404)
        assert resp.content_type == "text/plain"
        assert "invalid format" in resp

    def test_get_tile_tile_source_error(self, app):
        resp = app.get("/tiles/wms_cache/0/0/0.jpeg", status=500)
        assert resp.content_type == "text/plain"
        assert "No response from URL" in resp

    def _check_tile_resp(self, resp):
        assert resp.content_type == "image/jpeg"
        assert resp.content_length == len(resp.body)
        data = BytesIO(resp.body)
        assert is_jpeg(data)

    def _update_timestamp(self, cache_dir, base_config):
        timestamp = 1234567890.0
        size = 10214
        base_dir = base_config.cache.base_dir
        os.utime(
            os.path.join(
                base_dir, "wms_cache_EPSG900913/01/000/000/000/000/000/001.jpeg"
            ),
            (timestamp, timestamp),
        )
        max_age = base_config.tiles.expires_hours * 60 * 60
        etag = hashlib.md5((str(timestamp) + str(size)).encode("ascii")).hexdigest()
        return etag, max_age

    def _check_cache_control_headers(self, resp, etag, max_age):
        assert resp.headers["ETag"] == etag
        assert resp.headers["Last-modified"] == "Fri, 13 Feb 2009 23:31:30 GMT"
        assert resp.headers["Cache-control"] == "public, max-age=%d, s-maxage=%d" % (
            max_age,
            max_age,
        )

    def test_get_cached_tile(self, app, cache_dir, base_config, fixture_cache_data):
        etag, max_age = self._update_timestamp(cache_dir, base_config)
        resp = app.get("/tiles/wms_cache/1/0/1.jpeg")
        self._check_cache_control_headers(resp, etag, max_age)
        self._check_tile_resp(resp)

    def test_get_cached_tile_flipped_y(
        self, app, cache_dir, base_config, fixture_cache_data
    ):
        etag, max_age = self._update_timestamp(cache_dir, base_config)
        resp = app.get("/tiles/wms_cache/1/0/0.jpeg?origin=nw")
        self._check_cache_control_headers(resp, etag, max_age)
        self._check_tile_resp(resp)

    def test_if_none_match(self, app, cache_dir, base_config, fixture_cache_data):
        etag, max_age = self._update_timestamp(cache_dir, base_config)
        resp = app.get("/tiles/wms_cache/1/0/1.jpeg", headers={"If-None-Match": etag})
        assert resp.status == "304 Not Modified"
        self._check_cache_control_headers(resp, etag, max_age)

        resp = app.get(
            "/tiles/wms_cache/1/0/1.jpeg", headers={"If-None-Match": etag + "foo"}
        )
        self._check_cache_control_headers(resp, etag, max_age)
        assert resp.status == "200 OK"
        self._check_tile_resp(resp)

    @pytest.mark.parametrize(
        "date,modified",
        [
            ("Fri, 15 Feb 2009 23:31:30 GMT", False),
            ("Fri, 13 Feb 2009 23:31:31 GMT", False),
            ("Fri, 13 Feb 2009 23:31:30 GMT", False),
            ("Fri, 13 Feb 2009 23:31:29 GMT", True),
            ("Fri, 11 Feb 2009 23:31:29 GMT", True),
            ("Friday, 13-Feb-09 23:31:30 GMT", False),
            ("Friday, 13-Feb-09 23:31:29 GMT", True),
            ("Fri Feb 13 23:31:30 2009", False),
            ("Fri Feb 13 23:31:29 2009", True),
            # and some invalid ones
            ("Fri Foo 13 23:31:29 2009", True),
            ("1234567890", True),
        ],
    )
    def test_if_modified_since(
        self, app, cache_dir, base_config, fixture_cache_data, date, modified
    ):
        etag, max_age = self._update_timestamp(cache_dir, base_config)
        resp = app.get(
            "/tiles/wms_cache/1/0/1.jpeg", headers={"If-Modified-Since": date}
        )
        self._check_cache_control_headers(resp, etag, max_age)
        if modified:
            assert resp.status == "200 OK"
            self._check_tile_resp(resp)
        else:
            assert resp.status == "304 Not Modified"

    def test_get_tile(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=-20037508.3428,-20037508.3428,0.0,0.0"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tiles/wms_cache/1/0/0.jpeg")
                assert resp.content_type == "image/jpeg"
        assert cache_dir.join(
            "wms_cache_EPSG900913/01/000/000/000/000/000/000.jpeg"
        ).check()
