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
from mapproxy.source import ogcapitiles


class TestOGCAPITilesSource(SysTest):
    @pytest.fixture(scope="class")
    def config_file(self):
        return "ogcapitiles_source.yaml"

    def test_global_same_tiling_scheme(self, app):
        ogcapitiles.reset_config_cache = True

        landing_page = {
            "links": [
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tilesets-map",
                    "type": "application/json",
                    "title": "Map tilesets available for this dataset (as JSON)",
                    "href": "/ogcapi/map/tiles?f=json",
                },
            ]
        }

        tilesets = {
            "tilesets": [
                {
                    "title": "my_collection",
                    "tileMatrixSetURI": "http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad",
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
                    "dataType": "map",
                    "links": [
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "application/json",
                            "title": "WebMercatorQuadTileMatrixSet definition (as JSON)",
                            "href": "/ogcapi/tileMatrixSets/WebMercatorQuad",
                        },
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "WebMercatorQuad map tileset for my_collection (as JSON)",
                            "href": "/ogcapi/map/tiles/WebMercatorQuad?f=json",
                        },
                    ],
                },
            ]
        }

        WebMercatorQuad = {
            "id": "WebMercatorQuad",
            "title": "WebMercatorQuad",
            "uri": "http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad",
            "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
            "orderedAxes": ["E", "N"],
            "wellKnownScaleSet": "http://www.opengis.net/def/wkss/OGC/1.0/GoogleMapsCompatible",
            "tileMatrices": [
                {
                    "id": "0",
                    "scaleDenominator": 559082264.028718,
                    "cellSize": 156543.03392804,
                    "cornerOfOrigin": "topLeft",
                    "pointOfOrigin": [-20037508.3427892, 20037508.3427892],
                    "matrixWidth": 1,
                    "matrixHeight": 1,
                    "tileWidth": 256,
                    "tileHeight": 256,
                },
                {
                    "id": "1",
                    "scaleDenominator": 279541132.01436,
                    "cellSize": 78271.5169640205,
                    "cornerOfOrigin": "topLeft",
                    "pointOfOrigin": [-20037508.3427892, 20037508.3427892],
                    "matrixWidth": 2,
                    "matrixHeight": 2,
                    "tileWidth": 256,
                    "tileHeight": 256,
                },
                {
                    "id": "2",
                    "scaleDenominator": 139770566.00718,
                    "cellSize": 39135.7584820102,
                    "cornerOfOrigin": "topLeft",
                    "pointOfOrigin": [-20037508.3427892, 20037508.3427892],
                    "matrixWidth": 4,
                    "matrixHeight": 4,
                    "tileWidth": 256,
                    "tileHeight": 256,
                },
            ],
        }

        tiles = {
            "title": "dataset",
            "tileMatrixSetURI": "http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad",
            "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
            "dataType": "map",
            "links": [
                {
                    "rel": "item",
                    "type": "image/png",
                    "title": "WebMercatorQuad map tiles for dataset (as PNG)",
                    "href": "/ogcapi/map/tiles/WebMercatorQuad/{tileMatrix}/{tileRow}/{tileCol}.png",
                    "templated": True,
                },
            ],
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
                    {"path": r"/ogcapi/map/tiles?f=json"},
                    {
                        "body": bytes(json.dumps(tilesets).encode("UTF-8")),
                        "headers": {"content-type": "application/json"},
                    },
                ),
                (
                    {"path": r"/ogcapi/tileMatrixSets/WebMercatorQuad"},
                    {
                        "body": bytes(json.dumps(WebMercatorQuad).encode("UTF-8")),
                        "headers": {"content-type": "application/json"},
                    },
                ),
                (
                    {"path": r"/ogcapi/map/tiles/WebMercatorQuad?f=json"},
                    {
                        "body": bytes(json.dumps(tiles).encode("UTF-8")),
                        "headers": {"content-type": "application/json"},
                    },
                ),
                (
                    {"path": r"/ogcapi/map/tiles/WebMercatorQuad/2/0/1.png"},
                    {"body": img.read(), "headers": {"content-type": "image/png"}},
                ),
            ]
            with mock_httpd(("localhost", 42423), expected_reqs):
                resp = app.get("/tiles/test_cache_global/webmercator/2/1/0.png")
                assert resp.content_type == "image/png"
                img = Image.open(BytesIO(resp.body))
                assert img.format == "PNG"
                assert img.width == 256
                assert img.height == 256
                assert img.getextrema() == ((255, 255), (0, 0), (0, 0))

        with tmp_image((256, 256), format="png", color=(0, 255, 0)) as img:
            expected_reqs = [
                (
                    {"path": r"/ogcapi/map/tiles/WebMercatorQuad/0/0/0.png"},
                    {"body": img.read(), "headers": {"content-type": "image/png"}},
                ),
            ]
            with mock_httpd(("localhost", 42423), expected_reqs):
                resp = app.get("/tiles/test_cache_global/webmercator/0/0/0.png")
                assert resp.content_type == "image/png"
                img = Image.open(BytesIO(resp.body))
                assert img.format == "PNG"
                assert img.width == 256
                assert img.height == 256
                assert img.getextrema() == ((0, 0), (255, 255), (0, 0))

    def test_collection_not_same_tiling_scheme(self, app):
        ogcapitiles.reset_config_cache = True

        my_collection = {
            "links": [
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tilesets-map",
                    "type": "application/json",
                    "title": "Map tilesets available for this dataset (as JSON)",
                    "href": "/ogcapi/collections/my_collection/map/tiles?f=json",
                },
            ]
        }

        tilesets = {
            "tilesets": [
                {
                    "title": "my_collection",
                    "tileMatrixSetURI": "http://www.opengis.net/def/tilematrixset/OGC/1.0/tileMatrixSet",
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
                    "dataType": "map",
                    "links": [
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "application/json",
                            "title": "tileMatrixSet definition (as JSON)",
                            "href": "/ogcapi/tileMatrixSets/tileMatrixSet",
                        },
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "tileMatrixSet map tileset for my_collection (as JSON)",
                            "href": "/ogcapi/collections/my_collection/map/tiles/tileMatrixSet?f=json",
                        },
                    ],
                },
                {
                    "title": "my_collection",
                    "tileMatrixSetURI": "http://www.opengis.net/def/tilematrixset/OGC/1.0/my_tms",
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
                    "dataType": "map",
                    "links": [
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "application/json",
                            "title": "my_tms definition (as JSON)",
                            "href": "/ogcapi/tileMatrixSets/my_tms",
                        },
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "my_tms map tileset for my_collection (as JSON)",
                            "href": "/ogcapi/collections/my_collection/map/tiles/my_tms?f=json",
                        },
                    ],
                },
            ]
        }

        my_tms = {
            "id": "my_tms",
            "title": "my_tms",
            "uri": "http://www.opengis.net/def/tilematrixset/OGC/1.0/my_tms",
            "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
            "orderedAxes": ["E", "N"],
            "tileMatrices": [
                {
                    "id": "0",
                    "scaleDenominator": 279541132.01436,
                    "cellSize": 78271.5169640205,
                    "cornerOfOrigin": "topLeft",
                    "pointOfOrigin": [-20037508.3427892, 20037508.3427892],
                    "matrixWidth": 2,
                    "matrixHeight": 2,
                    "tileWidth": 256,
                    "tileHeight": 256,
                },
            ],
        }

        tiles = {
            "title": "my_collection",
            "tileMatrixSetURI": "http://www.opengis.net/def/tilematrixset/OGC/1.0/my_tms",
            "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
            "dataType": "map",
            "links": [
                {
                    "rel": "item",
                    "type": "image/png",
                    "title": "my_tms map tiles for my_collection (as PNG)",
                    "href": "/ogcapi/collections/my_collection/map/tiles/my_tms/{tileMatrix}/{tileRow}/{tileCol}.png",
                    "templated": True,
                },
            ],
        }

        expected_reqs = [
            (
                {"path": r"/ogcapi/collections/my_collection"},
                {
                    "body": bytes(json.dumps(my_collection).encode("UTF-8")),
                    "headers": {"content-type": "application/json"},
                },
            ),
            (
                {"path": r"/ogcapi/collections/my_collection/map/tiles?f=json"},
                {
                    "body": bytes(json.dumps(tilesets).encode("UTF-8")),
                    "headers": {"content-type": "application/json"},
                },
            ),
            (
                {"path": r"/ogcapi/tileMatrixSets/my_tms"},
                {
                    "body": bytes(json.dumps(my_tms).encode("UTF-8")),
                    "headers": {"content-type": "application/json"},
                },
            ),
            (
                {"path": r"/ogcapi/collections/my_collection/map/tiles/my_tms?f=json"},
                {
                    "body": bytes(json.dumps(tiles).encode("UTF-8")),
                    "headers": {"content-type": "application/json"},
                },
            ),
        ]
        with mock_httpd(("localhost", 42423), expected_reqs, unordered=True):
            resp = app.get(
                "/tiles/test_cache/webmercator/0/0/0.png", expect_errors=True
            )
            assert resp.content_type == "text/plain"
            assert resp.body == b"BBOX does not align to tile"


