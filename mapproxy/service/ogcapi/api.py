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
from typing import Any, cast

import mapproxy.service as service_package

from mapproxy.request.base import Request
from mapproxy.response import Response
from mapproxy.service.ogcapi.constants import (
    FORMAT_TYPES,
    F_JSON,
    F_HTML,
    MEDIA_TYPE_OPENAPI_3_0,
)
from mapproxy.service.ogcapi.server import OGCAPIServer
from mapproxy.util.jinja2_templates import render_j2_template
from mapproxy.version import __version__


def _get(d: dict, *path):
    for p in path:
        if p not in d:
            return None
        d = d[p]
    return d


def api(server: OGCAPIServer, req: Request):
    log = server.log
    log.debug("API page")

    for arg in req.args:
        if arg not in ("f", "ui"):
            raise OGCAPIServer.unknown_query_parameter(arg)
    if req.args.get("f", None) not in (None, F_JSON, F_HTML):
        raise OGCAPIServer.invalid_parameter("Invalid value for f query parameter")
    if req.args.get("ui", None) not in (None, "swagger", "redoc"):
        raise OGCAPIServer.invalid_parameter("Invalid value for ui query parameter")
    is_html_req = server.is_html_req(req)
    if req.args.get("ui", None) and not is_html_req:
        raise OGCAPIServer.invalid_parameter(
            "ui query parameter can only be used with HTML output"
        )

    cfg = server.get_pygeoapi_config(req)

    if is_html_req:
        template = "openapi/swagger.html"
        if req.args.get("ui", None) == "redoc":
            template = "openapi/redoc.html"

        path = server.create_href(req, "/ogcapi/api")
        data = {"openapi-document-path": path}
        content = render_j2_template(
            cfg, service_package.__package__, "ogcapi", template, data
        )
        return Response(
            content,
            content_type=FORMAT_TYPES[F_HTML],
            headers=server.response_headers,
            status=200,
        )

    oas: dict[str, Any] = {"openapi": "3.0.2", "tags": []}
    info = {"version": __version__}

    title = _get(cfg, "metadata", "identification", "title")
    if title:
        info["title"] = title
    else:
        info["title"] = "OGCAPI implementation"

    description = _get(cfg, "metadata", "identification", "description")
    if description:
        info["description"] = description

    keywords = _get(cfg, "metadata", "identification", "keywords")
    if keywords:
        info["x-keywords"] = keywords

    terms_of_service = _get(cfg, "metadata", "identification", "terms_of_service")
    if terms_of_service:
        info["termsOfService"] = terms_of_service

    license = _get(cfg, "metadata", "license")
    if license:
        info["license"] = license

    if server.enable_maps and server.max_output_pixels:
        info["x-OGC-limits"] = {
            "maps": {
                "maxWidth": server.max_width,
                "maxHeight": server.max_height,
                "maxPixels": server.max_output_pixels,
            }
        }

    oas["info"] = info

    oas["servers"] = [
        {
            "url": cfg["server"]["url"],
        }
    ]
    server_description = _get(cfg, "metadata", "identification", "description")
    if server_description:
        oas["servers"][0]["description"] = server_description

    OPENAPI_YAML = {
        "oapim-1": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json",  # noqa
        "oapit-1": "https://schemas.opengis.net/ogcapi/tiles/part1/1.0/openapi/ogcapi-tiles-1.bundled.json",  # noqa
    }

    paths = {}

    paths["/"] = {
        "get": {
            "summary": "Landing page",
            "description": "Landing page",
            "tags": ["server"],
            "operationId": "getLandingPage",
            "parameters": [
                {"$ref": "#/components/parameters/f"},
                # {'$ref': '#/components/parameters/lang'}
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/LandingPage"
                },  # noqa
                "400": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/InvalidParameter"
                },  # noqa
                "500": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/ServerError"
                },  # noqa
            },
        }
    }

    paths["/api"] = {
        "get": {
            "summary": "This document",
            "description": "This document",
            "tags": ["server"],
            "operationId": "getOpenapi",
            "parameters": [
                {"$ref": "#/components/parameters/f"},
                # {'$ref': '#/components/parameters/lang'},
                {
                    "name": "ui",
                    "in": "query",
                    "description": "UI to render the OpenAPI document",
                    "required": False,
                    "schema": {
                        "type": "string",
                        "enum": ["swagger", "redoc"],
                        "default": "swagger",
                    },
                    "style": "form",
                    "explode": False,
                },
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/API"
                },  #
                "400": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/InvalidParameter"
                },  # noqa
                "500": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/ServerError"
                },  # noqa
            },
        }
    }

    paths["/collections"] = {
        "get": {
            "summary": "Retrieve the description of the collections available from this service.",
            "description": "Collections",
            "tags": ["server"],
            "operationId": "getCollections",
            "parameters": [
                {"$ref": "#/components/parameters/f"},
                # {'$ref': '#/components/parameters/lang'}
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/CollectionsList"
                },  # noqa
                "400": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/InvalidParameter"
                },  # noqa
                "500": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/ServerError"
                },  # noqa
            },
        }
    }

    paths["/collections/{collectionId}"] = {
        "get": {
            "summary": "Retrieve the description of a collection available from this service.",
            "description": "Collection",
            "tags": ["server"],
            "operationId": "getCollection",
            "parameters": [
                {"$ref": "#/components/parameters/collectionId"},
                {"$ref": "#/components/parameters/f"},
                # {'$ref': '#/components/parameters/lang'}
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/Collection"
                },  # noqa
                "400": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/InvalidParameter"
                },  # noqa
                "404": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/NotFound"
                },  # noqa
                "500": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/ServerError"
                },  # noqa
            },
        }
    }

    if server.enable_maps:
        paths["/collections/{collectionId}/map"] = {
            "get": {
                "summary": "Retrieve the default map for the specified collection.",
                "description": "Map",
                "tags": ["server"],
                "operationId": "getCollectionMap",
                "parameters": [
                    {"$ref": "#/components/parameters/collectionId"},
                    {"$ref": "#/components/parameters/f_img"},
                    {"$ref": "#/components/parameters/width"},
                    {"$ref": "#/components/parameters/height"},
                    {"$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/crs"},
                    {"$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/bbox"},
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/bbox-crs"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/center"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/center-crs"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/subset"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/subset-crs"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/scale-denominator"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/bgcolor"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/transparent"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/mm-per-pixel"
                    },
                    # {'$ref': '#/components/parameters/lang'}
                ],
                "responses": {
                    "200": {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/Map"
                    },  # noqa
                    "204": {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/EmptyMap"
                    },  # noqa
                    "400": {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/InvalidParameter"
                    },  # noqa
                    "404": {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/NotFound"
                    },  # noqa
                    "500": {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/ServerError"
                    },  # noqa
                },
            }
        }

    if server.enable_tiles:
        paths["/collections/{collectionId}/map/tiles"] = {
            "get": {
                "summary": "Retrieve a list of all map tilesets for specified collection",
                "description": "CollectionMapTileSets",
                "tags": ["server"],
                "operationId": "listCollectionMapTileSets",
                "parameters": [
                    {"$ref": "#/components/parameters/collectionId"},
                    {"$ref": "#/components/parameters/f"},
                ],
                "responses": {
                    "200": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/TileSetsList"
                    },  # noqa
                    "400": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/InvalidParameter"
                    },  # noqa
                    "404": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/NotFound"
                    },  # noqa
                    "500": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/ServerError"
                    },  # noqa
                },
            }
        }
        paths["/collections/{collectionId}/map/tiles/{tileMatrixSetId}"] = {
            "get": {
                "summary": "Retrieve a map tile set metadata for the specified collection and tiling scheme (tile matrix set)",  # noqa
                "description": "CollectionMapTileSet",
                "tags": ["server"],
                "operationId": "describeCollectionMapTileSet",
                "parameters": [
                    {"$ref": "#/components/parameters/collectionId"},
                    {"$ref": "#/components/parameters/tileMatrixSetId"},
                    {"$ref": "#/components/parameters/f"},
                ],
                "responses": {
                    "200": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/TileSet"
                    },  # noqa
                    "400": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/InvalidParameter"
                    },  # noqa
                    "404": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/NotFound"
                    },  # noqa
                    "500": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/ServerError"
                    },  # noqa
                },
            }
        }
        paths[
            "/collections/{collectionId}/map/tiles/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}"
        ] = {
            "get": {
                "summary": "Retrieve a map tile from the specified collection",
                "description": "CollectionMapTile",
                "tags": ["server"],
                "operationId": "getCollectionMapTile",
                "parameters": [
                    {"$ref": "#/components/parameters/collectionId"},
                    {"$ref": "#/components/parameters/tileMatrixSetId"},
                    {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/parameters/tileMatrix"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/parameters/tileRow"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/parameters/tileCol"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/bgcolor"
                    },
                    {"$ref": "#/components/parameters/f_img"},
                ],
                "responses": {
                    "200": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/MapTile"
                    },  # noqa
                    "204": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/EmptyTile"
                    },  # noqa
                    "400": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/InvalidParameter"
                    },  # noqa
                    "404": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/NotFound"
                    },  # noqa
                    "500": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/ServerError"
                    },  # noqa
                },
            }
        }

        if server.enable_maps:
            parameters = cast(list, paths[
                "/collections/{collectionId}/map/tiles/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}"
            ]["get"]["parameters"])
            parameters += [
                {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/scale-denominator"
                },
                {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/transparent"
                },
                {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/mm-per-pixel"
                },
                {"$ref": "#/components/parameters/width"},
                {"$ref": "#/components/parameters/height"},
            ]

    if server.enable_maps and server.default_dataset_layers is not None:
        paths["/map"] = {
            "get": {
                "summary": "Retrieve the default map for the whole dataset.",
                "description": "Map",
                "tags": ["server"],
                "operationId": "getDatasetMap",
                "parameters": [
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/collections"
                    },
                    {"$ref": "#/components/parameters/f_img"},
                    {"$ref": "#/components/parameters/width"},
                    {"$ref": "#/components/parameters/height"},
                    {"$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/crs"},
                    {"$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/bbox"},
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/bbox-crs"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/center"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/center-crs"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/subset"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/subset-crs"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/scale-denominator"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/bgcolor"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/transparent"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/mm-per-pixel"
                    },
                    # {'$ref': '#/components/parameters/lang'}
                ],
                "responses": {
                    "200": {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/Map"
                    },  # noqa
                    "400": {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/InvalidParameter"
                    },  # noqa
                    "500": {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/ServerError"
                    },  # noqa
                },
            }
        }

    if server.enable_tiles and server.default_dataset_layers is not None:
        paths["/map/tiles"] = {
            "get": {
                "summary": "Retrieve a list of all map tilesets for the wkole dataset",
                "description": "DatasetMapTileSets",
                "tags": ["server"],
                "operationId": "listDatasetMapTileSets",
                "parameters": [
                    {"$ref": "#/components/parameters/f"},
                ],
                "responses": {
                    "200": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/TileSetsList"
                    },  # noqa
                    "400": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/InvalidParameter"
                    },  # noqa
                    "404": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/NotFound"
                    },  # noqa
                    "500": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/ServerError"
                    },  # noqa
                },
            }
        }
        paths["/map/tiles/{tileMatrixSetId}"] = {
            "get": {
                "summary": "Retrieve a map tile set metadata for the whole datase and tiling scheme (tile matrix set)",  # noqa
                "description": "DatasetMapTileSet",
                "tags": ["server"],
                "operationId": "describeDatasetMapTileSet",
                "parameters": [
                    {"$ref": "#/components/parameters/tileMatrixSetId"},
                    {"$ref": "#/components/parameters/f"},
                ],
                "responses": {
                    "200": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/TileSet"
                    },  # noqa
                    "400": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/InvalidParameter"
                    },  # noqa
                    "404": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/NotFound"
                    },  # noqa
                    "500": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/ServerError"
                    },  # noqa
                },
            }
        }
        paths["/map/tiles/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}"] = {
            "get": {
                "summary": "Retrieve a map tile from the whole dataset",
                "description": "CollectionMapTile",
                "tags": ["server"],
                "operationId": "getDatasetMapTile",
                "parameters": [
                    {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/parameters/collections"
                    },
                    {"$ref": "#/components/parameters/tileMatrixSetId"},
                    {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/parameters/tileMatrix"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/parameters/tileRow"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/parameters/tileCol"
                    },
                    {
                        "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/bgcolor"
                    },
                    {"$ref": "#/components/parameters/f_img"},
                ],
                "responses": {
                    "200": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/MapTile"
                    },  # noqa
                    "204": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/EmptyTile"
                    },  # noqa
                    "400": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/InvalidParameter"
                    },  # noqa
                    "404": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/NotFound"
                    },  # noqa
                    "500": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/ServerError"
                    },  # noqa
                },
            }
        }

        if server.enable_maps:
            parameters = cast(list, paths["/map/tiles/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}"][
                "get"
            ]["parameters"])
            parameters += [
                {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/scale-denominator"
                },
                {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/transparent"
                },
                {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/parameters/mm-per-pixel"
                },
                {"$ref": "#/components/parameters/width"},
                {"$ref": "#/components/parameters/height"},
            ]

    if server.enable_tiles and server.grid_configs:
        paths["/tileMatrixSets"] = {
            "get": {
                "tags": ["server"],
                "description": "TileMatrixSets",
                "summary": "Retrieve the list of available tiling schemes (tile matrix sets)",
                "operationId": "listTileMatrixSets",
                "parameters": [
                    {"$ref": "#/components/parameters/f"},
                    # {'$ref': '#/components/parameters/lang'}
                ],
                "responses": {
                    "200": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/TileMatrixSetsList"
                    },  # noqa
                    "400": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/InvalidParameter"
                    },  # noqa
                    "500": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/ServerError"
                    },  # noqa
                },
            }
        }

        paths["/tileMatrixSets/{tileMatrixSetId}"] = {
            "get": {
                "tags": ["server"],
                "description": "TileMatrixSet",
                "summary": "Retrieve the definition of the specified tiling scheme (tile matrix set)",
                "operationId": "describeTileMatrixSet",
                "parameters": [
                    {"$ref": "#/components/parameters/f"},
                    {"$ref": "#/components/parameters/tileMatrixSetId"},
                    # {'$ref': '#/components/parameters/lang'}
                ],
                "responses": {
                    "200": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/TileMatrixSet"
                    },  # noqa
                    "400": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/InvalidParameter"
                    },  # noqa
                    "500": {
                        "$ref": f"{OPENAPI_YAML['oapit-1']}#/components/responses/ServerError"
                    },  # noqa
                },
            }
        }
    paths["/conformance"] = {
        "get": {
            "summary": "API conformance definition",
            "description": "API conformance definition",
            "tags": ["server"],
            "operationId": "getConformanceDeclaration",
            "parameters": [
                {"$ref": "#/components/parameters/f"},
                # {'$ref': '#/components/parameters/lang'}
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/Conformance"
                },  # noqa
                "400": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/InvalidParameter"
                },  # noqa
                "500": {
                    "$ref": f"{OPENAPI_YAML['oapim-1']}#/components/responses/ServerError"
                },  # noqa
            },
        }
    }

    oas["paths"] = paths

    tags_server = {
        "name": "server",
        "description": description if description else "OGCAPI implementation",  # noqa
    }
    identification_url = _get(cfg, "metadata", "identification", "url")
    if identification_url:
        tags_server["externalDocs"] = {
            "description": "information",
            "url": identification_url,
        }
    oas["tags"].append(tags_server)

    oas["components"] = {
        "responses": {
            "200": {"description": "Successful operation"},
        },
        "parameters": _get_openapi_parameters(server),
    }

    return Response(
        json.dumps(oas, indent=2),
        content_type=MEDIA_TYPE_OPENAPI_3_0,
        headers=server.response_headers,
        status=200,
    )


