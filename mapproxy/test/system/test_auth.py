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

from __future__ import division

import pytest

from mapproxy.srs import bbox_equals
from mapproxy.util.geom import geom_support

from mapproxy.test.http import MockServ
from mapproxy.test.image import img_from_buf, create_tmp_image, is_transparent
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "auth.yaml"


TESTSERVER_ADDRESS = "localhost", 42423
CAPABILITIES_REQ = "/service?request=GetCapabilities&service=WMS&Version=1.1.1"
MAP_REQ = (
    "/service?request=GetMap&service=WMS&Version=1.1.1&SRS=EPSG:4326"
    "&BBOX=-80,-40,0,0&WIDTH=200&HEIGHT=100&styles=&FORMAT=image/png&"
)
FI_REQ = (
    "/service?request=GetFeatureInfo&service=WMS&Version=1.1.1&SRS=EPSG:4326"
    "&BBOX=-80,-40,0,0&WIDTH=200&HEIGHT=100&styles=&FORMAT=image/png&X=10&Y=10&"
)


pytestmark = pytest.mark.skipif(not geom_support, reason="Shapely required")


class TestWMSAuth(SysTest):

    # ###
    # see mapproxy.test.unit.test_auth for WMS GetMap request tests
    # ###
    def test_capabilities_authorize_all(self, app):

        def auth(service, layers, **kw):
            assert service == "wms.capabilities"
            assert len(layers) == 8
            return {"authorized": "full"}

        resp = app.get(CAPABILITIES_REQ, extra_environ={"mapproxy.authorize": auth})
        xml = resp.lxml
        assert xml.xpath("//Layer/Name/text()") == [
            "layer1",
            "layer1a",
            "layer1b",
            "layer2",
            "layer2a",
            "layer2b",
            "layer2b1",
            "layer3",
        ]

    def test_capabilities_authorize_none(self, app):

        def auth(service, layers, **kw):
            assert service == "wms.capabilities"
            assert len(layers) == 8
            return {"authorized": "none"}

        app.get(
            CAPABILITIES_REQ, extra_environ={"mapproxy.authorize": auth}, status=403
        )

    def test_capabilities_unauthenticated(self, app):

        def auth(service, layers, **kw):
            assert service == "wms.capabilities"
            assert len(layers) == 8
            return {"authorized": "unauthenticated"}

        app.get(
            CAPABILITIES_REQ, extra_environ={"mapproxy.authorize": auth}, status=401
        )

    def test_capabilities_authorize_partial(self, app):

        def auth(service, layers, **kw):
            assert service == "wms.capabilities"
            assert len(layers) == 8
            return {
                "authorized": "partial",
                "layers": {
                    "layer1a": {"map": True},
                    "layer2": {"map": True},
                    "layer2b": {"map": True},
                    "layer2b1": {"map": True},
                },
            }

        resp = app.get(CAPABILITIES_REQ, extra_environ={"mapproxy.authorize": auth})
        xml = resp.lxml
        # layer1a not included cause root layer (layer1) is not permitted
        assert xml.xpath("//Layer/Name/text()") == ["layer2", "layer2b", "layer2b1"]

    def test_capabilities_authorize_partial_limited_to(self, app):

        def auth(service, layers, **kw):
            assert service == "wms.capabilities"
            assert len(layers) == 8
            return {
                "authorized": "partial",
                "layers": {
                    "layer1a": {"map": True},
                    "layer2": {
                        "map": True,
                        "limited_to": {
                            "srs": "EPSG:4326",
                            "geometry": [-40.0, -50.0, 0.0, 5.0],
                        },
                    },
                    "layer2b": {"map": True},
                    "layer2b1": {"map": True},
                },
            }

        resp = app.get(CAPABILITIES_REQ, extra_environ={"mapproxy.authorize": auth})
        xml = resp.lxml
        # layer1a not included cause root layer (layer1) is not permitted
        assert xml.xpath("//Layer/Name/text()") == ["layer2", "layer2b", "layer2b1"]
        limited_bbox = xml.xpath("//Layer/LatLonBoundingBox")[1]
        assert float(limited_bbox.attrib["minx"]) == -40.0
        assert float(limited_bbox.attrib["miny"]) == -50.0
        assert float(limited_bbox.attrib["maxx"]) == 0.0
        assert float(limited_bbox.attrib["maxy"]) == 5.0

    def test_capabilities_authorize_partial_global_limited(self, app):

        def auth(service, layers, **kw):
            assert service == "wms.capabilities"
            assert len(layers) == 8
            return {
                "authorized": "partial",
                "limited_to": {
                    "srs": "EPSG:4326",
                    "geometry": [171.0, -50.0, 178.0, 5.0],
                },
                "layers": {
                    "layer1": {"map": True},
                    "layer1a": {"map": True},
                    "layer2": {"map": True},
                    "layer2b": {"map": True},
                    "layer2b1": {"map": True},
                },
            }

        resp = app.get(CAPABILITIES_REQ, extra_environ={"mapproxy.authorize": auth})
        xml = resp.lxml
        # print resp.body
        # layer2/2b/2b1 not included because coverage of 2b1 is outside of global limited_to
        assert xml.xpath("//Layer/Name/text()") == ["layer1", "layer1a"]
        limited_bbox = xml.xpath("//Layer/LatLonBoundingBox")[1]
        assert float(limited_bbox.attrib["minx"]) == 171.0
        assert float(limited_bbox.attrib["miny"]) == -50.0
        assert float(limited_bbox.attrib["maxx"]) == 178.0
        assert float(limited_bbox.attrib["maxy"]) == 5.0

    def test_capabilities_authorize_partial_with_fi(self, app):

        def auth(service, layers, **kw):
            assert service == "wms.capabilities"
            assert len(layers) == 8
            return {
                "authorized": "partial",
                "layers": {
                    "layer1": {"map": True},
                    "layer1a": {"map": True},
                    "layer2": {"map": True, "featureinfo": True},
                    "layer2b": {"map": True, "featureinfo": True},
                    "layer2b1": {"map": True, "featureinfo": True},
                },
            }

        resp = app.get(CAPABILITIES_REQ, extra_environ={"mapproxy.authorize": auth})
        xml = resp.lxml
        assert xml.xpath("//Layer/Name/text()") == [
            "layer1",
            "layer1a",
            "layer2",
            "layer2b",
            "layer2b1",
        ]
        layers = xml.xpath("//Layer")
        assert layers[3][0].text == "layer2"
        assert layers[3].attrib["queryable"] == "1"
        assert layers[4][0].text == "layer2b"
        assert layers[4].attrib["queryable"] == "1"
        assert layers[5][0].text == "layer2b1"
        assert layers[5].attrib["queryable"] == "1"

    def test_get_map_authorized(self, app):

        def auth(service, layers, query_extent, **kw):
            assert query_extent == ("EPSG:4326", (-80.0, -40.0, 0.0, 0.0))
            assert service == "wms.map"
            assert len(layers) == 1
            return {"authorized": "partial", "layers": {"layer1": {"map": True}}}

        resp = app.get(
            MAP_REQ + "layers=layer1", extra_environ={"mapproxy.authorize": auth}
        )
        assert resp.content_type == "image/png"

    def test_get_map_authorized_limited(self, app):

        def auth(service, layers, query_extent, **kw):
            assert query_extent == ("EPSG:4326", (-80.0, -40.0, 0.0, 0.0))
            assert service == "wms.map"
            assert len(layers) == 1
            return {
                "authorized": "partial",
                "layers": {
                    "layer1": {
                        "map": True,
                        "limited_to": {
                            "srs": "EPSG:4326",
                            "geometry": [-40.0, -40.0, 0.0, 0.0],
                        },
                    }
                },
            }

        resp = app.get(
            MAP_REQ + "layers=layer1", extra_environ={"mapproxy.authorize": auth}
        )
        assert resp.content_type == "image/png"
        img = img_from_buf(resp.body)
        # left part not authorized, only bgcolor
        assert len(img.crop((0, 0, 100, 100)).getcolors()) == 1
        # right part authorized, bgcolor + text
        assert len(img.crop((100, 0, 200, 100)).getcolors()) >= 2

    def test_get_map_authorized_global_limited(self, app):

        def auth(service, layers, query_extent, **kw):
            assert query_extent == ("EPSG:4326", (-80.0, -40.0, 0.0, 0.0))
            assert service == "wms.map"
            assert len(layers) == 1
            return {
                "authorized": "partial",
                "limited_to": {
                    "srs": "EPSG:4326",
                    "geometry": [-20.0, -40.0, 0.0, 0.0],
                },
                "layers": {
                    "layer1": {
                        "map": True,
                        "limited_to": {
                            "srs": "EPSG:4326",
                            "geometry": [-40.0, -40.0, 0.0, 0.0],
                        },
                    }
                },
            }

        resp = app.get(
            MAP_REQ + "layers=layer1", extra_environ={"mapproxy.authorize": auth}
        )
        assert resp.content_type == "image/png"
        img = img_from_buf(resp.body)
        # left part not authorized, only bgcolor
        assert len(img.crop((0, 0, 100, 100)).getcolors()) == 1
        # right part authorized, bgcolor + text
        assert len(img.crop((100, 0, 200, 100)).getcolors()) >= 2

    def test_get_map_authorized_none(self, app):

        def auth(service, layers, query_extent, **kw):
            assert query_extent == ("EPSG:4326", (-80.0, -40.0, 0.0, 0.0))
            assert service == "wms.map"
            assert len(layers) == 1
            return {"authorized": "partial", "layers": {"layer1": {"map": False}}}

        app.get(
            MAP_REQ + "layers=layer1",
            extra_environ={"mapproxy.authorize": auth},
            status=403,
        )

    def test_get_featureinfo_limited_to_inside(self, app):

        def auth(service, layers, query_extent, **kw):
            assert query_extent == ("EPSG:4326", (-80.0, -40.0, 0.0, 0.0))
            assert service == "wms.featureinfo"
            assert len(layers) == 1
            return {
                "authorized": "partial",
                "layers": {
                    "layer1b": {
                        "featureinfo": True,
                        "limited_to": {
                            "srs": "EPSG:4326",
                            "geometry": [-80.0, -40.0, 0.0, 0.0],
                        },
                    }
                },
            }

        serv = MockServ(port=42423)
        serv.expects(
            "/service?request=GetFeatureInfo&service=WMS&Version=1.1.1&SRS=EPSG:4326"
            "&BBOX=-80.0,-40.0,0.0,0.0&WIDTH=200&HEIGHT=100&styles=&FORMAT=image/png&X=10&Y=10"
            "&query_layers=fi&layers=fi"
        )
        serv.returns(b"infoinfo")
        with serv:
            resp = app.get(
                FI_REQ + "query_layers=layer1b&layers=layer1b",
                extra_environ={"mapproxy.authorize": auth},
            )
            assert resp.body == b"infoinfo"

    def test_get_featureinfo_limited_to_outside(self, app):

        def auth(service, layers, query_extent, **kw):
            assert query_extent == ("EPSG:4326", (-80.0, -40.0, 0.0, 0.0))
            assert service == "wms.featureinfo"
            assert len(layers) == 1
            return {
                "authorized": "partial",
                "layers": {
                    "layer1b": {
                        "featureinfo": True,
                        "limited_to": {
                            "srs": "EPSG:4326",
                            "geometry": [-80.0, -40.0, 0.0, -10.0],
                        },
                    }
                },
            }

        resp = app.get(
            FI_REQ + "query_layers=layer1b&layers=layer1b",
            extra_environ={"mapproxy.authorize": auth},
        )
        # empty response, FI request is outside of limited_to geometry
        assert resp.body == b""

    def test_get_featureinfo_global_limited(self, app):

        def auth(service, layers, query_extent, **kw):
            assert query_extent == ("EPSG:4326", (-80.0, -40.0, 0.0, 0.0))
            assert service == "wms.featureinfo"
            assert len(layers) == 1
            return {
                "authorized": "partial",
                "limited_to": {
                    "srs": "EPSG:4326",
                    "geometry": [-40.0, -40.0, 0.0, 0.0],
                },
                "layers": {"layer1b": {"featureinfo": True}},
            }

        resp = app.get(
            FI_REQ + "query_layers=layer1b&layers=layer1b",
            extra_environ={"mapproxy.authorize": auth},
        )
        # empty response, FI request is outside of limited_to geometry
        assert resp.body == b""


