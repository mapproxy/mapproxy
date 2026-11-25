import pytest

from mapproxy.test.http import mock_httpd
from mapproxy.test.image import (
    create_tmp_image,
    img_from_buf,
    is_png,
    is_transparent,
    tmp_image,
)
from mapproxy.test.system import SysTest
from mapproxy.test.system.test_wms import is_130_capa, ns130

TESTSERVER = ("localhost", 42423)


def upstream_map(layer, bbox, size, srs, img):
    return (
        {
            "path": "/service?LAYERS=%s&SERVICE=WMS&FORMAT=image%%2Fpng&REQUEST=GetMap"
            "&HEIGHT=%d&SRS=%s&STYLES=&VERSION=1.1.1&BBOX=%s&WIDTH=%d"
            % (
                layer,
                size[1],
                srs.replace(":", "%3A"),
                ",".join(str(v) for v in bbox),
                size[0],
            )
        },
        {"body": img, "headers": {"content-type": "image/png"}},
    )


def map_params(layers, bbox, size=(100, 100), srs="EPSG:3857"):
    return (
        "/service?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&STYLES=&FORMAT=image/png"
        "&TRANSPARENT=true&LAYERS=%s&SRS=%s&BBOX=%s&WIDTH=%d&HEIGHT=%d"
        % (layers, srs, ",".join(str(v) for v in bbox), size[0], size[1])
    )


def ogc_scale(res):
    return res / 0.00028


class LayerLimitHelpers(SysTest):
    def capabilities(self, app):
        resp = app.get("/service?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities")
        xml = resp.lxml
        assert is_130_capa(xml)
        return xml

    def layer(self, xml, name):
        found = xml.xpath("//wms:Layer[wms:Name='%s']" % name, namespaces=ns130)
        assert len(found) == 1, name
        return found[0]

    def scales(self, layer):
        min_scale = layer.xpath("wms:MinScaleDenominator/text()", namespaces=ns130)
        max_scale = layer.xpath("wms:MaxScaleDenominator/text()", namespaces=ns130)
        return (
            float(min_scale[0]) if min_scale else None,
            float(max_scale[0]) if max_scale else None,
        )

    def dimensions(self, layer):
        return {
            d.attrib["name"]: (d.text.split(","), d.attrib["default"])
            for d in layer.xpath("wms:Dimension", namespaces=ns130)
        }

    def geo_bbox(self, layer):
        box = layer.xpath("wms:EX_GeographicBoundingBox", namespaces=ns130)[0]
        return tuple(
            float(box.xpath("wms:%s/text()" % tag, namespaces=ns130)[0])
            for tag in (
                "westBoundLongitude",
                "southBoundLatitude",
                "eastBoundLongitude",
                "northBoundLatitude",
            )
        )

    def red_tile_request(self, layer):
        red = create_tmp_image((256, 256), format="png", color=(255, 0, 0))
        return (
            {
                "path": "/service?LAYERS=%s&SERVICE=WMS&FORMAT=image%%2Fpng"
                "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%%3A3857&styles="
                "&VERSION=1.1.1&WIDTH=256"
                "&BBOX=-18785164.0714,19411336.2071,-18472078.0035,19724422.2749"
                % layer
            },
            {"body": red, "headers": {"content-type": "image/png"}},
        )

    def assert_red(self, body):
        assert img_from_buf(body).convert("RGBA").getpixel((128, 128)) == (
            255,
            0,
            0,
            255,
        )

    def wmts_layer(self, app, name):
        xml = app.get("/wmts/1.0.0/WMTSCapabilities.xml").lxml
        ns = {
            "wmts": "http://www.opengis.net/wmts/1.0",
            "ows": "http://www.opengis.net/ows/1.1",
        }
        return xml.xpath("//wmts:Layer[ows:Identifier='%s']" % name, namespaces=ns)[
            0
        ], ns