class TestOGCAPITilesNonEarthSource(SysTest):
    @pytest.fixture(scope="class")
    def config_file(self):
        return "ogcapitiles_non_earth_source.yaml"

    def test(self, app):
        ogcapitiles.reset_cache = True

        my_collection = {
            "links": [
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tilesets-map",
                    "type": "application/json",
                    "title": "Map tilesets available for this dataset (as JSON)",
                    "href": "/ogcapi/collections/my_collection/map/tiles?f=json",
                },
            ],
            "storageCrs": "http://www.opengis.net/def/crs/IAU/2015/30100",
        }

        tilesets = {
            "tilesets": [
                {
                    "title": "my_collection",
                    "crs": "http://www.opengis.net/def/crs/IAU/2015/30100",
                    "dataType": "map",
                    "links": [
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "application/json",
                            "title": "moon_grid definition (as JSON)",
                            "href": "/ogcapi/tileMatrixSets/moon_grid",
                        },
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "moon_grid map tileset for my_collection (as JSON)",
                            "href": "/ogcapi/collections/my_collection/map/tiles/moon_grid?f=json",
                        },
                    ],
                },
                {
                    "title": "my_collection",
                    "crs": "http://www.opengis.net/def/crs/IAU/2015/30100",
                    "dataType": "map",
                    "links": [
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "application/json",
                            "title": "moon_grid definition (as JSON)",
                            "href": "/ogcapi/tileMatrixSets/moon_grid",
                        },
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "moon_grid map tileset for my_collection (as JSON)",
                            "href": "/ogcapi/collections/my_collection/map/tiles/moon_grid?f=json",
                        },
                    ],
                },
            ]
        }

        moon_grid = {
            "id": "moon_grid",
            "title": "moon_grid",
            "crs": "http://www.opengis.net/def/crs/IAU/2015/30100",
            "orderedAxes": ["N", "E"],
            "tileMatrices": [
                {
                    "id": "0",
                    "scaleDenominator": 559082264.0287179,
                    "cellSize": 1.40625,
                    "cornerOfOrigin": "topLeft",
                    "pointOfOrigin": [90, -180],
                    "matrixWidth": 1,
                    "matrixHeight": 1,
                    "tileWidth": 256,
                    "tileHeight": 256,
                },
                {
                    "id": "1",
                    "scaleDenominator": 279541132.01435894,
                    "cellSize": 0.703125,
                    "cornerOfOrigin": "topLeft",
                    "pointOfOrigin": [90, -180],
                    "matrixWidth": 2,
                    "matrixHeight": 2,
                    "tileWidth": 256,
                    "tileHeight": 256,
                },
            ],
        }

        tiles = {
            "title": "my_collection",
            "crs": "http://www.opengis.net/def/crs/IAU/2015/30100",
            "dataType": "map",
            "links": [
                {
                    "rel": "item",
                    "type": "image/png",
                    "title": "moon_grid map tiles for my_collection (as PNG)",
                    "href": "/ogcapi/collections/my_collection/map/tiles/moon_grid/{tileMatrix}/{tileRow}/{tileCol}.png",  # noqa
                    "templated": True,
                },
            ],
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
                    {"path": r"/ogcapi/collections/my_collection/map/tiles?f=json"},
                    {
                        "body": bytes(json.dumps(tilesets).encode("UTF-8")),
                        "headers": {"content-type": "application/json"},
                    },
                ),
                (
                    {"path": r"/ogcapi/tileMatrixSets/moon_grid"},
                    {
                        "body": bytes(json.dumps(moon_grid).encode("UTF-8")),
                        "headers": {"content-type": "application/json"},
                    },
                ),
                (
                    {
                        "path": r"/ogcapi/collections/my_collection/map/tiles/moon_grid?f=json"
                    },
                    {
                        "body": bytes(json.dumps(tiles).encode("UTF-8")),
                        "headers": {"content-type": "application/json"},
                    },
                ),
                (
                    {
                        "path": r"/ogcapi/collections/my_collection/map/tiles/moon_grid/1/0/1.png"
                    },
                    {"body": img.read(), "headers": {"content-type": "image/png"}},
                ),
            ]
            with mock_httpd(("localhost", 42423), expected_reqs):
                resp = app.get("/wmts/test/moon_grid/1/1/0.png")
                assert resp.content_type == "image/png"
                img = Image.open(BytesIO(resp.body))
                assert img.format == "PNG"
                assert img.width == 512
                assert img.height == 256
                assert img.getextrema() == ((255, 255), (0, 0), (0, 0))
