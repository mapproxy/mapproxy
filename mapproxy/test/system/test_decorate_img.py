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

from io import BytesIO

import pytest

from mapproxy.compat.image import Image
from mapproxy.image import ImageSource
from mapproxy.request.wms import WMS111MapRequest
from mapproxy.request.wmts import WMTS100TileRequest
from mapproxy.test.image import is_png, is_jpeg
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "layer.yaml"


def to_greyscale(image, service, layers, **kw):
    img = image.as_image()
    if hasattr(image.image_opts, "transparent") and image.image_opts.transparent:
        img = img.convert("LA").convert("RGBA")
    else:
        img = img.convert("L").convert("RGB")
    return ImageSource(img, image.image_opts)


@pytest.mark.usefixtures("fixture_cache_data")
class TestDecorateImg(SysTest):

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
                layer="wms_cache",
                format="image/jpeg",
                style="",
                request="GetTile",
            ),
        )

    def test_wms(self, app):
        req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-180,0,0,80",
                width="200",
                height="200",
                layers="wms_cache",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
            ),
        )
        resp = app.get(req, extra_environ={"mapproxy.decorate_img": to_greyscale})
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        assert img.mode == "RGB"

    def test_wms_transparent(self, app):
        req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-180,0,0,80",
                width="200",
                height="200",
                layers="wms_cache_transparent",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
                transparent="True",
            ),
        )
        resp = app.get(req, extra_environ={"mapproxy.decorate_img": to_greyscale})
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        assert img.mode == "RGBA"

    def test_wms_bgcolor(self, app):
        req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-180,0,0,80",
                width="200",
                height="200",
                layers="wms_cache_transparent",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
                bgcolor="0xff00a0",
            ),
        )
        resp = app.get(req, extra_environ={"mapproxy.decorate_img": to_greyscale})
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        assert img.mode == "RGB"
        assert sorted(img.getcolors())[-1][1] == (94, 94, 94)

    def test_wms_args(self, app):
        req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-180,0,0,80",
                width="200",
                height="200",
                layers="wms_cache,wms_cache_transparent",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
                transparent="True",
            ),
        )

        def callback(img_src, service, layers, environ, query_extent):
            assert isinstance(img_src, ImageSource)
            assert "wms.map" == service
            assert len(layers) == 2
            assert "wms_cache_transparent" in layers
            assert "wms_cache" in layers
            assert isinstance(environ, dict)
            assert len(query_extent) == 2
            assert len(query_extent[1]) == 4
            assert query_extent[0] == "EPSG:4326"
            return img_src

        app.get(req, extra_environ={"mapproxy.decorate_img": callback})

    def test_tms(self, app):
        resp = app.get(
            "/tms/1.0.0/wms_cache/0/0/1.jpeg",
            extra_environ={"mapproxy.decorate_img": to_greyscale},
        )
        assert resp.content_type == "image/jpeg"
        assert resp.content_length == len(resp.body)
        data = BytesIO(resp.body)
        assert is_jpeg(data)

    def test_tms_args(self, app):

        def callback(img_src, service, layers, environ, query_extent):
            assert isinstance(img_src, ImageSource)
            assert "tms" == service
            assert "wms_cache" == layers[0]
            assert isinstance(environ, dict)
            assert len(query_extent) == 2
            assert len(query_extent[1]) == 4
            assert query_extent[0] == "EPSG:900913"
            return img_src

        app.get(
            "/tms/1.0.0/wms_cache/0/0/1.jpeg",
            extra_environ={"mapproxy.decorate_img": callback},
        )

    def test_wmts(self, app):
        resp = app.get(
            str(self.common_tile_req),
            extra_environ={"mapproxy.decorate_img": to_greyscale},
        )
        assert resp.content_type == "image/jpeg"
        assert resp.content_length == len(resp.body)
        data = BytesIO(resp.body)
        assert is_jpeg(data)

    def test_wmts_args(self, app):

        def callback(img_src, service, layers, environ, query_extent):
            assert isinstance(img_src, ImageSource)
            assert "wmts" == service
            assert "wms_cache" == layers[0]
            assert isinstance(environ, dict)
            assert len(query_extent) == 2
            assert len(query_extent[1]) == 4
            assert query_extent[0] == "EPSG:900913"
            return img_src

        app.get(
            str(self.common_tile_req), extra_environ={"mapproxy.decorate_img": callback}
        )
