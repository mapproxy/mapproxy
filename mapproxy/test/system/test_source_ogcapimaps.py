# This file is part of the MapProxy project.
# Copyright (C) 2025 Spatialys
#
# Initial development funded by Centre National d'Etudes Spatiales (CNES): https://cnes.fr
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

import json
from io import BytesIO

import pytest

from PIL import Image
from mapproxy.test.http import mock_httpd
from mapproxy.test.image import tmp_image
from mapproxy.test.system import SysTest
from mapproxy.source import ogcapimaps


class TestOGCAPIMapsSource(SysTest):
    @pytest.fixture(scope="class")
    def config_file(self):
        return "ogcapimaps_source.yaml"

    def test_global_same_crs(self, app):
        ogcapimaps.reset_config_cache = True

        landing_page = {
            "links": [
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                    "type": "image/png",
                    "title": "Map available for this dataset (as PNG)",
                    "href": "/ogcapi/map.png",
                },
            ]
        }

        with tmp_image((256, 256), format="png", color=(255, 0, 0)) as img:
            expected_reqs = [
                (
                    {"path": r"/ogcapi"},
                    {
                        "body": bytes(json.dumps(landing_page).encode("UTF-8")),
                        "headers": {"content-type": "application/json"},
                    },
                ),
                (
                    {
                        "path": r"/ogcapi/map.png?bbox=-180,-90,180,90&width=256&height=256"
                    },
                    {"body": img.read(), "headers": {"content-type": "image/png"}},
                ),
            ]
            with mock_httpd(("localhost", 42423), expected_reqs):
                resp = app.get(
                    "/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&"
                    "LAYERS=test_source_global&BBOX=-90,-180,90,180&"
                    "CRS=EPSG:4326&WIDTH=256&HEIGHT=256&"
                    "FORMAT=image/png&STYLES="
                )
                assert resp.content_type == "image/png"
                img = Image.open(BytesIO(resp.body))
                assert img.format == "PNG"
                assert img.width == 256
                assert img.height == 256
                assert img.getextrema() == ((255, 255), (0, 0), (0, 0))

    def test_collection_different_crs(self, app):
        ogcapimaps.reset_config_cache = True

        my_collection = {
            "links": [
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                    "type": "image/png",
                    "title": "Map available for this dataset (as PNG)",
                    "href": "/ogcapi/collections/my_collection/map.png",
                },
            ],
            "storageCrs": "http://www.opengis.net/def/crs/EPSG/0/3857",
        }

        with tmp_image((512, 510), format="png", color=(255, 0, 0)) as img:
            expected_reqs = [
                (
                    {"path": r"/ogcapi/collections/my_collection"},
                    {
                        "body": bytes(json.dumps(my_collection).encode("UTF-8")),
                        "headers": {"content-type": "application/json"},
                    },
                ),
                (
                    {
                        "path": r"/ogcapi/collections/my_collection/map.png?"
                        "bbox=-20037508.342789244,-19971868.880408566,"
                        "20037508.342789244,19971868.880408566&"
                        "bbox-crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2F"
                        "EPSG%2F0%2F3857&"
                        "crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2F"
                        "EPSG%2F0%2F3857&"
                        "width=512&height=510&transparent=true"
                    },
                    {"body": img.read(), "headers": {"content-type": "image/png"}},
                ),
            ]
            with mock_httpd(
                ("localhost", 42423), expected_reqs, bbox_aware_query_comparator=True
            ):
                resp = app.get(
                    "/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&"
                    "LAYERS=test_source&BBOX=-85,-180,85,180&CRS=EPSG:4326&"
                    "WIDTH=512&HEIGHT=256&FORMAT=image/png&STYLES="
                )
                assert resp.content_type == "image/png"
                img = Image.open(BytesIO(resp.body))
                assert img.format == "PNG"
                assert img.width == 512
                assert img.height == 256
                assert img.getextrema() == ((255, 255), (0, 0), (0, 0))