class TestInheritedScaleAndDimensions(LayerLimitHelpers):
    @pytest.fixture(scope="class")
    def config_file(self):
        return "layer_limits.yaml"

    def test_layer_tree_omits_layers_outside_scale(self, app):
        xml = self.capabilities(app)
        assert "coarse" not in xml.xpath(
            "//wms:Layer/wms:Name/text()", namespaces=ns130
        )
        basemap = self.layer(xml, "basemap")
        assert basemap.xpath("wms:Layer/wms:Name/text()", namespaces=ns130) == [
            "roads",
            "rails",
            "details",
            "roads_tiles",
        ]

    def test_scale_limits_flow_down(self, app):
        xml = self.capabilities(app)
        for name, expected in [
            ("basemap", (ogc_scale(10), ogc_scale(1000))),
            ("roads", (ogc_scale(10), ogc_scale(1000))),
            ("rails", (ogc_scale(100), ogc_scale(1000))),
            ("details", (ogc_scale(10), ogc_scale(500))),
            ("poi", (ogc_scale(10), ogc_scale(500))),
        ]:
            min_scale, max_scale = self.scales(self.layer(xml, name))
            assert min_scale == pytest.approx(expected[0]), name
            assert max_scale == pytest.approx(expected[1]), name

    def test_dimensions_flow_down(self, app):
        xml = self.capabilities(app)
        inherited = {"time": (["2020", "2021"], "2021")}
        assert self.dimensions(self.layer(xml, "basemap")) == inherited
        assert self.dimensions(self.layer(xml, "roads")) == inherited
        assert self.dimensions(self.layer(xml, "details")) == inherited
        assert self.dimensions(self.layer(xml, "poi")) == inherited
        assert self.dimensions(self.layer(xml, "rails")) == {
            "time": (["2019", "2020"], "2019"),
            "reference_time": (["2018", "2019"], "2018"),
        }
        layer, ns = self.wmts_layer(app, "roads_tiles")
        assert layer.xpath("wmts:Dimension", namespaces=ns) == []

    def test_group_renders_children_inside_their_limits(self, app):
        bbox = (0, 0, 50000, 50000)
        with tmp_image((100, 100), format="png") as img:
            img = img.read()
            expected = [
                upstream_map("roads,rails,poi", bbox, (100, 100), "EPSG:3857", img)
            ]
            with mock_httpd(TESTSERVER, expected, bbox_aware_query_comparator=True):
                resp = app.get(map_params("basemap", bbox))
                assert is_png(resp.body)

    def test_group_skips_children_outside_their_limits(self, app):
        bbox = (0, 0, 5000, 5000)
        with tmp_image((100, 100), format="png") as img:
            img = img.read()
            expected = [upstream_map("roads,poi", bbox, (100, 100), "EPSG:3857", img)]
            with mock_httpd(TESTSERVER, expected, bbox_aware_query_comparator=True):
                resp = app.get(map_params("basemap", bbox))
                assert is_png(resp.body)

    def test_inherited_limit_hides_child(self, app):
        with mock_httpd(TESTSERVER, [], bbox_aware_query_comparator=True):
            resp = app.get(map_params("roads", (0, 0, 200000, 200000)))
            assert is_png(resp.body)
            assert is_transparent(resp.body)
            resp = app.get(map_params("basemap", (0, 0, 200000, 200000)))
            assert is_transparent(resp.body)
            resp = app.get(map_params("rails", (0, 0, 5000, 5000)))
            assert is_transparent(resp.body)
            resp = app.get(map_params("poi", (0, 0, 70000, 70000)))
            assert is_transparent(resp.body)

    def test_omitted_layer_is_unknown(self, app):
        resp = app.get(
            map_params("coarse", (0, 0, 1000000, 1000000)), expect_errors=True
        )
        assert b"LayerNotDefined" in resp.body

    def test_tile_scale_limit(self, app):
        with mock_httpd(TESTSERVER, [], bbox_aware_query_comparator=True):
            resp = app.get("/tms/1.0.0/tiled/GLOBAL_WEBMERCATOR/7/4/254.png")
            assert is_transparent(resp.body)
        with mock_httpd(
            TESTSERVER,
            [self.red_tile_request("tiled")],
            bbox_aware_query_comparator=True,
        ):
            resp = app.get("/tms/1.0.0/tiled/GLOBAL_WEBMERCATOR/6/4/126.png")
            self.assert_red(resp.body)