TMS_CAPABILITIES_REQ = "/tms/1.0.0"


class TestTMSAuth(SysTest):

    def test_capabilities_authorize_all(self, app):

        def auth(service, layers, environ, **kw):
            assert environ["PATH_INFO"] == "/tms/1.0.0"
            assert service == "tms"
            assert len(layers) == 6
            return {"authorized": "full"}

        resp = app.get(TMS_CAPABILITIES_REQ, extra_environ={"mapproxy.authorize": auth})
        xml = resp.lxml
        assert xml.xpath("//TileMap/@title") == [
            "layer 1a",
            "layer 1b",
            "layer 1",
            "layer 2a",
            "layer 2b1",
            "layer 3",
        ]

    def test_capabilities_authorize_none(self, app):

        def auth(service, layers, **kw):
            assert service == "tms"
            assert len(layers) == 6
            return {"authorized": "none"}

        app.get(
            TMS_CAPABILITIES_REQ, extra_environ={"mapproxy.authorize": auth}, status=403
        )

    def test_capabilities_unauthenticated(self, app):

        def auth(service, layers, **kw):
            assert service == "tms"
            assert len(layers) == 6
            return {"authorized": "unauthenticated"}

        app.get(
            TMS_CAPABILITIES_REQ, extra_environ={"mapproxy.authorize": auth}, status=401
        )

    def test_capabilities_authorize_partial(self, app):

        def auth(service, layers, **kw):
            assert service == "tms"
            assert len(layers) == 6
            return {
                "authorized": "partial",
                "layers": {
                    "layer1a": {"tile": True},
                    "layer1b": {"tile": False},
                    "layer2": {"tile": True},
                    "layer2b": {"tile": True},
                    "layer2b1": {"tile": True},
                },
            }

        resp = app.get(TMS_CAPABILITIES_REQ, extra_environ={"mapproxy.authorize": auth})
        xml = resp.lxml
        assert xml.xpath("//TileMap/@title") == ["layer 1a", "layer 2b1"]

    def test_layer_capabilities_authorize_none(self, app):

        def auth(service, layers, **kw):
            assert service == "tms"
            assert len(layers) == 1
            return {"authorized": "none"}

        app.get(
            TMS_CAPABILITIES_REQ + "/layer1",
            extra_environ={"mapproxy.authorize": auth},
            status=403,
        )

    def test_layer_capabilities_authorize_all(self, app):

        def auth(service, layers, **kw):
            assert service == "tms"
            assert len(layers) == 1
            return {"authorized": "full"}

        resp = app.get(
            TMS_CAPABILITIES_REQ + "/layer1", extra_environ={"mapproxy.authorize": auth}
        )
        xml = resp.lxml
        assert xml.xpath("//TileMap/Title/text()") == ["layer 1"]

    def test_layer_capabilities_authorize_partial(self, app):

        def auth(service, layers, **kw):
            assert service == "tms"
            assert len(layers) == 1
            return {"authorized": "partial", "layers": {"layer1": {"tile": True}}}

        resp = app.get(
            TMS_CAPABILITIES_REQ + "/layer1", extra_environ={"mapproxy.authorize": auth}
        )
        xml = resp.lxml
        assert xml.xpath("//TileMap/Title/text()") == ["layer 1"]

    def test_layer_capabilities_deny_partial(self, app):

        def auth(service, layers, **kw):
            assert service == "tms"
            assert len(layers) == 1
            return {"authorized": "partial", "layers": {"layer1": {"tile": False}}}

        app.get(
            TMS_CAPABILITIES_REQ + "/layer1",
            extra_environ={"mapproxy.authorize": auth},
            status=403,
        )

    def test_get_tile(self, app):

        def auth(service, layers, environ, query_extent, **kw):
            assert environ["PATH_INFO"] == "/tms/1.0.0/layer1_EPSG900913/0/0/0.png"
            assert service == "tms"
            assert query_extent[0] == "EPSG:900913"
            assert bbox_equals(
                query_extent[1], (-20037508.342789244, -20037508.342789244, 0, 0)
            )
            assert len(layers) == 1
            return {"authorized": "partial", "layers": {"layer1": {"tile": True}}}

        resp = app.get(
            TMS_CAPABILITIES_REQ + "/layer1_EPSG900913/0/0/0.png",
            extra_environ={"mapproxy.authorize": auth},
        )
        assert resp.content_type == "image/png"
        assert resp.content_length > 1000

    def test_get_tile_global_limited_to(self, app):
        # check with limited_to for all layers
        auth_dict = {
            "authorized": "partial",
            "limited_to": {"geometry": [-180, -89, -90, 89], "srs": "EPSG:4326"},
            "layers": {"layer3": {"tile": True}},
        }
        self.check_get_tile_limited_to(app, auth_dict)

    def test_get_tile_layer_limited_to(self, app):
        # check with limited_to for one layer
        auth_dict = {
            "authorized": "partial",
            "layers": {
                "layer3": {
                    "tile": True,
                    "limited_to": {
                        "geometry": [-180, -89, -90, 89],
                        "srs": "EPSG:4326",
                    },
                }
            },
        }

        self.check_get_tile_limited_to(app, auth_dict)

    def check_get_tile_limited_to(self, app, auth_dict):

        def auth(service, layers, environ, query_extent, **kw):
            assert environ["PATH_INFO"] == "/tms/1.0.0/layer3/0/0/0.jpeg"
            assert service == "tms"
            assert len(layers) == 1
            assert query_extent[0] == "EPSG:900913"
            assert bbox_equals(
                query_extent[1], (-20037508.342789244, -20037508.342789244, 0, 0)
            )

            return auth_dict

        serv = MockServ(port=42423)
        serv.expects("/1/0/0.png")
        serv.returns(
            create_tmp_image((256, 256), color=(255, 0, 0)),
            headers={"content-type": "image/png"},
        )
        with serv:
            resp = app.get(
                TMS_CAPABILITIES_REQ + "/layer3/0/0/0.jpeg",
                extra_environ={"mapproxy.authorize": auth},
            )

        assert resp.content_type == "image/png"

        img = img_from_buf(resp.body)
        img = img.convert("RGBA")
        # left part authorized, red
        assert img.crop((0, 0, 127, 255)).getcolors()[0] == (
            127 * 255,
            (255, 0, 0, 255),
        )
        # right part not authorized, transparent
        assert img.crop((129, 0, 255, 255)).getcolors()[0][1][3] == 0

    def test_get_tile_authorize_none(self, app):

        def auth(service, layers, **kw):
            assert service == "tms"
            assert len(layers) == 1
            return {"authorized": "none"}

        app.get(
            TMS_CAPABILITIES_REQ + "/layer1/0/0/0.png",
            extra_environ={"mapproxy.authorize": auth},
            status=403,
        )