class TestOGCAPIMapsWithSupportedSRSSource(SysTest):
    @pytest.fixture(scope="class")
    def config_file(self):
        return "ogcapimaps_source_with_supported_srs.yaml"

    def test(self, app):
        my_collection = {
            "links": [
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                    "type": "image/png",
                    "title": "Map available for this dataset (as PNG)",
                    "href": "/ogcapi/collections/my_collection/map.png",
                },
            ]
        }

        with tmp_image((512, 510), format="png", color=(255, 0, 0)) as img:
            expected_reqs = [
                (
                    {"path": r"/ogcapi/collections/my_collection"},
                    {
                        "body": bytes(json.dumps(my_collection).encode("UTF-8")),
                        "headers": {"content-type": "application/json"},
                    },
                ),
                (
                    {
                        "path": r"/ogcapi/collections/my_collection/map.png?"
                        "bbox=-20037508.342789244,-19971868.880408566,"
                        "20037508.342789244,19971868.880408566&"
                        "bbox-crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2F"
                        "EPSG%2F0%2F3857&"
                        "crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2F"
                        "EPSG%2F0%2F3857&"
                        "width=512&height=510&bgcolor=0xFF00FF"
                    },
                    {"body": img.read(), "headers": {"content-type": "image/png"}},
                ),
            ]
            with mock_httpd(
                ("localhost", 42423), expected_reqs, bbox_aware_query_comparator=True
            ):
                resp = app.get(
                    "/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&"
                    "LAYERS=test_source&BBOX=-85,-180,85,180&CRS=EPSG:4326&"
                    "WIDTH=512&HEIGHT=256&FORMAT=image/png&STYLES="
                )
                assert resp.content_type == "image/png"
                img = Image.open(BytesIO(resp.body))
                assert img.format == "PNG"
                assert img.width == 512
                assert img.height == 256
                assert img.getextrema() == ((255, 255), (0, 0), (0, 0))


class TestOGCAPIMapsNonEarthSource(SysTest):
    @pytest.fixture(scope="class")
    def config_file(self):
        return "ogcapimaps_non_earth_source.yaml"

    def test(self, app):
        ogcapimaps.reset_cache = True

        resp = app.get("/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities")
        assert b'<BoundingBox CRS="IAU_2015:30100" minx="-90" miny="-180" maxx="90" maxy="180" />' in resp.body
        assert b'EPSG:' not in resp.body
        assert b'CRS:84' not in resp.body

        my_collection = {
            "links": [
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                    "type": "image/png",
                    "title": "Map available for this dataset (as PNG)",
                    "href": "/ogcapi/collections/my_collection/map.png",
                },
            ],
            "storageCrs": "http://www.opengis.net/def/crs/IAU/2015/30100"
        }

        with tmp_image((512, 256), format="png", color=(255, 0, 0)) as img:
            expected_reqs = [
                (
                    {"path": r"/ogcapi/collections/my_collection"},
                    {
                        "body": bytes(json.dumps(my_collection).encode("UTF-8")),
                        "headers": {"content-type": "application/json"},
                    },
                ),
                (
                    {"path": r"/ogcapi/collections/my_collection/map.png?bbox=-90,-180,90,180&bbox-crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FIAU%2F2015%2F30100&crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FIAU%2F2015%2F30100&width=512&height=256"},  # noqa
                    {"body": img.read(), "headers": {"content-type": "image/png"}},
                ),
            ]
            with mock_httpd(("localhost", 42423), expected_reqs):
                resp = app.get("/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&"
                               "LAYERS=test&BBOX=-90,-180,90,180&"
                               "CRS=IAU_2015:30100&WIDTH=512&HEIGHT=256&"
                               "FORMAT=image/png&STYLES=")
                assert resp.content_type == "image/png"
                img = Image.open(BytesIO(resp.body))
                assert img.format == "PNG"
                assert img.width == 512
                assert img.height == 256
                assert img.getextrema() == ((255, 255), (0, 0), (0, 0))
