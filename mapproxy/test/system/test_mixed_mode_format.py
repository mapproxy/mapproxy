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

from contextlib import contextmanager
from io import BytesIO

import pytest

from mapproxy.compat.image import Image, ImageDraw, ImageColor
from mapproxy.request.wms import WMS111MapRequest
from mapproxy.request.wmts import WMTS100TileRequest
from mapproxy.test.image import check_format, is_transparent
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "mixed_mode.yaml"


class TestWMS(SysTest):

    def setup(self):
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="0,0,180,80",
                width="200",
                height="200",
                layers="mixed_mode",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
                transparent="true",
            ),
        )
        self.expected_base_path = "/service?SERVICE=WMS&REQUEST=GetMap&HEIGHT=256" "&SRS=EPSG%3A900913&styles=&VERSION=1.1.1&WIDTH=512" "&BBOX=-20037508.3428,0.0,20037508.3428,20037508.3428"

    def test_mixed_mode(self, app, cache_dir):
        req_format = "png"
        transparent = "True"
        with create_mixed_mode_img((512, 256)) as img:
            expected_req = (
                {
                    "path": self.expected_base_path
                    + "&layers=mixedsource"
                    + "&format=image%2F"
                    + req_format
                    + "&transparent="
                    + transparent
                },
                {
                    "body": img.read(),
                    "headers": {"content-type": "image/" + req_format},
                },
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params["format"] = "image/" + req_format
                resp = app.get(self.common_map_req)

                assert resp.content_type == "image/" + req_format
                check_format(BytesIO(resp.body), req_format)
                # GetMap Request is fully within the opaque tile
                assert not is_transparent(resp.body)

        # check cache formats
        for f, format in [
            ["mixed_cache_EPSG900913/01/000/000/000/000/000/001.mixed", "png"],
            ["mixed_cache_EPSG900913/01/000/000/001/000/000/001.mixed", "jpeg"],
        ]:
            assert cache_dir.join(f).check()
            check_format(cache_dir.join(f).read_binary(), format)


class TestTMS(SysTest):

    def setup(self):
        self.expected_base_path = "/service?SERVICE=WMS&REQUEST=GetMap&HEIGHT=256" "&SRS=EPSG%3A900913&styles=&VERSION=1.1.1&WIDTH=512" "&BBOX=-20037508.3428,-20037508.3428,20037508.3428,0.0"

    def test_mixed_mode(self, app, cache_dir):
        with create_mixed_mode_img((512, 256)) as img:
            expected_req = (
                {
                    "path": self.expected_base_path
                    + "&layers=mixedsource"
                    + "&format=image%2Fpng"
                    + "&transparent=True"
                },
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tms/1.0.0/mixed_mode/0/0/0.png")
                assert resp.content_type == "image/png"
                assert is_transparent(resp.body)

                resp = app.get("/tms/1.0.0/mixed_mode/0/1/0.png")

                assert resp.content_type == "image/jpeg"
        assert cache_dir.join(
            "mixed_cache_EPSG900913/01/000/000/000/000/000/000.mixed"
        ).check()
        assert cache_dir.join(
            "mixed_cache_EPSG900913/01/000/000/001/000/000/000.mixed"
        ).check()


class TestWMTS(SysTest):

    def setup(self):
        self.common_tile_req = WMTS100TileRequest(
            url="/service?",
            param=dict(
                service="WMTS",
                version="1.0.0",
                tilerow="0",
                tilecol="0",
                tilematrix="01",
                tilematrixset="GLOBAL_MERCATOR",
                layer="mixed_mode",
                format="image/png",
                style="",
                request="GetTile",
                transparent="True",
            ),
        )
        self.expected_base_path = "/service?SERVICE=WMS&REQUEST=GetMap&HEIGHT=256" "&SRS=EPSG%3A900913&styles=&VERSION=1.1.1&WIDTH=512" "&BBOX=-20037508.3428,0.0,20037508.3428,20037508.3428"

    def test_mixed_mode(self, app, cache_dir):
        with create_mixed_mode_img((512, 256)) as img:
            expected_req = (
                {
                    "path": self.expected_base_path
                    + "&layers=mixedsource"
                    + "&format=image%2Fpng"
                    + "&transparent=True"
                },
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get(self.common_tile_req)
                assert resp.content_type == "image/png"
                assert is_transparent(resp.body)

                self.common_tile_req.params["tilecol"] = "1"
                resp = app.get(self.common_tile_req)
                assert resp.content_type == "image/jpeg"
        assert cache_dir.join(
            "mixed_cache_EPSG900913/01/000/000/000/000/000/001.mixed"
        ).check()
        assert cache_dir.join(
            "mixed_cache_EPSG900913/01/000/000/001/000/000/001.mixed"
        ).check()


@contextmanager
def create_mixed_mode_img(size, format="png"):
    img = Image.new("RGBA", size)

    # draw a black rectangle into the image, rect_width = 3/4 img_width
    # thus 1/4 of the image is transparent and with square tiles, one of two
    # tiles (img size = 512x256) will be fully opaque and the other
    # has transparency
    draw = ImageDraw.Draw(img)
    w, h = size
    red_color = ImageColor.getrgb("red")
    draw.rectangle((w / 4, 0, w, h), fill=red_color)

    data = BytesIO()
    img.save(data, format)
    data.seek(0)
    yield data