class TestKMLAuth(SysTest):

    def test_superoverlay_authorize_all(self, app):

        def auth(service, layers, environ, **kw):
            assert environ["PATH_INFO"] == "/kml/layer1/0/0/0.kml"
            assert service == "kml"
            assert len(layers) == 1
            return {"authorized": "full"}

        resp = app.get(
            "/kml/layer1/0/0/0.kml", extra_environ={"mapproxy.authorize": auth}
        )
        xml = resp.lxml
        assert xml.xpath(
            "kml:Document/kml:name/text()",
            namespaces={"kml": "http://www.opengis.net/kml/2.2"},
        ) == ["layer1"]

    def test_superoverlay_authorize_none(self, app):

        def auth(service, layers, **kw):
            assert service == "kml"
            assert len(layers) == 1
            return {"authorized": "none"}

        app.get(
            "/kml/layer1/0/0/0.kml",
            extra_environ={"mapproxy.authorize": auth},
            status=403,
        )

    def test_superoverlay_unauthenticated(self, app):

        def auth(service, layers, **kw):
            assert service == "kml"
            assert len(layers) == 1
            return {"authorized": "unauthenticated"}

        app.get(
            "/kml/layer1/0/0/0.kml",
            extra_environ={"mapproxy.authorize": auth},
            status=401,
        )

    def test_superoverlay_authorize_partial(self, app):

        def auth(service, layers, query_extent, **kw):
            assert service == "kml"
            assert len(layers) == 1
            assert query_extent[0] == "EPSG:900913"
            assert bbox_equals(
                query_extent[1],
                (
                    -20037508.342789244,
                    -20037508.342789244,
                    20037508.342789244,
                    20037508.342789244,
                ),
            )

            return {"authorized": "partial", "layers": {"layer1": {"tile": True}}}

        resp = app.get(
            "/kml/layer1/0/0/0.kml", extra_environ={"mapproxy.authorize": auth}
        )
        xml = resp.lxml
        assert xml.xpath(
            "kml:Document/kml:name/text()",
            namespaces={"kml": "http://www.opengis.net/kml/2.2"},
        ) == ["layer1"]

    def test_superoverlay_deny_partial(self, app):

        def auth(service, layers, **kw):
            assert service == "kml"
            assert len(layers) == 1
            return {"authorized": "partial", "layers": {"layer1": {"tile": False}}}

        app.get(
            "/kml/layer1/0/0/0.kml",
            extra_environ={"mapproxy.authorize": auth},
            status=403,
        )

    def test_get_tile_global_limited_to(self, app):
        # check with limited_to for all layers
        auth_dict = {
            "authorized": "partial",
            "limited_to": {"geometry": [-180, -89, -90, 89], "srs": "EPSG:4326"},
            "layers": {"layer3": {"tile": True}},
        }
        self.check_get_tile_limited_to(app, auth_dict)

    def test_get_tile_layer_limited_to(self, app):
        # check with limited_to for one layer
        auth_dict = {
            "authorized": "partial",
            "layers": {
                "layer3": {
                    "tile": True,
                    "limited_to": {
                        "geometry": [-180, -89, -90, 89],
                        "srs": "EPSG:4326",
                    },
                }
            },
        }

        self.check_get_tile_limited_to(app, auth_dict)

    def check_get_tile_limited_to(self, app, auth_dict):

        def auth(service, layers, environ, query_extent, **kw):
            assert environ["PATH_INFO"] == "/kml/layer3_EPSG900913/1/0/0.jpeg"
            assert service == "kml"
            assert len(layers) == 1
            assert query_extent[0] == "EPSG:900913"
            assert bbox_equals(
                query_extent[1], (-20037508.342789244, -20037508.342789244, 0, 0)
            )
            return auth_dict

        serv = MockServ(port=42423)
        serv.expects("/1/0/0.png")
        serv.returns(
            create_tmp_image((256, 256), color=(255, 0, 0)),
            headers={"content-type": "image/png"},
        )
        with serv:
            resp = app.get(
                "/kml/layer3_EPSG900913/1/0/0.jpeg",
                extra_environ={"mapproxy.authorize": auth},
            )

        assert resp.content_type == "image/png"

        img = img_from_buf(resp.body)
        img = img.convert("RGBA")
        # left part authorized, red
        assert img.crop((0, 0, 127, 255)).getcolors()[0] == (
            127 * 255,
            (255, 0, 0, 255),
        )
        # right part not authorized, transparent
        assert img.crop((129, 0, 255, 255)).getcolors()[0][1][3] == 0