class TestInheritedCoverage(LayerLimitHelpers):
    @pytest.fixture(scope="class")
    def config_file(self):
        return "layer_limits_area.yaml"

    def test_layer_tree_omits_layers_outside_coverage(self, app):
        xml = self.capabilities(app)
        assert "far" not in xml.xpath("//wms:Layer/wms:Name/text()", namespaces=ns130)
        region = self.layer(xml, "region")
        assert region.xpath("wms:Layer/wms:Name/text()", namespaces=ns130) == [
            "lakes",
            "rivers",
        ]

    def test_coverages_intersect_down(self, app):
        xml = self.capabilities(app)
        assert self.geo_bbox(self.layer(xml, "region")) == pytest.approx((0, 0, 20, 20))
        assert self.geo_bbox(self.layer(xml, "lakes")) == pytest.approx(
            (10, 10, 20, 20)
        )
        assert self.geo_bbox(self.layer(xml, "rivers")) == pytest.approx((0, 0, 20, 20))

    def test_group_renders_children_inside_their_coverage(self, app):
        with tmp_image((100, 100), format="png") as img:
            img = img.read()
            bbox = (12, 12, 18, 18)
            expected = [
                upstream_map("lakes,rivers", bbox, (100, 100), "EPSG:4326", img)
            ]
            with mock_httpd(TESTSERVER, expected, bbox_aware_query_comparator=True):
                app.get(map_params("region", bbox, srs="EPSG:4326"))
            bbox = (2, 2, 8, 8)
            expected = [upstream_map("rivers", bbox, (100, 100), "EPSG:4326", img)]
            with mock_httpd(TESTSERVER, expected, bbox_aware_query_comparator=True):
                app.get(map_params("region", bbox, srs="EPSG:4326"))
        with mock_httpd(TESTSERVER, [], bbox_aware_query_comparator=True):
            resp = app.get(map_params("region", (25, 25, 35, 35), srs="EPSG:4326"))
            assert is_transparent(resp.body)
            resp = app.get(map_params("lakes", (2, 2, 8, 8), srs="EPSG:4326"))
            assert is_transparent(resp.body)

    def test_featureinfo_outside_coverage(self, app):
        req = (
            "/service?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetFeatureInfo&STYLES=&FORMAT=image/png"
            "&LAYERS=lakes&QUERY_LAYERS=lakes&SRS=EPSG:4326&BBOX=%s&WIDTH=100&HEIGHT=100"
            "&X=50&Y=50&INFO_FORMAT=text/plain"
        )
        with mock_httpd(TESTSERVER, [], bbox_aware_query_comparator=True):
            resp = app.get(req % "2,2,8,8")
            assert resp.body == b""
        expected = (
            {
                "path": "/service?LAYERs=lakes&SERVICE=WMS&FORMAT=image%2Fpng"
                "&REQUEST=GetFeatureInfo&HEIGHT=100&SRS=EPSG%3A4326&styles="
                "&VERSION=1.1.1&BBOX=12.0,12.0,18.0,18.0&WIDTH=100"
                "&QUERY_LAYERS=lakes&X=50&Y=50&info_format=text/plain"
            },
            {"body": b"lake info", "headers": {"content-type": "text/plain"}},
        )
        with mock_httpd(TESTSERVER, [expected], bbox_aware_query_comparator=True):
            resp = app.get(req % "12,12,18,18")
            assert resp.body == b"lake info"

    def test_omitted_layer_is_unknown(self, app):
        resp = app.get(
            map_params("far", (100, 50, 120, 60), srs="EPSG:4326"), expect_errors=True
        )
        assert b"LayerNotDefined" in resp.body

    def test_tiles_outside_coverage_are_empty(self, app):
        with mock_httpd(TESTSERVER, [], bbox_aware_query_comparator=True):
            resp = app.get("/tms/1.0.0/north/GLOBAL_WEBMERCATOR/6/4/1.png")
            assert is_transparent(resp.body)
        with mock_httpd(
            TESTSERVER,
            [self.red_tile_request("north")],
            bbox_aware_query_comparator=True,
        ):
            resp = app.get("/tms/1.0.0/north/GLOBAL_WEBMERCATOR/6/4/126.png")
            self.assert_red(resp.body)

    def test_tile_capabilities_use_coverage(self, app):
        layer, ns = self.wmts_layer(app, "north")
        lower = layer.xpath(
            "ows:WGS84BoundingBox/ows:LowerCorner/text()", namespaces=ns
        )[0]
        upper = layer.xpath(
            "ows:WGS84BoundingBox/ows:UpperCorner/text()", namespaces=ns
        )[0]
        assert [float(v) for v in lower.split()] == pytest.approx([-180, 0], abs=1e-6)
        assert [float(v) for v in upper.split()] == pytest.approx(
            [180, 85.0511287798], abs=1e-6
        )