def _get_openapi_parameters(server: OGCAPIServer):
    parameters: dict[str, Any] = {
        "f": {
            "name": "f",
            "in": "query",
            "description": "The optional f parameter indicates the output format which the server shall provide as part of the response document.  The default format is JSON.",  # noqa
            "required": False,
            "schema": {
                "type": "string",
                "enum": ["json", "html"],
                "default": "json",
            },
            "style": "form",
            "explode": False,
        },
        "collectionId": {
            "name": "collectionId",
            "in": "path",
            "description": "Local identifier of a collection",
            "required": True,
            "allowEmptyValue": False,
            "schema": {
                "type": "string",
                "enum": [id for id in server.layers],
            },
        },
    }

    if server.enable_tiles and server.grid_configs:
        parameters["tileMatrixSetId"] = {
            "name": "tileMatrixSetId",
            "in": "path",
            "description": "Identifier for a supported TileMatrixSet",
            "required": True,
            "allowEmptyValue": False,
            "schema": {
                "type": "string",
                "enum": [id for id in server.grid_configs],
            },
        }

    if server.enable_maps:
        parameters["f_img"] = {
            "name": "f",
            "in": "query",
            "description": "The optional f parameter indicates the output format which the server shall provide as part of the response document.  The default format is PNG.",  # noqa
            "required": False,
            "schema": {
                "type": "string",
                "enum": ["png", "jpeg"],
                "default": "png",
            },
            "style": "form",
            "explode": False,
        }

        parameters["width"] = {
            "name": "width",
            "in": "query",
            "description": "Width of the map in pixels. If omitted and `height` is specified, defaults to the width maintaining a 1:1 aspect ratio. If both `width` and `height` are omitted, the server will select default dimensions. When used together with the `center` and/or `scale-denominator` parameter, `width` takes on a subsetting role rather than scaling (resampling), defining the horizontal portion of the map to subset based on the scale (native scale, or specified by `scale-denominator`) and display resolution (0.28 mm/pixel, or specified by `mm-per-pixel`).",  # noqa
            "required": False,
            "style": "form",
            "explode": False,
            "schema": {"type": "integer"},
        }

        parameters["height"] = {
            "name": "height",
            "in": "query",
            "description": "Height of the map in pixels. If omitted and `width` is specified, defaults to the height maintaining a 1:1 aspect ratio. If both `width` and `height` are omitted, the server will select default dimensions. When used together with the `center` and/or `scale-denominator` parameter, `height` takes on a subsetting role rather than scaling (resampling), defining the vertical portion of the map to subset based on the scale (native scale, or specified by `scale-denominator`) and display resolution (0.28 mm/pixel, or specified by `mm-per-pixel`).",  # noqa
            "required": False,
            "style": "form",
            "explode": False,
            "schema": {"type": "integer"},
        }

        if server.max_width:
            parameters["width"]["schema"]["maximum"] = server.max_width

        if server.max_height:
            parameters["height"]["schema"]["maximum"] = server.max_height

    return parameters
