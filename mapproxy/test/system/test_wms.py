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

from __future__ import print_function, division

import re
import sys
import functools

from io import BytesIO

import pytest

from mapproxy.image import ImageSource
from mapproxy.srs import SRS
from mapproxy.compat.image import Image
from mapproxy.request.wms import (
    WMS100MapRequest,
    WMS111MapRequest,
    WMS130MapRequest,
    WMS111FeatureInfoRequest,
    WMS111CapabilitiesRequest,
    WMS130CapabilitiesRequest,
    WMS100CapabilitiesRequest,
    WMS100FeatureInfoRequest,
    WMS130FeatureInfoRequest,
    WMS110MapRequest,
    WMS110FeatureInfoRequest,
    WMS110CapabilitiesRequest,
    wms_request,
)
from mapproxy.test.image import is_jpeg, is_png, tmp_image, create_tmp_image
from mapproxy.test.unit.test_image import assert_geotiff_tags
from mapproxy.test.http import mock_httpd
from mapproxy.test.helper import validate_with_dtd, validate_with_xsd
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "layer.yaml"


class TestBase(SysTest):

    def test_invalid_url(self, app):
        app.get("/invalid?fop", status=404)


class TestCoverageWMS(SysTest):
    config_file = "layer.yaml"

    def test_unknown_version_110(self, app):
        resp = app.get(
            "http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities"
            "&VERSION=1.1.0"
        )
        assert is_110_capa(resp.lxml)

    def test_unknown_version_113(self, app):
        resp = app.get(
            "http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities"
            "&VERSION=1.1.3"
        )
        assert is_111_capa(resp.lxml)

    def test_unknown_version_090(self, app):
        resp = app.get(
            "http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities"
            "&WMTVER=0.9.0"
        )
        assert is_100_capa(resp.lxml)

    def test_unknown_version_200(self, app):
        resp = app.get(
            "http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities"
            "&VERSION=2.0.0"
        )
        assert is_130_capa(resp.lxml)


def bbox_srs_from_boundingbox(bbox_elem):
    return [
        float(bbox_elem.attrib["minx"]),
        float(bbox_elem.attrib["miny"]),
        float(bbox_elem.attrib["maxx"]),
        float(bbox_elem.attrib["maxy"]),
    ]


