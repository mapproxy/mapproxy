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

import copy
import json
import yaml

from mapproxy.config.configuration.proxy import ProxyConfiguration
from mapproxy.script.gridconf_from_ogcapitilematrixset import (
    gridconf_from_ogcapitilematrixset_command,
)
from mapproxy.test.helper import capture
from mapproxy.test.http import mock_httpd


class TestUtilGridConfFromOGCAPITileMatrixSet(object):
    def test(self):
        landing_page = {
            "links": [
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-schemes",
                    "type": "application/json",
                    "title": "Map tilesets available for this dataset (as JSON)",
                    "href": "/ogcapi/tileMatrixSets?f=json",
                },
            ]
        }

        tileMatrixSets = {
            "tileMatrixSets": [
                {
                    "id": "WebMercatorQuad",
                    "title": "WebMercatorQuad",
                    "links": [
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "The JSON representation of the WebMercatorQuad tiling scheme definition",
                            "href": "/ogcapi/tileMatrixSets/WebMercatorQuad?f=json",
                        },
                    ],
                },
                {
                    "id": "invalid",
                    "title": "invalid",
                    "links": [
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "The JSON representation of the invalid tiling scheme definition",
                            "href": "/ogcapi/tileMatrixSets/invalid?f=json",
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

        invalid = copy.copy(WebMercatorQuad)
        invalid["id"] = "invalid"
        invalid["crs"] = "http://www.opengis.net/def/crs/EPSG/0/98765432"

        expected_reqs = [
            (
                {"path": r"/ogcapi"},
                {
                    "body": bytes(json.dumps(landing_page).encode("UTF-8")),
                    "headers": {"content-type": "application/json"},
                },
            ),
            (
                {"path": r"/ogcapi/tileMatrixSets?f=json"},
                {
                    "body": bytes(json.dumps(tileMatrixSets).encode("UTF-8")),
                    "headers": {"content-type": "application/json"},
                },
            ),
            (
                {"path": r"/ogcapi/tileMatrixSets/WebMercatorQuad?f=json"},
                {
                    "body": bytes(json.dumps(WebMercatorQuad).encode("UTF-8")),
                    "headers": {"content-type": "application/json"},
                },
            ),
            (
                {"path": r"/ogcapi/tileMatrixSets/invalid?f=json"},
                {
                    "body": bytes(json.dumps(invalid).encode("UTF-8")),
                    "headers": {"content-type": "application/json"},
                },
            ),
        ]
        with mock_httpd(("localhost", 42423), expected_reqs):
            with capture() as (out, err):
                args = ["dummy_utility", "http://localhost:42423/ogcapi"]
                gridconf_from_ogcapitilematrixset_command(args)
        captured_error = err.getvalue()
        captured_output = out.getvalue()
        assert (
            "Cannot handle http://localhost:42423/ogcapi/tileMatrixSets/invalid?f=json: "
            + "CRS http://www.opengis.net/def/crs/EPSG/0/98765432 is not supported"
            in captured_error
        )
        pos_grids = captured_output.find("grids:")
        config_dict = yaml.safe_load(captured_output[pos_grids:])
        assert config_dict == {
            "grids": {
                "WebMercatorQuad": {
                    "bbox": [
                        -20037508.3427892,
                        -20037508.342789043,
                        20037508.342789043,
                        20037508.3427892,
                    ],
                    "origin": "ul",
                    "res": [156543.03392804, 78271.5169640205, 39135.7584820102],
                    "srs": "EPSG:3857",
                    "tile_size": [256, 256],
                }
            }
        }

        config = ProxyConfiguration(config_dict)
        grid = config.grids["WebMercatorQuad"].tile_grid()
        assert grid.name == "WebMercatorQuad"
        assert grid.bbox == (
            -20037508.3427892,
            -20037508.342789043,
            20037508.342789043,
            20037508.3427892,
        )
        assert grid.origin == "ul"
        assert grid.srs.srs_code == "EPSG:3857"
        assert grid.tile_size == (256, 256)
        assert [grid.resolutions[level] for level in range(grid.levels)] == config_dict[
            "grids"
        ]["WebMercatorQuad"]["res"]