WMTS_CAPABILITIES_REQ = "/wmts/1.0.0/WMTSCapabilities.xml"


class TestWMTSAuth(SysTest):

    def test_capabilities_authorize_all(self, app):

        def auth(service, layers, environ, **kw):
            assert environ["PATH_INFO"] == "/wmts/1.0.0/WMTSCapabilities.xml"
            assert service == "wmts"
            assert len(layers) == 6
            return {"authorized": "full"}

        resp = app.get(
            WMTS_CAPABILITIES_REQ, extra_environ={"mapproxy.authorize": auth}
        )
        xml = resp.lxml
        assert set(
            xml.xpath(
                "//wmts:Layer/ows:Title/text()",
                namespaces={
                    "wmts": "http://www.opengis.net/wmts/1.0",
                    "ows": "http://www.opengis.net/ows/1.1",
                },
            )
        ) == set(
            ["layer 1b", "layer 1a", "layer 2a", "layer 2b1", "layer 1", "layer 3"]
        )

    def test_capabilities_authorize_none(self, app):

        def auth(service, layers, **kw):
            assert service == "wmts"
            assert len(layers) == 6
            return {"authorized": "none"}

        app.get(
            WMTS_CAPABILITIES_REQ,
            extra_environ={"mapproxy.authorize": auth},
            status=403,
        )

    def test_capabilities_unauthenticated(self, app):

        def auth(service, layers, **kw):
            assert service == "wmts"
            assert len(layers) == 6
            return {"authorized": "unauthenticated"}

        app.get(
            WMTS_CAPABILITIES_REQ,
            extra_environ={"mapproxy.authorize": auth},
            status=401,
        )

    def test_capabilities_authorize_partial(self, app):

        def auth(service, layers, **kw):
            assert service == "wmts"
            assert len(layers) == 6
            return {
                "authorized": "partial",
                "layers": {
                    "layer1a": {"tile": True},
                    "layer1b": {"tile": False},
                    "layer2": {"tile": True},
                    "layer2b": {"tile": True},
                    "layer2b1": {"tile": True},
                },
            }

        resp = app.get(
            WMTS_CAPABILITIES_REQ, extra_environ={"mapproxy.authorize": auth}
        )
        xml = resp.lxml
        assert set(
            xml.xpath(
                "//wmts:Layer/ows:Title/text()",
                namespaces={
                    "wmts": "http://www.opengis.net/wmts/1.0",
                    "ows": "http://www.opengis.net/ows/1.1",
                },
            )
        ) == set(["layer 1a", "layer 2b1"])

    def test_get_tile(self, app):

        def auth(service, layers, environ, query_extent, **kw):
            assert environ["PATH_INFO"] == "/wmts/layer1/GLOBAL_MERCATOR/0/0/0.png"
            assert service == "wmts"
            assert len(layers) == 1
            assert query_extent[0] == "EPSG:900913"
            assert bbox_equals(
                query_extent[1],
                (
                    -20037508.342789244,
                    -20037508.342789244,
                    20037508.342789244,
                    20037508.342789244,
                ),
            )
            return {"authorized": "partial", "layers": {"layer1": {"tile": True}}}

        resp = app.get(
            "/wmts/layer1/GLOBAL_MERCATOR/0/0/0.png",
            extra_environ={"mapproxy.authorize": auth},
        )
        assert resp.content_type == "image/png"
        assert resp.content_length > 1000

    def test_get_tile_global_limited_to(self, app):
        # check with limited_to for all layers
        auth_dict = {
            "authorized": "partial",
            "limited_to": {"geometry": [-180, -89, -90, 89], "srs": "EPSG:4326"},
            "layers": {"layer3": {"tile": True}},
        }
        self.check_get_tile_limited_to(app, auth_dict)

    def test_get_tile_layer_limited_to(self, app):
        # check with limited_to for one layer
        auth_dict = {
            "authorized": "partial",
            "layers": {
                "layer3": {
                    "tile": True,
                    "limited_to": {
                        "geometry": [-180, -89, -90, 89],
                        "srs": "EPSG:4326",
                    },
                }
            },
        }

        self.check_get_tile_limited_to(app, auth_dict)

    def check_get_tile_limited_to(self, app, auth_dict):

        def auth(service, layers, environ, query_extent, **kw):
            assert environ["PATH_INFO"] == "/wmts/layer3/GLOBAL_MERCATOR/1/0/0.jpeg"
            assert service == "wmts"
            assert len(layers) == 1
            assert query_extent[0] == "EPSG:900913"
            assert bbox_equals(
                query_extent[1], (-20037508.342789244, 0, 0, 20037508.342789244)
            )
            return auth_dict

        serv = MockServ(port=42423)
        serv.expects("/1/0/1.png")
        serv.returns(
            create_tmp_image((256, 256), color=(255, 0, 0)),
            headers={"content-type": "image/png"},
        )
        with serv:
            resp = app.get(
                "/wmts/layer3/GLOBAL_MERCATOR/1/0/0.jpeg",
                extra_environ={"mapproxy.authorize": auth},
            )

        assert resp.content_type == "image/png"

        img = img_from_buf(resp.body)
        img = img.convert("RGBA")
        # left part authorized, red
        assert img.crop((0, 0, 127, 255)).getcolors()[0] == (
            127 * 255,
            (255, 0, 0, 255),
        )
        # right part not authorized, transparent
        assert img.crop((129, 0, 255, 255)).getcolors()[0][1][3] == 0

    def test_get_tile_limited_to_outside(self, app):

        def auth(service, layers, environ, **kw):
            assert environ["PATH_INFO"] == "/wmts/layer3/GLOBAL_MERCATOR/2/0/0.jpeg"
            assert service == "wmts"
            assert len(layers) == 1
            return {
                "authorized": "partial",
                "limited_to": {"geometry": [0, -89, 90, 89], "srs": "EPSG:4326"},
                "layers": {"layer3": {"tile": True}},
            }

        resp = app.get(
            "/wmts/layer3/GLOBAL_MERCATOR/2/0/0.jpeg",
            extra_environ={"mapproxy.authorize": auth},
        )

        assert resp.content_type == "image/png"
        is_transparent(resp.body)

    def test_get_tile_limited_to_inside(self, app):

        def auth(service, layers, environ, **kw):
            assert environ["PATH_INFO"] == "/wmts/layer3/GLOBAL_MERCATOR/1/0/0.jpeg"
            assert service == "wmts"
            assert len(layers) == 1
            return {
                "authorized": "partial",
                "limited_to": {"geometry": [-180, -89, 180, 89], "srs": "EPSG:4326"},
                "layers": {"layer3": {"tile": True}},
            }

        serv = MockServ(port=42423)
        serv.expects("/1/0/1.png")
        serv.returns(
            create_tmp_image((256, 256), color=(255, 0, 0)),
            headers={"content-type": "image/png"},
        )
        with serv:
            resp = app.get(
                "/wmts/layer3/GLOBAL_MERCATOR/1/0/0.jpeg",
                extra_environ={"mapproxy.authorize": auth},
            )

        assert resp.content_type == "image/jpeg"

        img = img_from_buf(resp.body)
        assert img.getcolors()[0] == (256 * 256, (255, 0, 0))

    def test_get_tile_kvp(self, app):

        def auth(service, layers, environ, **kw):
            assert environ["PATH_INFO"] == "/service"
            assert service == "wmts"
            assert len(layers) == 1
            return {"authorized": "partial", "layers": {"layer1": {"tile": True}}}

        resp = app.get(
            "/service?service=WMTS&version=1.0.0&layer=layer1&request=GetTile&"
            "style=&tilematrixset=GLOBAL_MERCATOR&tilematrix=00&tilerow=0&tilecol=0&format=image/png",
            extra_environ={"mapproxy.authorize": auth},
        )
        assert resp.content_type == "image/png"

    def test_get_tile_authorize_none(self, app):

        def auth(service, layers, **kw):
            assert service == "wmts"
            assert len(layers) == 1
            return {"authorized": "none"}

        app.get(
            "/wmts/layer1/GLOBAL_MERCATOR/0/0/0.png",
            extra_environ={"mapproxy.authorize": auth},
            status=403,
        )

    def test_get_tile_authorize_none_kvp(self, app):

        def auth(service, layers, environ, **kw):
            assert environ["PATH_INFO"] == "/service"
            assert service == "wmts"
            assert len(layers) == 1
            return {"authorized": "partial", "layers": {"layer1": {"tile": False}}}

        app.get(
            "/service?service=WMTS&version=1.0.0&layer=layer1&request=GetTile&"
            "style=&tilematrixset=GLOBAL_MERCATOR&tilematrix=00&tilerow=0&tilecol=0&format=image/png",
            extra_environ={"mapproxy.authorize": auth},
            status=403,
        )

    def test_get_featureinfo_kvp(self, app):

        def auth(service, layers, environ, **kw):
            assert environ["PATH_INFO"] == "/service"
            assert service == "wmts.featureinfo"
            assert len(layers) == 1
            return {"authorized": "partial", "layers": {"layer1b": {"featureinfo": True}}}


        serv = MockServ(port=42423)
        serv.expects(
            "/service?request=GetFeatureInfo&service=WMS&Version=1.1.1&SRS=EPSG:900913"
            "&BBOX=-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244"
            "&WIDTH=256&HEIGHT=256&styles=&FORMAT=image/png&X=10&Y=20"
            "&query_layers=fi&layers=fi&info_format=application/json"
        )
        serv.returns(b"{}")
        with serv:
            resp = app.get(
                "/service?service=WMTS&version=1.0.0&layer=layer1b&request=GetFeatureInfo&"
                "style=&tilematrixset=GLOBAL_MERCATOR&tilematrix=00&tilerow=0&tilecol=0&format=image/png"
                "&infoformat=application/json&i=10&j=20",
                extra_environ={"mapproxy.authorize": auth},
            )
            assert resp.content_type == "application/json"

    def test_get_featureinfo_kvp_authorized_none(self, app):

        def auth(service, layers, environ, **kw):
            assert environ["PATH_INFO"] == "/service"
            assert service == "wmts.featureinfo"
            assert len(layers) == 1
            return {"authorized": "partial", "layers": {"layer1b": {"tile": True}}}

        app.get(
            "/service?service=WMTS&version=1.0.0&layer=layer1b&request=GetFeatureInfo&"
            "style=&tilematrixset=GLOBAL_MERCATOR&tilematrix=00&tilerow=0&tilecol=0&format=image/png"
            "&infoformat=application/json&i=10&j=20",
            extra_environ={"mapproxy.authorize": auth},
            status=403,
        )

    def test_get_featureinfo_rest(self, app):

        def auth(service, layers, environ, **kw):
            assert environ["PATH_INFO"].startswith('/wmts/layer1b/')
            assert service == "wmts.featureinfo"
            assert len(layers) == 1
            return {"authorized": "partial", "layers": {"layer1b": {"featureinfo": True}}}


        serv = MockServ(port=42423)
        serv.expects(
            "/service?request=GetFeatureInfo&service=WMS&Version=1.1.1&SRS=EPSG:900913"
            "&BBOX=-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244"
            "&WIDTH=256&HEIGHT=256&styles=&FORMAT=image/png&X=10&Y=20"
            "&query_layers=fi&layers=fi&info_format=application/json"
        )
        serv.returns(b"{}")
        with serv:
            resp = app.get(
                "/wmts/layer1b/GLOBAL_MERCATOR/00/0/0/10/20.geojson",
                extra_environ={"mapproxy.authorize": auth},
            )
            assert resp.content_type == "application/json"

    def test_get_featureinfo_rest_authorized_none(self, app):

        def auth(service, layers, environ, **kw):
            assert environ["PATH_INFO"].startswith('/wmts/layer1b/')
            assert service == "wmts.featureinfo"
            assert len(layers) == 1
            return {"authorized": "partial", "layers": {"layer1b": {"tile": True}}}

        app.get(
            "/wmts/layer1b/GLOBAL_MERCATOR/00/0/0/10/20.geojson",
            extra_environ={"mapproxy.authorize": auth},
            status=403,
        )