class TestWMS111(SysTest):
    config_file = "layer.yaml"

    def setup(self):
        # WMSTest.setup(self)
        self.common_req = WMS111MapRequest(
            url="/service?", param=dict(service="WMS", version="1.1.1")
        )
        self.common_map_req = WMS111MapRequest(
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
        self.common_fi_req = WMS111FeatureInfoRequest(
            url="/service?",
            param=dict(
                x="10",
                y="20",
                width="200",
                height="200",
                layers="wms_cache",
                format="image/png",
                query_layers="wms_cache",
                styles="",
                bbox="1000,400,2000,1400",
                srs="EPSG:900913",
            ),
        )

    def test_invalid_request_type(self, app):
        req = str(self.common_map_req).replace("GetMap", "invalid")
        resp = app.get(req)
        is_111_exception(resp.lxml, "unknown WMS request type 'invalid'")

    def test_endpoints(self, app):
        for endpoint in ("service", "ows", "wms"):
            req = WMS111CapabilitiesRequest(
                url="/%s?" % endpoint
            ).copy_with_request_params(self.common_req)
            resp = app.get(req)
            assert resp.content_type == "application/vnd.ogc.wms_xml"
            xml = resp.lxml
            assert validate_with_dtd(xml, dtd_name="wms/1.1.1/WMS_MS_Capabilities.dtd")

    def test_wms_capabilities(self, app):
        req = WMS111CapabilitiesRequest(url="/service?").copy_with_request_params(
            self.common_req
        )
        resp = app.get(req)
        assert resp.content_type == "application/vnd.ogc.wms_xml"
        xml = resp.lxml
        assert (
            xml.xpath(
                "//GetMap//OnlineResource/@xlink:href",
                namespaces=dict(xlink="http://www.w3.org/1999/xlink"),
            )[0] ==
            "http://localhost/service?"
        )

        # test for MetadataURL
        assert (
            xml.xpath(
                "//Layer/MetadataURL/OnlineResource/@xlink:href",
                namespaces=dict(xlink="http://www.w3.org/1999/xlink"),
            )[0] ==
            "http://some.url/"
        )
        assert xml.xpath("//Layer/MetadataURL/@type")[0] == "TC211"

        layer_names = set(xml.xpath("//Layer/Layer/Name/text()"))
        expected_names = set(
            [
                "direct_fwd_params",
                "direct",
                "wms_cache",
                "wms_cache_100",
                "wms_cache_130",
                "wms_cache_transparent",
                "wms_merge",
                "tms_cache",
                "tms_fi_cache",
                "wms_cache_multi",
                "wms_cache_link_single",
                "wms_cache_110",
                "watermark_cache",
                "wms_managed_cookies_cache",
            ]
        )
        assert layer_names == expected_names
        assert set(xml.xpath("//Layer/Layer[3]/Abstract/text()")) == set(["Some abstract"])

        bboxs = xml.xpath("//Layer/Layer[1]/BoundingBox")
        bboxs = dict((e.attrib["SRS"], e) for e in bboxs)
        assert_almost_equal_bbox(
            bbox_srs_from_boundingbox(bboxs["EPSG:3857"]),
            [-20037508.3428, -15538711.0963, 18924313.4349, 15538711.0963],
        )
        assert_almost_equal_bbox(
            bbox_srs_from_boundingbox(bboxs["EPSG:4326"]), [-180.0, -70.0, 170.0, 80.0]
        )

        bbox_srs = xml.xpath("//Layer/Layer/BoundingBox")
        bbox_srs = set(e.attrib["SRS"] for e in bbox_srs)
        # we have a coverage in EPSG:4258, but it is not in wms.srs (#288)
        assert "EPSG:4258" not in bbox_srs

        assert validate_with_dtd(xml, dtd_name="wms/1.1.1/WMS_MS_Capabilities.dtd")

    def test_invalid_layer(self, app):
        self.common_map_req.params["layers"] = "invalid"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        is_111_exception(resp.lxml, "unknown layer: invalid", "LayerNotDefined")

    def test_invalid_layer_img_exception(self, app):
        self.common_map_req.params["layers"] = "invalid"
        self.common_map_req.params["exceptions"] = "application/vnd.ogc.se_inimage"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        assert is_png(BytesIO(resp.body))

    def test_invalid_format(self, app):
        self.common_map_req.params["format"] = "image/ascii"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        is_111_exception(
            resp.lxml, "unsupported image format: image/ascii", "InvalidFormat"
        )

    def test_invalid_format_img_exception(self, app):
        self.common_map_req.params["format"] = "image/ascii"
        self.common_map_req.params["exceptions"] = "application/vnd.ogc.se_inimage"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        assert is_png(BytesIO(resp.body))

    def test_invalid_format_options_img_exception(self, app):
        self.common_map_req.params["format"] = "image/png; mode=12bit"
        self.common_map_req.params["exceptions"] = "application/vnd.ogc.se_inimage"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        assert is_png(BytesIO(resp.body))

    def test_missing_format_img_exception(self, app):
        del self.common_map_req.params["format"]
        self.common_map_req.params["exceptions"] = "application/vnd.ogc.se_inimage"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        assert is_png(BytesIO(resp.body))

    def test_invalid_srs(self, app):
        self.common_map_req.params["srs"] = "EPSG:1234"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        is_111_exception(resp.lxml, "unsupported srs: EPSG:1234", "InvalidSRS")

    def test_get_map_unknown_style(self, app):
        self.common_map_req.params["styles"] = "unknown"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        is_111_exception(resp.lxml, "unsupported styles: unknown", "StyleNotDefined")

    def test_get_map_too_large(self, app):
        self.common_map_req.params.size = (5000, 5000)
        self.common_map_req.params["exceptions"] = "application/vnd.ogc.se_inimage"
        resp = app.get(self.common_map_req)
        # is xml, even if inimage was requested
        assert resp.content_type == "application/vnd.ogc.se_xml"
        is_111_exception(resp.lxml, "image size too large")

    def test_get_map_default_style(self, app, fixture_cache_data):
        self.common_map_req.params["styles"] = "default"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        assert Image.open(data).mode == "RGB"

    def test_get_map_png(self, app, fixture_cache_data):
        resp = app.get(self.common_map_req)
        assert "Cache-Control" not in resp.headers
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        assert Image.open(data).mode == "RGB"

    def test_get_map_float_size(self, app, fixture_cache_data):
        self.common_map_req.params['width'] = '200.0'
        resp = app.get(self.common_map_req)
        assert "Cache-Control" not in resp.headers
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        assert Image.open(data).mode == "RGB"

    def test_get_map_png8_custom_format(self, app, fixture_cache_data):
        self.common_map_req.params["layers"] = "wms_cache"
        self.common_map_req.params["format"] = "image/png; mode=8bit"
        resp = app.get(self.common_map_req)
        assert resp.headers["Content-type"] == "image/png; mode=8bit"
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        assert img.mode == "P"

    def test_get_map_png_transparent_non_transparent_data(
        self, app, fixture_cache_data
    ):
        self.common_map_req.params["transparent"] = "True"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        assert img.mode == "RGB"

    def test_get_map_png_transparent(self, app, fixture_cache_data):
        self.common_map_req.params["layers"] = "wms_cache_transparent"
        self.common_map_req.params["transparent"] = "True"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        assert Image.open(data).mode == "RGBA"

    def test_get_map_png_w_default_bgcolor(self, app, fixture_cache_data):
        self.common_map_req.params["layers"] = "wms_cache_transparent"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        assert img.mode == "RGB"
        assert img.getcolors()[0][1] == (255, 255, 255)

    def test_get_map_png_w_bgcolor(self, app, fixture_cache_data):
        self.common_map_req.params["layers"] = "wms_cache_transparent"
        self.common_map_req.params["bgcolor"] = "0xff00a0"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        assert img.mode == "RGB"
        assert sorted(img.getcolors())[-1][1] == (255, 0, 160)

    def test_get_map_jpeg(self, app, fixture_cache_data):
        self.common_map_req.params["format"] = "image/jpeg"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/jpeg"
        assert is_jpeg(BytesIO(resp.body))

    def test_get_map_geotiff(self, app, fixture_cache_data):
        self.common_map_req.params["format"] = "image/tiff"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/tiff"
        img = ImageSource(BytesIO(resp.body)).as_image()
        assert_geotiff_tags(img, (-180, 80), (180/200.0, 80/200.0), 4326, False)

    def test_get_map_xml_exception(self, app):
        self.common_map_req.params["bbox"] = "0,0,90,90"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        xml = resp.lxml
        assert xml.xpath("/ServiceExceptionReport/ServiceException/@code") == []
        assert "No response from URL" in xml.xpath("//ServiceException/text()")[0]
        assert validate_with_dtd(xml, "wms/1.1.1/exception_1_1_1.dtd")

    def test_direct_layer_error(self, app):
        self.common_map_req.params["layers"] = "direct"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        xml = resp.lxml
        assert xml.xpath("/ServiceExceptionReport/ServiceException/@code") == []
        # TODO hide error
        # assert 'unable to get map for layers: direct' in \
        #     xml.xpath('//ServiceException/text()')[0]
        assert "No response from URL" in xml.xpath("//ServiceException/text()")[0]

        assert validate_with_dtd(xml, "wms/1.1.1/exception_1_1_1.dtd")

    def test_direct_layer_non_image_response(self, app):
        self.common_map_req.params["layers"] = "direct"
        expected_req = (
            {
                "path": r"/service?LAYERs=bar&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles="
                "&VERSION=1.1.1&BBOX=-180.0,0.0,0.0,80.0"
                "&WIDTH=200"
            },
            {"body": b"notanimage", "headers": {"content-type": "image/jpeg"}},
        )
        with mock_httpd(("localhost", 42423), [expected_req]):
            resp = app.get(self.common_map_req)
            assert resp.content_type == "application/vnd.ogc.se_xml"
            xml = resp.lxml
            assert xml.xpath("/ServiceExceptionReport/ServiceException/@code") == []
            assert (
                "error while processing image file"
                in xml.xpath("//ServiceException/text()")[0]
            )

            assert validate_with_dtd(xml, "wms/1.1.1/exception_1_1_1.dtd")

    def test_get_map_non_image_response(self, app, cache_dir):
        expected_req = (
            {
                "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                "&VERSION=1.1.1&BBOX=0.0,0.0,20037508.3428,20037508.3428"
                "&WIDTH=256"
            },
            {"body": b"notanimage", "headers": {"content-type": "image/jpeg"}},
        )
        with mock_httpd(
            ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
        ):
            self.common_map_req.params["bbox"] = "0,0,180,90"
            resp = app.get(self.common_map_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"

        xml = resp.lxml
        assert xml.xpath("/ServiceExceptionReport/ServiceException/@code") == []
        assert (
            "unable to transform image: cannot identify image file"
            in xml.xpath("//ServiceException/text()")[0]
        )

        assert validate_with_dtd(xml, "wms/1.1.1/exception_1_1_1.dtd")

        assert cache_dir.join(
            "wms_cache_EPSG900913/01/000/000/001/000/000/001.jpeg"
        ).check()

    def test_get_map(self, app, base_dir, cache_dir):
        # check global tile lock directory
        tiles_lock_dir = base_dir.join("wmscachetilelockdir")
        # make sure global tile_lock_dir was ot created by other tests
        if tiles_lock_dir.check():
            tiles_lock_dir.remove()

        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=0.0,0.0,20037508.3428,20037508.3428"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params["bbox"] = "0,0,180,90"
                resp = app.get(self.common_map_req)
                assert 35000 < int(resp.headers["Content-length"]) < 75000
                assert resp.content_type == "image/png"

        # check custom tile_lock_dir
        assert cache_dir.join(
            "wms_cache_EPSG900913/01/000/000/001/000/000/001.jpeg"
        ).check()
        assert tiles_lock_dir.check()

    def test_get_map_direct_fwd_params_layer(self, app):
        img = create_tmp_image((200, 200), format="png")
        expected_req = (
            {
                "path": r"/service?LAYERs=bar&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles="
                "&VERSION=1.1.1&BBOX=-180.0,0.0,0.0,80.0"
                "&WIDTH=200&TIME=20041012"
            },
            {"body": img},
        )
        with mock_httpd(
            ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
        ):
            self.common_map_req.params["layers"] = "direct_fwd_params"
            self.common_map_req.params["time"] = "20041012"
            resp = app.get(self.common_map_req)
            assert resp.content_type == "image/png"

    def test_get_map_use_direct_from_level(self, app):
        with tmp_image((200, 200), format="png") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fpng"
                    "&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326&styles="
                    "&VERSION=1.1.1&BBOX=5.0,-10.0,6.0,-9.0"
                    "&WIDTH=200"
                },
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params["bbox"] = "5,-10,6,-9"
                resp = app.get(self.common_map_req)
                img.seek(0)
                assert resp.body == img.read()
                is_png(img)
                assert resp.content_type == "image/png"

    def test_get_map_use_direct_from_level_with_transform(self, app):
        with tmp_image((200, 200), format="png") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fpng"
                    "&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=908822.944624,7004479.85652,920282.144964,7014491.63726"
                    "&WIDTH=229"
                },
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params[
                    "bbox"
                ] = "444122.311736,5885498.04243,450943.508884,5891425.10484"
                self.common_map_req.params["srs"] = "EPSG:25832"
                resp = app.get(self.common_map_req)
                img.seek(0)
                assert resp.body != img.read()
                is_png(img)
                assert resp.content_type == "image/png"

    def test_get_map_invalid_bbox(self, app):
        # min x larger than max x
        url = (
            """/service?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&BBOX=7,2,-9,10&SRS=EPSG:4326&WIDTH=164&HEIGHT=388&LAYERS=wms_cache&STYLES=&FORMAT=image/png&TRANSPARENT=TRUE"""
        )
        resp = app.get(url)
        is_111_exception(resp.lxml, "invalid bbox 7,2,-9,10")

    def test_get_map_invalid_bbox2(self, app):
        # broken bbox for the requested srs
        url = (
            """/service?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&BBOX=-72988843.697212,-255661507.634227,142741550.188860,255661507.634227&SRS=EPSG:25833&WIDTH=164&HEIGHT=388&LAYERS=wms_cache_100&STYLES=&FORMAT=image/png&TRANSPARENT=TRUE"""
        )
        resp = app.get(url)
        # result depends on proj version
        is_111_exception(
            resp.lxml,
            re_msg="Request too large or invalid BBOX.|Could not transform BBOX: Invalid result.",
        )

    def test_get_map_broken_bbox(self, app):
        url = (
            """/service?VERSION=1.1.11&REQUEST=GetMap&SRS=EPSG:31468&BBOX=-20000855.0573254,2847125.18913603,-19329367.42767611,4239924.78564583&WIDTH=130&HEIGHT=62&LAYERS=wms_cache&STYLES=&FORMAT=image/png&TRANSPARENT=TRUE"""
        )
        resp = app.get(url)
        is_111_exception(resp.lxml, "Could not transform BBOX: Invalid result.")

    def test_get_map100(self, app, base_dir, cache_dir):
        # check global tile lock directory
        tiles_lock_dir = base_dir.join("defaulttilelockdir")
        # make sure global tile_lock_dir was ot created by other tests
        if tiles_lock_dir.check():
            tiles_lock_dir.remove()

        # request_format tiff, cache format jpeg, wms request in png
        with tmp_image((256, 256), format="tiff") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&FORMAT=TIFF"
                    "&REQUEST=map&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&WMTVER=1.0.0&BBOX=0.0,0.0,20037508.3428,20037508.3428"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/tiff"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params["bbox"] = "0,0,180,90"
                self.common_map_req.params["layers"] = "wms_cache_100"
                resp = app.get(self.common_map_req)
                assert resp.content_type == "image/png"

        # check global tile lock directory was created
        assert tiles_lock_dir.check()

        assert cache_dir.join(
            "wms_cache_100_EPSG900913/01/000/000/001/000/000/001.jpeg"
        ).check()

    def test_get_map130(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&CRS=EPSG%3A900913&styles="
                    "&VERSION=1.3.0&BBOX=0.0,0.0,20037508.3428,20037508.3428"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params["bbox"] = "0,0,180,90"
                self.common_map_req.params["layers"] = "wms_cache_130"
                resp = app.get(self.common_map_req)
                assert resp.content_type == "image/png"
        assert cache_dir.join(
            "wms_cache_130_EPSG900913/01/000/000/001/000/000/001.jpeg"
        ).check()

    def test_get_map130_axis_order(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            img = img.read()
            expected_reqs = [
                (
                    {
                        "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                        "&REQUEST=GetMap&HEIGHT=256&CRS=EPSG%3A4326&styles="
                        "&VERSION=1.3.0&BBOX=0.0,90.0,90.0,180.0"
                        "&WIDTH=256"
                    },
                    {"body": img, "headers": {"content-type": "image/jpeg"}},
                )
            ]
            with mock_httpd(("localhost", 42423), expected_reqs):
                self.common_map_req.params["bbox"] = "90,0,180,90"
                self.common_map_req.params["layers"] = "wms_cache_multi"
                resp = app.get(self.common_map_req)
                assert resp.content_type == "image/png"
        assert cache_dir.join(
            "wms_cache_multi_EPSG4326/02/000/000/003/000/000/001.jpeg"
        ).check()

    def test_get_featureinfo(self, app):
        expected_req = (
            {
                "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913"
                "&VERSION=1.1.1&BBOX=1000.0,400.0,2000.0,1400.0&styles="
                "&WIDTH=200&QUERY_LAYERS=foo,bar&X=10&Y=20&feature_count=100"
            },
            {"body": b"info", "headers": {"content-type": "text/plain"}},
        )
        with mock_httpd(("localhost", 42423), [expected_req]):
            self.common_fi_req.params["feature_count"] = 100
            resp = app.get(self.common_fi_req)
            assert resp.content_type == "text/plain"
            assert resp.body == b"info"

    def test_get_featureinfo_coverage(self, app):
        self.common_fi_req.params["bbox"] = "-180.0,-90.0,180.0,90.0"
        self.common_fi_req.params["srs"] = "EPSG:4326"
        self.common_fi_req.params["width"] = "400"
        self.common_fi_req.params["height"] = "200"
        self.common_fi_req.params["x"] = 395  # outside of coverage
        self.common_fi_req.params["y"] = 50
        self.common_fi_req.params["layers"] = 'tms_fi_cache'
        self.common_fi_req.params["query_layers"] = 'tms_fi_cache'

        resp = app.get(self.common_fi_req)
        assert resp.body == b""
        assert resp.content_type == "text/plain"

        expected_req = (
            {
                "path": r"/service?LAYERs=fi&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A4326"
                "&VERSION=1.1.1&BBOX=-180.0,-90.0,180.0,90.0&styles="
                "&WIDTH=400&QUERY_LAYERS=fi&X=380&Y=50"
            },
            {"body": b"info", "headers": {"content-type": "text/plain"}},
        )
        with mock_httpd(("localhost", 42423), [expected_req]):
            self.common_fi_req.params["x"] = 380  # inside of coverage

            resp = app.get(self.common_fi_req)
            assert resp.body == b"info"
            assert resp.content_type == "text/plain"

    def test_get_featureinfo_float(self, app):
        expected_req = (
            {
                "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913"
                "&VERSION=1.1.1&BBOX=1000.0,400.0,2000.0,1400.0&styles="
                "&WIDTH=200&QUERY_LAYERS=foo,bar&X=10.123&Y=20.567&feature_count=100"
            },
            {"body": b"info", "headers": {"content-type": "text/plain"}},
        )
        with mock_httpd(("localhost", 42423), [expected_req]):
            self.common_fi_req.params["feature_count"] = 100
            self.common_fi_req.params["x"] = 10.123
            self.common_fi_req.params["y"] = 20.567
            resp = app.get(self.common_fi_req)
            assert resp.content_type == "text/plain"
            assert resp.body == b"info"

    def test_get_featureinfo_transformed(self, app):
        expected_req = (
            {
                "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913"
                "&BBOX=1172272.30156,7196018.03449,1189711.04571,7213496.99738"
                "&styles=&VERSION=1.1.1&feature_count=100"
                "&WIDTH=200&QUERY_LAYERS=foo,bar&X=14&Y=20"
            },
            {"body": b"info", "headers": {"content-type": "text/plain"}},
        )

        # out fi point at x=10,y=20
        p_25832 = (
            600000 + 10 * (610000 - 600000) / 200,
            6010000 - 20 * (6010000 - 6000000) / 200,
        )
        # the transformed fi point at x=14,y=20
        p_900913 = (
            1172272.30156 + 14 * (1189711.04571 - 1172272.30156) / 200,
            7213496.99738 - 20 * (7213496.99738 - 7196018.03449) / 200,
        )

        # are they the same?
        # check with tolerance: pixel resolution is ~50 and x/y position is rounded to pizel
        assert abs(SRS(25832).transform_to(SRS(900913), p_25832)[0] - p_900913[0]) < 50
        assert abs(SRS(25832).transform_to(SRS(900913), p_25832)[1] - p_900913[1]) < 50

        with mock_httpd(
            ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
        ):
            self.common_fi_req.params["bbox"] = "600000,6000000,610000,6010000"
            self.common_fi_req.params["srs"] = "EPSG:25832"
            self.common_fi_req.params.pos = 10, 20
            self.common_fi_req.params["feature_count"] = 100
            resp = app.get(self.common_fi_req)
            assert resp.content_type == "text/plain"
            assert resp.body == b"info"

    def test_get_featureinfo_info_format(self, app):
        expected_req = (
            {
                "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913"
                "&VERSION=1.1.1&BBOX=1000.0,400.0,2000.0,1400.0&styles="
                "&WIDTH=200&QUERY_LAYERS=foo,bar&X=10&Y=20"
                "&info_format=text%2Fhtml"
            },
            {"body": b"info", "headers": {"content-type": "text/html"}},
        )
        with mock_httpd(("localhost", 42423), [expected_req]):
            self.common_fi_req.params["info_format"] = "text/html"
            resp = app.get(self.common_fi_req)
            assert resp.content_type == "text/html"
            assert resp.body == b"<html><body><p>info</p></body></html>"

    def test_get_featureinfo_130(self, app):
        expected_req = (
            {
                "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetFeatureInfo&HEIGHT=200&CRS=EPSG%3A900913"
                "&VERSION=1.3.0&BBOX=1000.0,400.0,2000.0,1400.0&styles="
                "&WIDTH=200&QUERY_LAYERS=foo,bar&I=10&J=20"
            },
            {"body": b"info", "headers": {"content-type": "text/plain"}},
        )
        with mock_httpd(("localhost", 42423), [expected_req]):
            self.common_fi_req.params["layers"] = "wms_cache_130"
            self.common_fi_req.params["query_layers"] = "wms_cache_130"
            resp = app.get(self.common_fi_req)
            assert resp.content_type == "text/plain"
            assert resp.body == b"info"

    def test_get_featureinfo_missing_params(self, app):
        expected_req = (
            {
                "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913"
                "&VERSION=1.1.1&BBOX=1000.0,400.0,2000.0,1400.0&styles="
                "&WIDTH=200&QUERY_LAYERS=foo,bar&X=10&Y=20"
            },
            {"body": b"info", "headers": {"content-type": "text/plain"}},
        )
        with mock_httpd(("localhost", 42423), [expected_req]):
            del self.common_fi_req.params["format"]
            del self.common_fi_req.params["styles"]
            resp = app.get(self.common_fi_req)
            assert resp.content_type == "text/plain"
            assert resp.body == b"info"

    def test_get_featureinfo_missing_params_strict(self, app):
        request_parser = app.app.handlers["service"].services["wms"].request_parser
        try:
            app.app.handlers["service"].services[
                "wms"
            ].request_parser = functools.partial(wms_request, strict=True)

            del self.common_fi_req.params["format"]
            del self.common_fi_req.params["styles"]
            resp = app.get(self.common_fi_req)
            xml = resp.lxml
            assert "missing parameters" in xml.xpath("//ServiceException/text()")[0]
            assert validate_with_dtd(xml, "wms/1.1.1/exception_1_1_1.dtd")
        finally:
            app.app.handlers["service"].services["wms"].request_parser = request_parser
            app.app.handlers["service"].request_parser = request_parser

    def test_get_featureinfo_not_queryable(self, app):
        self.common_fi_req.params["query_layers"] = "tms_cache"
        self.common_fi_req.params["exceptions"] = "application/vnd.ogc.se_xml"
        resp = app.get(self.common_fi_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        xml = resp.lxml
        assert xml.xpath("/ServiceExceptionReport/ServiceException/@code") == []
        assert "tms_cache is not queryable" in xml.xpath("//ServiceException/text()")[0]
        assert validate_with_dtd(xml, "wms/1.1.1/exception_1_1_1.dtd")


class TestWMS110(SysTest):
    config_file = "layer.yaml"

    def setup(self):
        # WMSTest.setup(self)
        self.common_req = WMS110MapRequest(
            url="/service?", param=dict(service="WMS", version="1.1.0")
        )
        self.common_map_req = WMS110MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.0",
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
        self.common_fi_req = WMS110FeatureInfoRequest(
            url="/service?",
            param=dict(
                x="10",
                y="20",
                width="200",
                height="200",
                layers="wms_cache",
                format="image/png",
                query_layers="wms_cache_110",
                styles="",
                bbox="1000,400,2000,1400",
                srs="EPSG:900913",
            ),
        )

    def test_wms_capabilities(self, app):
        req = WMS110CapabilitiesRequest(url="/service?").copy_with_request_params(
            self.common_req
        )
        resp = app.get(req)
        assert resp.content_type == "application/vnd.ogc.wms_xml"
        xml = resp.lxml
        assert (
            xml.xpath(
                "//GetMap//OnlineResource/@xlink:href",
                namespaces=dict(xlink="http://www.w3.org/1999/xlink"),
            )[0] ==
            "http://localhost/service?"
        )

        llbox = xml.xpath("//Capability/Layer/LatLonBoundingBox")[0]
        # some clients don't like 90deg north/south
        assert float(llbox.attrib["miny"]) == pytest.approx(-70.0)
        assert float(llbox.attrib["maxy"]) == pytest.approx(89.999999)
        assert float(llbox.attrib["minx"]) == pytest.approx(-180.0)
        assert float(llbox.attrib["maxx"]) == pytest.approx(180.0)

        layer_names = set(xml.xpath("//Layer/Layer/Name/text()"))
        expected_names = set(
            [
                "direct_fwd_params",
                "direct",
                "wms_cache",
                "wms_cache_100",
                "wms_cache_130",
                "wms_cache_transparent",
                "wms_merge",
                "tms_cache",
                "tms_fi_cache",
                "wms_cache_multi",
                "wms_cache_link_single",
                "wms_cache_110",
                "watermark_cache",
                "wms_managed_cookies_cache",
            ]
        )
        assert layer_names == expected_names
        assert validate_with_dtd(xml, dtd_name="wms/1.1.0/capabilities_1_1_0.dtd")

    def test_invalid_layer(self, app):
        self.common_map_req.params["layers"] = "invalid"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        xml = resp.lxml
        assert xml.xpath("/ServiceExceptionReport/@version")[0] == "1.1.0"
        assert (
            xml.xpath("/ServiceExceptionReport/ServiceException/@code")[0] ==
            "LayerNotDefined"
        )
        assert xml.xpath("//ServiceException/text()")[0] == "unknown layer: invalid"
        assert validate_with_dtd(xml, dtd_name="wms/1.1.0/exception_1_1_0.dtd")

    def test_invalid_format(self, app):
        self.common_map_req.params["format"] = "image/ascii"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        xml = resp.lxml
        assert xml.xpath("/ServiceExceptionReport/@version")[0] == "1.1.0"
        assert (
            xml.xpath("/ServiceExceptionReport/ServiceException/@code")[0] ==
            "InvalidFormat"
        )
        assert (
            xml.xpath("//ServiceException/text()")[0] ==
            "unsupported image format: image/ascii"
        )
        assert validate_with_dtd(xml, dtd_name="wms/1.1.0/exception_1_1_0.dtd")

    def test_invalid_format_img_exception(self, app):
        self.common_map_req.params["format"] = "image/ascii"
        self.common_map_req.params["exceptions"] = "application/vnd.ogc.se_inimage"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        assert is_png(BytesIO(resp.body))

    def test_missing_format_img_exception(self, app):
        del self.common_map_req.params["format"]
        self.common_map_req.params["exceptions"] = "application/vnd.ogc.se_inimage"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        assert is_png(BytesIO(resp.body))

    def test_invalid_srs(self, app):
        self.common_map_req.params["srs"] = "EPSG:1234"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        xml = resp.lxml
        assert xml.xpath("/ServiceExceptionReport/@version")[0] == "1.1.0"
        assert (
            xml.xpath("/ServiceExceptionReport/ServiceException/@code")[0] == "InvalidSRS"
        )
        assert xml.xpath("//ServiceException/text()")[0] == "unsupported srs: EPSG:1234"
        assert validate_with_dtd(xml, dtd_name="wms/1.1.0/exception_1_1_0.dtd")

    def test_get_map_png(self, app, fixture_cache_data):
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        assert Image.open(data).mode == "RGB"

    def test_get_map_jpeg(self, app, fixture_cache_data):
        self.common_map_req.params["format"] = "image/jpeg"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/jpeg"
        assert is_jpeg(BytesIO(resp.body))

    def test_get_map_xml_exception(self, app):
        self.common_map_req.params["bbox"] = "0,0,90,90"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        xml = resp.lxml
        assert xml.xpath("/ServiceExceptionReport/ServiceException/@code") == []
        assert "No response from URL" in xml.xpath("//ServiceException/text()")[0]
        assert validate_with_dtd(xml, "wms/1.1.0/exception_1_1_0.dtd")

    def test_get_map(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=0.0,0.0,20037508.3428,20037508.3428"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params["bbox"] = "0,0,180,90"
                resp = app.get(self.common_map_req)
                assert 35000 < int(resp.headers["Content-length"]) < 75000
                assert resp.content_type == "image/png"

        assert cache_dir.join(
            "wms_cache_EPSG900913/01/000/000/001/000/000/001.jpeg"
        ).check()

    def test_get_map_110(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.0&BBOX=0.0,0.0,20037508.3428,20037508.3428"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params["bbox"] = "0,0,180,90"
                self.common_map_req.params["layers"] = "wms_cache_110"
                resp = app.get(self.common_map_req)
                assert 35000 < int(resp.headers["Content-length"]) < 75000
                assert resp.content_type == "image/png"

        assert cache_dir.join(
            "wms_cache_110_EPSG900913/01/000/000/001/000/000/001.jpeg"
        ).check()

    def test_get_featureinfo(self, app):
        expected_req = (
            {
                "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913"
                "&VERSION=1.1.0&BBOX=1000.0,400.0,2000.0,1400.0&styles="
                "&WIDTH=200&QUERY_LAYERS=foo,bar&X=10&Y=20"
            },
            {"body": b"info", "headers": {"content-type": "text/plain"}},
        )
        with mock_httpd(("localhost", 42423), [expected_req]):
            resp = app.get(self.common_fi_req)
            assert resp.content_type == "text/plain"
            assert resp.body == b"info"

    def test_get_featureinfo_not_queryable(self, app):
        self.common_fi_req.params["query_layers"] = "tms_cache"
        self.common_fi_req.params["exceptions"] = "application/vnd.ogc.se_xml"
        resp = app.get(self.common_fi_req)
        assert resp.content_type == "application/vnd.ogc.se_xml"
        xml = resp.lxml
        assert xml.xpath("/ServiceExceptionReport/ServiceException/@code") == []
        assert "tms_cache is not queryable" in xml.xpath("//ServiceException/text()")[0]
        assert validate_with_dtd(xml, "wms/1.1.0/exception_1_1_0.dtd")

    def test_managed_cookies(self, app):
        def assert_no_cookie(req_handler):
            return 'Cookie' not in req_handler.headers

        def assert_cookie(req_handler):
            assert 'Cookie' in req_handler.headers
            cookie_name, cookie_val = req_handler.headers['Cookie'].split(';')[0].split('=')
            assert cookie_name == 'testcookie'
            assert cookie_val == '42'
            return True

        url = (r"/service?LAYERs=layer1&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913"
                "&VERSION=1.1.1&BBOX=1000.0,400.0,2000.0,1400.0&styles="
                "&WIDTH=200&QUERY_LAYERS=layer1&X=10&Y=20")
        # First response has a Set-Cookie => with managed_cookies=True, mapproxy should send the
        # cookie in the second request
        expected_requests = [
            (
                {'path': url, 'req_assert_function': assert_no_cookie},
                {'body': b'nothing', 'headers': {'Set-Cookie': "testcookie=42"}}
            ),
            (
                {'path': url, 'req_assert_function': assert_cookie},
                {'body': b'nothing'}
            )
        ]
        with mock_httpd(("localhost", 42423), expected_requests):
            self.common_fi_req.params["layers"] = "wms_managed_cookies_cache"
            self.common_fi_req.params["query_layers"] = "wms_managed_cookies_cache"
            resp = app.get(self.common_fi_req)
            assert resp.body == b"nothing"
            resp = app.get(self.common_fi_req)
            assert resp.body == b"nothing"


class TestWMS100(SysTest):
    config_file = "layer.yaml"

    def setup(self):
        self.common_req = WMS100MapRequest(url="/service?", param=dict(wmtver="1.0.0"))
        self.common_map_req = WMS100MapRequest(
            url="/service?",
            param=dict(
                wmtver="1.0.0",
                bbox="-180,0,0,80",
                width="200",
                height="200",
                layers="wms_cache",
                srs="EPSG:4326",
                format="PNG",
                styles="",
                request="GetMap",
            ),
        )
        self.common_fi_req = WMS100FeatureInfoRequest(
            url="/service?",
            param=dict(
                x="10",
                y="20",
                width="200",
                height="200",
                layers="wms_cache_100",
                format="PNG",
                query_layers="wms_cache_100",
                styles="",
                bbox="1000,400,2000,1400",
                srs="EPSG:900913",
            ),
        )

    def test_wms_capabilities(self, app):
        req = WMS100CapabilitiesRequest(url="/service?").copy_with_request_params(
            self.common_req
        )
        resp = app.get(req)
        assert resp.content_type == "text/xml"
        xml = resp.lxml
        assert (
            xml.xpath("/WMT_MS_Capabilities/Service/Title/text()")[0] ==
            u"MapProxy test fixture \u2603"
        )
        layer_names = set(xml.xpath("//Layer/Layer/Name/text()"))
        expected_names = set(
            [
                "direct_fwd_params",
                "direct",
                "wms_cache",
                "wms_cache_100",
                "wms_cache_130",
                "wms_cache_transparent",
                "wms_merge",
                "tms_cache",
                "tms_fi_cache",
                "wms_cache_multi",
                "wms_cache_link_single",
                "wms_cache_110",
                "watermark_cache",
                "wms_managed_cookies_cache",
            ]
        )
        assert layer_names == expected_names
        # TODO srs
        assert validate_with_dtd(xml, dtd_name="wms/1.0.0/capabilities_1_0_0.dtd")

    def test_invalid_layer(self, app):
        self.common_map_req.params["layers"] = "invalid"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "text/xml"
        xml = resp.lxml
        assert xml.xpath("/WMTException/@version")[0] == "1.0.0"
        assert xml.xpath("//WMTException/text()")[0].strip() == "unknown layer: invalid"

    def test_invalid_format(self, app):
        self.common_map_req.params["format"] = "image/ascii"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "text/xml"
        xml = resp.lxml
        assert xml.xpath("/WMTException/@version")[0] == "1.0.0"
        assert (
            xml.xpath("//WMTException/text()")[0].strip() ==
            "unsupported image format: ASCII"
        )

    def test_invalid_format_img_exception(self, app):
        self.common_map_req.params["format"] = "image/ascii"
        self.common_map_req.params["exceptions"] = "INIMAGE"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        assert is_png(BytesIO(resp.body))

    def test_missing_format_img_exception(self, app):
        del self.common_map_req.params["format"]
        self.common_map_req.params["exceptions"] = "INIMAGE"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        assert is_png(BytesIO(resp.body))

    def test_invalid_srs(self, app):
        self.common_map_req.params["srs"] = "EPSG:1234"
        print(self.common_map_req.complete_url)
        resp = app.get(self.common_map_req.complete_url)
        xml = resp.lxml
        assert xml.xpath("//WMTException/text()")[0].strip() == "unsupported srs: EPSG:1234"

    def test_get_map_png(self, app, fixture_cache_data):
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        assert Image.open(data).mode == "RGB"

    def test_get_map_png_transparent_paletted(
        self, app, base_config, fixture_cache_data
    ):
        try:
            base_config.image.paletted = True
            self.common_map_req.params["transparent"] = "True"
            resp = app.get(self.common_map_req)
            assert resp.content_type == "image/png"
            data = BytesIO(resp.body)
            assert is_png(data)
            assert Image.open(data).mode == "P"
        finally:
            base_config.image.paletted = False

    def test_get_map_jpeg(self, app, fixture_cache_data):
        self.common_map_req.params["format"] = "image/jpeg"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/jpeg"
        assert is_jpeg(BytesIO(resp.body))

    def test_get_map_xml_exception(self, app):
        self.common_map_req.params["bbox"] = "0,0,90,90"
        resp = app.get(self.common_map_req)
        xml = resp.lxml
        assert "No response from URL" in xml.xpath("//WMTException/text()")[0]

    def test_get_map(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=0.0,0.0,20037508.3428,20037508.3428"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params["bbox"] = "0,0,180,90"
                resp = app.get(self.common_map_req)
                assert resp.content_type == "image/png"
        assert cache_dir.join(
            "wms_cache_EPSG900913/01/000/000/001/000/000/001.jpeg"
        ).check()

    def test_get_featureinfo(self, app):
        expected_req = (
            {
                "path": r"/service?LAYERs=foo,bar&FORMAT=image%2FPNG"  # TODO should be PNG only
                "&REQUEST=feature_info&HEIGHT=200&SRS=EPSG%3A900913"
                "&WMTVER=1.0.0&BBOX=1000.0,400.0,2000.0,1400.0&styles="
                "&WIDTH=200&QUERY_LAYERS=foo,bar&X=10&Y=20"
            },
            {"body": b"info", "headers": {"content-type": "text/plain"}},
        )
        with mock_httpd(("localhost", 42423), [expected_req]):
            resp = app.get(self.common_fi_req)
            assert resp.content_type == "text/plain"
            assert resp.body == b"info"

    def test_get_featureinfo_not_queryable(self, app):
        self.common_fi_req.params["query_layers"] = "tms_cache"
        self.common_fi_req.params["exceptions"] = "application/vnd.ogc.se_xml"
        resp = app.get(self.common_fi_req)
        assert resp.content_type == "text/xml"
        xml = resp.lxml
        assert "tms_cache is not queryable" in xml.xpath("//WMTException/text()")[0]


ns130 = {
    "wms": "http://www.opengis.net/wms",
    "ogc": "http://www.opengis.net/ogc",
    "sld": "http://www.opengis.net/sld",
    "xlink": "http://www.w3.org/1999/xlink",
}


def assert_xpath(xml, xpath, expected, namespaces=None):
    assert xml.xpath(xpath, namespaces=namespaces)[0] == expected


assert_xpath_wms130 = functools.partial(assert_xpath, namespaces=ns130)


class TestWMS130(SysTest):
    config_file = "layer.yaml"

    def setup(self):
        self.common_req = WMS130MapRequest(
            url="/service?", param=dict(service="WMS", version="1.3.0")
        )
        self.common_map_req = WMS130MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.3.0",
                bbox="0,-180,80,0",
                width="200",
                height="200",
                layers="wms_cache",
                crs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
            ),
        )
        self.common_fi_req = WMS130FeatureInfoRequest(
            url="/service?",
            param=dict(
                i="10",
                j="20",
                width="200",
                height="200",
                layers="wms_cache_130",
                format="image/png",
                query_layers="wms_cache_130",
                styles="",
                bbox="1000,400,2000,1400",
                crs="EPSG:900913",
            ),
        )

    def test_wms_capabilities(self, app):
        req = WMS130CapabilitiesRequest(url="/service?").copy_with_request_params(
            self.common_req
        )
        resp = app.get(req)
        assert resp.content_type == "text/xml"
        xml = resp.lxml
        assert_xpath_wms130(
            xml,
            "/wms:WMS_Capabilities/wms:Service/wms:Title/text()",
            u"MapProxy test fixture \u2603",
        )

        # test for extended layer metadata
        assert_xpath_wms130(
            xml,
            "/wms:WMS_Capabilities/wms:Capability/wms:Layer/wms:Layer/wms:Attribution/wms:Title/text()",
            u"My attribution title",
        )

        layer_names = set(
            xml.xpath("//wms:Layer/wms:Layer/wms:Name/text()", namespaces=ns130)
        )
        expected_names = set(
            [
                "direct_fwd_params",
                "direct",
                "wms_cache",
                "wms_cache_100",
                "wms_cache_130",
                "wms_cache_transparent",
                "wms_merge",
                "tms_cache",
                "tms_fi_cache",
                "wms_cache_multi",
                "wms_cache_link_single",
                "wms_cache_110",
                "watermark_cache",
                "wms_managed_cookies_cache",
            ]
        )
        assert layer_names == expected_names
        assert is_130_capa(xml)

    def test_invalid_layer(self, app):
        self.common_map_req.params["layers"] = "invalid"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "text/xml"
        xml = resp.lxml
        assert_xpath_wms130(xml, "/ogc:ServiceExceptionReport/@version", "1.3.0")
        assert_xpath_wms130(
            xml,
            "/ogc:ServiceExceptionReport/ogc:ServiceException/@code",
            "LayerNotDefined",
        )
        assert_xpath_wms130(xml, "//ogc:ServiceException/text()", "unknown layer: invalid")
        assert validate_with_xsd(xml, xsd_name="wms/1.3.0/exceptions_1_3_0.xsd")

    def test_invalid_format(self, app):
        self.common_map_req.params["format"] = "image/ascii"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "text/xml"
        xml = resp.lxml
        assert_xpath_wms130(xml, "/ogc:ServiceExceptionReport/@version", "1.3.0")
        assert_xpath_wms130(
            xml,
            "/ogc:ServiceExceptionReport/ogc:ServiceException/@code",
            "InvalidFormat",
        )
        assert_xpath_wms130(
            xml,
            "//ogc:ServiceException/text()",
            "unsupported image format: image/ascii",
        )
        assert validate_with_xsd(xml, xsd_name="wms/1.3.0/exceptions_1_3_0.xsd")

    def test_invalid_format_img_exception(self, app):
        self.common_map_req.params["format"] = "image/ascii"
        self.common_map_req.params["exceptions"] = "application/vnd.ogc.se_inimage"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        assert is_png(BytesIO(resp.body))

    def test_missing_format_img_exception(self, app):
        del self.common_map_req.params["format"]
        self.common_map_req.params["exceptions"] = "application/vnd.ogc.se_inimage"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        assert is_png(BytesIO(resp.body))

    def test_invalid_srs(self, app):
        self.common_map_req.params["srs"] = "EPSG:1234"
        self.common_map_req.params["exceptions"] = "text/xml"

        resp = app.get(self.common_map_req)
        assert resp.content_type == "text/xml"
        xml = resp.lxml
        assert_xpath_wms130(
            xml, "/ogc:ServiceExceptionReport/ogc:ServiceException/@code", "InvalidCRS"
        )
        assert_xpath_wms130(
            xml, "//ogc:ServiceException/text()", "unsupported crs: EPSG:1234"
        )
        assert validate_with_xsd(xml, xsd_name="wms/1.3.0/exceptions_1_3_0.xsd")

    def test_get_map_png(self, app, fixture_cache_data):
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        assert Image.open(data).mode == "RGB"

    def test_get_map_jpeg(self, app, fixture_cache_data):
        self.common_map_req.params["format"] = "image/jpeg"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/jpeg"
        assert is_jpeg(BytesIO(resp.body))

    def test_get_map_xml_exception(self, app):
        self.common_map_req.params["bbox"] = "0,0,90,90"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "text/xml"
        xml = resp.lxml
        assert (
            xml.xpath(
                "/ogc:ServiceExceptionReport/ogc:ServiceException/@code",
                namespaces=ns130,
            ) ==
            []
        )
        assert (
            "No response from URL"
            in xml.xpath("//ogc:ServiceException/text()", namespaces=ns130)[0]
        )
        assert validate_with_xsd(xml, xsd_name="wms/1.3.0/exceptions_1_3_0.xsd")

    def test_get_map(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=0.0,0.0,20037508.3428,20037508.3428"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params["bbox"] = "0,0,180,90"  # internal axis-order
                resp = app.get(self.common_map_req)
                assert resp.content_type == "image/png"

        assert cache_dir.join(
            "wms_cache_EPSG900913/01/000/000/001/000/000/001.jpeg"
        ).check()

    def test_get_featureinfo(self, app):
        expected_req = (
            {
                "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetFeatureInfo&HEIGHT=200&CRS=EPSG%3A900913"
                "&VERSION=1.3.0&BBOX=1000.0,400.0,2000.0,1400.0&styles="
                "&WIDTH=200&QUERY_LAYERS=foo,bar&I=10&J=20"
            },
            {"body": b"info", "headers": {"content-type": "text/plain"}},
        )
        with mock_httpd(("localhost", 42423), [expected_req]):
            resp = app.get(self.common_fi_req)
            assert resp.content_type == "text/plain"
            assert resp.body == b"info"

    def test_get_featureinfo_111(self, app):
        expected_req = (
            {
                "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913"
                "&VERSION=1.1.1&BBOX=1000.0,400.0,2000.0,1400.0&styles="
                "&WIDTH=200&QUERY_LAYERS=foo,bar&X=10&Y=20"
            },
            {"body": b"info", "headers": {"content-type": "text/plain"}},
        )
        with mock_httpd(("localhost", 42423), [expected_req]):
            self.common_fi_req.params["layers"] = "wms_cache"
            self.common_fi_req.params["query_layers"] = "wms_cache"
            resp = app.get(self.common_fi_req)
            assert resp.content_type == "text/plain"
            assert resp.body == b"info"


@pytest.mark.skipif(sys.platform == "win32", reason="not supported on Windows")
class TestWMSLinkSingleColorImages(SysTest):
    config_file = "layer.yaml"

    def setup(self):
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-180,0,0,80",
                width="200",
                height="200",
                layers="wms_cache_link_single",
                srs="EPSG:4326",
                format="image/jpeg",
                styles="",
                request="GetMap",
            ),
        )

    def test_get_map(self, app, cache_dir):
        link_name = "wms_cache_link_single_EPSG900913/01/000/000/001/000/000/001.png"
        real_name = "wms_cache_link_single_EPSG900913/single_color_tiles/fe00a0.png"
        with tmp_image((256, 256), format="jpeg", color="#fe00a0") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=0.0,0.0,20037508.3428,20037508.3428"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params["bbox"] = "0,0,180,90"
                resp = app.get(self.common_map_req)
                assert resp.content_type == "image/jpeg"

            single_loc = cache_dir.join(real_name)
            tile_loc = cache_dir.join(link_name)
            assert single_loc.check()
            assert tile_loc.check(link=True)

            self.common_map_req.params["format"] = "image/png"
            resp = app.get(self.common_map_req)
            assert resp.content_type == "image/png"


def assert_almost_equal_bbox(bbox1, bbox2, rel=0.01):
    assert bbox1 == pytest.approx(bbox2, rel=rel)


def is_100_capa(xml):
    return validate_with_dtd(xml, dtd_name="wms/1.0.0/capabilities_1_0_0.dtd")


def is_110_capa(xml):
    return validate_with_dtd(xml, dtd_name="wms/1.1.0/capabilities_1_1_0.dtd")


def is_111_exception(xml, msg=None, code=None, re_msg=None):
    assert xml.xpath("/ServiceExceptionReport/@version")[0] == "1.1.1"
    if msg:
        assert xml.xpath("//ServiceException/text()")[0] == msg
    if re_msg:
        exception_msg = xml.xpath("//ServiceException/text()")[0]
        assert re.findall(re_msg, exception_msg, re.I), "'%r' does not match '%s'" % (
            re_msg,
            exception_msg,
        )
    if code is not None:
        assert xml.xpath("/ServiceExceptionReport/ServiceException/@code")[0] == code
    assert validate_with_dtd(xml, "wms/1.1.1/exception_1_1_1.dtd")


def is_111_capa(xml):
    return validate_with_dtd(xml, dtd_name="wms/1.1.1/WMS_MS_Capabilities.dtd")


def is_130_capa(xml):
    return validate_with_xsd(xml, xsd_name="wms/1.3.0/capabilities_1_3_0.xsd")