class TestDemoAuth(SysTest):

    def test_authorize_all(self, app):

        def auth(service, layers, environ, **kw):
            return {"authorized": "full"}

        app.get("/demo", extra_environ={"mapproxy.authorize": auth})

    def test_authorize_none(self, app):

        def auth(service, layers, environ, **kw):
            return {"authorized": "none"}

        app.get("/demo", extra_environ={"mapproxy.authorize": auth}, status=403)

    def test_unauthenticated(self, app):

        def auth(service, layers, environ, **kw):
            return {"authorized": "unauthenticated"}

        app.get("/demo", extra_environ={"mapproxy.authorize": auth}, status=401)

    def test_superoverlay_authorize_none(self, app):

        def auth(service, layers, **kw):
            assert service == "kml"
            assert len(layers) == 1
            return {"authorized": "none"}

        app.get(
            "/kml/layer1/0/0/0.kml",
            extra_environ={"mapproxy.authorize": auth},
            status=403,
        )

    def test_superoverlay_unauthenticated(self, app):

        def auth(service, layers, **kw):
            assert service == "kml"
            assert len(layers) == 1
            return {"authorized": "unauthenticated"}

        app.get(
            "/kml/layer1/0/0/0.kml",
            extra_environ={"mapproxy.authorize": auth},
            status=401,
        )
