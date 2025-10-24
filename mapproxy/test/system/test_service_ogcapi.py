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

from importlib import resources as importlib_resources
import json
import jsonschema
from io import BytesIO
import sys
from PIL import Image

import pytest

from mapproxy.srs import SRS
import mapproxy.test as test_module
from mapproxy.test.http import mock_httpd
from mapproxy.test.image import tmp_image
from mapproxy.test.system import SysTest
from mapproxy.version import __version__


# Base test class
class TestOGCAPIService(SysTest):
    def _test_links(self, app, json_doc):
        if isinstance(json_doc, dict):
            links = json_doc.get("links", None)
            if links:
                for link in links:
                    href = link["href"]
                    if not (href.endswith(".png") or href.endswith(".jpg")):
                        try:
                            app.get(href)
                        except Exception:
                            raise Exception(f"Cannot get {href}")
            else:
                for k in json_doc:
                    self._test_links(app, json_doc[k])
        elif isinstance(json_doc, list):
            for elt in json_doc:
                self._test_links(app, elt)


# Tests where only OGC API Maps is enabled
class TestOGCAPIMapsService(TestOGCAPIService):
    @pytest.fixture(scope="class")
    def config_file(self):
        return "ogcapimaps_service.yaml"

    def test_invalid_resource(self, app):
        app.get("/ogcapi/invalid", expect_errors=True, status=404)

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/ogcapi",
            "/ogcapi/api",
            "/ogcapi/map",
            "/ogcapi/conformance",
            "/ogcapi/collections",
            "/ogcapi/collections/test",
            "/ogcapi/collections/test/map",
        ],
    )
    def test_generic_errors(self, app, endpoint):
        resp = app.get(endpoint, {"unexpected": "true"}, status=400)
        assert resp.content_type == "application/json"
        assert resp.json == {
            "detail": "Unknown query parameter unexpected",
            "status": 400,
            "title": "OGCAPI",
            "type": "Bad Request",
        }

        resp = app.get(endpoint, {"f": "unexpected"}, status=400)
        assert resp.content_type == "application/json"
        assert resp.json == {
            "detail": "Invalid value for f query parameter",
            "status": 400,
            "title": "OGCAPI",
            "type": "Invalid Parameter",
        }

    def _validate_response_against_schema(
        self, json_doc, schema_name=None, response_name=None
    ):
        if sys.version_info < (3, 10):
            # jsonschema.validate() hangs for py 3.9
            return

        ogcapi_tiles_schema_path = (
            importlib_resources.files(test_module.__package__)
            .joinpath("schemas")
            .joinpath("ogcapi")
            .joinpath("ogcapi-maps-1.bundled.json")
        )
        ogcapi_tiles_schema = json.loads(open(ogcapi_tiles_schema_path, "rb").read())
        if schema_name:
            schema = ogcapi_tiles_schema["components"]["schemas"][schema_name]
        elif response_name:
            schema = ogcapi_tiles_schema["components"]["responses"][response_name][
                "content"
            ]["application/json"]["schema"]
        else:
            assert False, "one of schema_name or response_name must be specified"
        schema["components"] = ogcapi_tiles_schema["components"]
        jsonschema.validate(json_doc, schema)

    def test_landingpage(self, app):
        resp = app.get("/ogcapi")
        assert resp.content_type == "application/json"
        expected_json = {
            "links": [
                {
                    "rel": "self",
                    "type": "application/json",
                    "title": "The JSON representation of the landing page for this OGC (geospatial) API Service providing links to the API definition, the conformance declaration and information about the data collections offered at this endpoint.",  # noqa
                    "href": "http://localhost/ogcapi?f=json",
                },
                {
                    "rel": "alternate",
                    "type": "text/html",
                    "title": "The HTML representation of the landing page for this OGC (geospatial) API Service providing links to the API definition, the conformance declaration and information about the data collections offered at this endpoint.",  # noqa
                    "href": "http://localhost/ogcapi?f=html",
                },
                {
                    "rel": "conformance",
                    "type": "application/json",
                    "title": "The JSON representation of the conformance declaration for this server listing the requirement classes implemented by this server",  # noqa
                    "href": "http://localhost/ogcapi/conformance?f=json",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/conformance",
                    "type": "application/json",
                    "title": "The JSON representation of the conformance declaration for this server listing the requirement classes implemented by this server",  # noqa
                    "href": "http://localhost/ogcapi/conformance?f=json",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/conformance",
                    "type": "text/html",
                    "title": "The HTML representation of the conformance declaration for this server listing the requirement classes implemented by this server",  # noqa
                    "href": "http://localhost/ogcapi/conformance?f=html",
                },
                {
                    "rel": "service-desc",
                    "type": "application/vnd.oai.openapi+json;version=3.0",
                    "title": "The JSON OpenAPI 3.0 document that describes the API offered at this endpoint",
                    "href": "http://localhost/ogcapi/api?f=json",
                },
                {
                    "rel": "service-doc",
                    "type": "text/html",
                    "title": "The HTML documentation of the API offered at this endpoint",
                    "href": "http://localhost/ogcapi/api?f=html",
                },
                {
                    "rel": "data",
                    "type": "application/json",
                    "title": "The JSON representation of the list of all data collections served from this endpoint",
                    "href": "http://localhost/ogcapi/collections?f=json",
                },
                {
                    "rel": "data",
                    "type": "text/html",
                    "title": "The HTML representation of the list of all data collections served from this endpoint",
                    "href": "http://localhost/ogcapi/collections?f=html",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/data",
                    "type": "application/json",
                    "title": "The JSON representation of the list of all data collections served from this endpoint",
                    "href": "http://localhost/ogcapi/collections?f=json",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/data",
                    "type": "text/html",
                    "title": "The HTML representation of the list of all data collections served from this endpoint",
                    "href": "http://localhost/ogcapi/collections?f=html",
                },
                {
                    "href": "http://localhost/ogcapi/map.png",
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                    "title": "Default map of the whole datase (as PNG)",
                    "type": "image/png",
                },
                {
                    "href": "http://localhost/ogcapi/map.jpg",
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                    "title": "Default map of the whole datase (as JPEG)",
                    "type": "image/jpeg",
                },
            ]
        }
        assert resp.json == expected_json

        self._test_links(app, resp.json)

        self._validate_response_against_schema(resp.json, schema_name="landingPage")

        resp = app.get("/ogcapi", {"f": "json"})
        assert resp.json == expected_json

        resp = app.get("/ogcapi", {}, {"Accept": "application/json"})
        assert resp.json == expected_json

        resp = app.get("/ogcapi", {"f": "html"})
        assert resp.content_type == "text/html"
        assert (
            b'<link rel="alternate" type="application/json" title="The JSON representation of the landing page for this OGC (geospatial) API Service providing links to the API definition, the conformance declaration and information about the data collections offered at this endpoint." href="http://localhost/ogcapi?f=json"/>'  # noqa
            in resp.body
        )
        assert (
            b'<link rel="canonical" href="http://localhost/ogcapi?f=html" /'
            in resp.body
        )
        assert (
            b'<link rel="conformance" type="application/json" title="The JSON representation of the conformance declaration for this server listing the requirement classes implemented by this server" href="http://localhost/ogcapi/conformance?f=json"/>'  # noqa
            in resp.body
        )
        assert (
            b'<link rel="http://www.opengis.net/def/rel/ogc/1.0/conformance" type="text/html" title="The HTML representation of the conformance declaration for this server listing the requirement classes implemented by this server" href="http://localhost/ogcapi/conformance?f=html"/>'  # noqa
            in resp.body
        )
        assert (
            b'<link rel="service-desc" type="application/vnd.oai.openapi+json;version=3.0" title="The JSON OpenAPI 3.0 document that describes the API offered at this endpoint" href="http://localhost/ogcapi/api?f=json"/>'  # noqa
            in resp.body
        )
        assert (
            b'<link rel="service-doc" type="text/html" title="The HTML documentation of the API offered at this endpoint" href="http://localhost/ogcapi/api?f=html"/>'  # noqa
            in resp.body
        )
        assert (
            b'<link rel="data" type="application/json" title="The JSON representation of the list of all data collections served from this endpoint" href="http://localhost/ogcapi/collections?f=json"/>'  # noqa
            in resp.body
        )
        assert (
            b'<link rel="data" type="text/html" title="The HTML representation of the list of all data collections served from this endpoint" href="http://localhost/ogcapi/collections?f=html"/>'  # noqa
            in resp.body
        )
        assert (
            b'<link rel="http://www.opengis.net/def/rel/ogc/1.0/data" type="application/json" title="The JSON representation of the list of all data collections served from this endpoint" href="http://localhost/ogcapi/collections?f=json"/>'  # noqa
            in resp.body
        )
        assert (
            b'<link rel="http://www.opengis.net/def/rel/ogc/1.0/data" type="text/html" title="The HTML representation of the list of all data collections served from this endpoint" href="http://localhost/ogcapi/collections?f=html"/>'  # noqa
            in resp.body
        )

        resp = app.get("/ogcapi", {}, {"Accept": "*/*, text/html"})
        assert resp.content_type == "text/html"

    def test_conformance(self, app):
        resp = app.get("/ogcapi/conformance")
        assert resp.content_type == "application/json"
        expected_json = {
            "conformsTo": [
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/html",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/json",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/landing-page",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/oas30",
                "http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/scaling",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/spatial-subsetting",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/crs",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/display-resolution",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/background",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/collection-map",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/collections-selection",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/png",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/jpeg",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/dataset-map",
            ]
        }
        assert resp.json == expected_json

        self._validate_response_against_schema(resp.json, schema_name="confClasses")

        resp = app.get("/ogcapi/conformance", {"f": "json"})
        assert resp.json == expected_json

        resp = app.get("/ogcapi/conformance", {}, {"Accept": "application/json"})
        assert resp.json == expected_json

        resp = app.get("/ogcapi/conformance", {"f": "html"})
        assert resp.content_type == "text/html"
        for klass in expected_json["conformsTo"]:
            assert (
                f'<a title="{klass}" href="{klass}">{klass}</a>'.encode("utf-8")
                in resp.body
            )

        resp = app.get("/ogcapi/conformance", {}, {"Accept": "*/*, text/html"})
        assert resp.content_type == "text/html"

    def test_api(self, app):
        resp = app.get("/ogcapi/api")
        assert (
            resp.headers["Content-type"]
            == "application/vnd.oai.openapi+json;version=3.0"
        )

        expected_json = {
            "openapi": "3.0.2",
            "tags": [
                {
                    "name": "server",
                    "description": "Minimal MapProxy example",
                    "externalDocs": {
                        "description": "information",
                        "url": "http://example.com",
                    },
                }
            ],
            "info": {
                "version": __version__,
                "title": "MapProxy OGCAPI",
                "description": "Minimal MapProxy example",
                "x-keywords": ["OGC API", "Demo"],
                "termsOfService": "http://example.com",
                "license": {
                    "name": "Do what you want",
                    "url": "http://example.com",
                },
                "x-OGC-limits": {
                    "maps": {
                        "maxWidth": 40000,
                        "maxHeight": 40000,
                        "maxPixels": 16000000,
                    }
                },
            },
            "servers": [
                {
                    "url": "http://localhost/ogcapi",
                    "description": "Minimal MapProxy example",
                }
            ],
            "paths": {
                "/": {
                    "get": {
                        "summary": "Landing page",
                        "description": "Landing page",
                        "tags": ["server"],
                        "operationId": "getLandingPage",
                        "parameters": [{"$ref": "#/components/parameters/f"}],
                        "responses": {
                            "200": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/LandingPage"  # noqa
                            },
                            "400": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/InvalidParameter"  # noqa
                            },
                            "500": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/ServerError"  # noqa
                            },
                        },
                    }
                },
                "/api": {
                    "get": {
                        "summary": "This document",
                        "description": "This document",
                        "tags": ["server"],
                        "operationId": "getOpenapi",
                        "parameters": [
                            {"$ref": "#/components/parameters/f"},
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
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/API"  # noqa
                            },
                            "400": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/InvalidParameter"  # noqa
                            },
                            "500": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/ServerError"  # noqa
                            },
                        },
                    }
                },
                "/collections": {
                    "get": {
                        "summary": "Retrieve the description of the collections available from this service.",
                        "description": "Collections",
                        "tags": ["server"],
                        "operationId": "getCollections",
                        "parameters": [{"$ref": "#/components/parameters/f"}],
                        "responses": {
                            "200": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/CollectionsList"  # noqa
                            },
                            "400": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/InvalidParameter"  # noqa
                            },
                            "500": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/ServerError"  # noqa
                            },
                        },
                    }
                },
                "/collections/{collectionId}": {
                    "get": {
                        "summary": "Retrieve the description of a collection available from this service.",
                        "description": "Collection",
                        "tags": ["server"],
                        "operationId": "getCollection",
                        "parameters": [
                            {"$ref": "#/components/parameters/collectionId"},
                            {"$ref": "#/components/parameters/f"},
                        ],
                        "responses": {
                            "200": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/Collection"  # noqa
                            },
                            "400": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/InvalidParameter"  # noqa
                            },
                            "404": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/NotFound"  # noqa
                            },
                            "500": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/ServerError"  # noqa
                            },
                        },
                    }
                },
                "/collections/{collectionId}/map": {
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
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/crs"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/bbox"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/bbox-crs"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/center"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/center-crs"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/subset"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/subset-crs"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/scale-denominator"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/bgcolor"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/transparent"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/mm-per-pixel"  # noqa
                            },
                        ],
                        "responses": {
                            "200": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/Map"  # noqa
                            },
                            "204": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/EmptyMap"  # noqa
                            },
                            "400": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/InvalidParameter"  # noqa
                            },
                            "404": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/NotFound"  # noqa
                            },
                            "500": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/ServerError"  # noqa
                            },
                        },
                    }
                },
                "/map": {
                    "get": {
                        "summary": "Retrieve the default map for the whole dataset.",
                        "description": "Map",
                        "tags": ["server"],
                        "operationId": "getDatasetMap",
                        "parameters": [
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/collections"  # noqa
                            },
                            {"$ref": "#/components/parameters/f_img"},
                            {"$ref": "#/components/parameters/width"},
                            {"$ref": "#/components/parameters/height"},
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/crs"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/bbox"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/bbox-crs"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/center"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/center-crs"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/subset"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/subset-crs"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/scale-denominator"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/bgcolor"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/transparent"  # noqa
                            },
                            {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/parameters/mm-per-pixel"  # noqa
                            },
                        ],
                        "responses": {
                            "200": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/Map"  # noqa
                            },
                            "400": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/InvalidParameter"  # noqa
                            },
                            "500": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/ServerError"  # noqa
                            },
                        },
                    }
                },
                "/conformance": {
                    "get": {
                        "summary": "API conformance definition",
                        "description": "API conformance definition",
                        "tags": ["server"],
                        "operationId": "getConformanceDeclaration",
                        "parameters": [{"$ref": "#/components/parameters/f"}],
                        "responses": {
                            "200": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/Conformance"  # noqa
                            },
                            "400": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/InvalidParameter"  # noqa
                            },
                            "500": {
                                "$ref": "https://schemas.opengis.net/ogcapi/maps/part1/1.0/openapi/ogcapi-maps-1.bundled.json#/components/responses/ServerError"  # noqa
                            },
                        },
                    }
                },
            },
            "components": {
                "responses": {"200": {"description": "Successful operation"}},
                "parameters": {
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
                            "enum": ["test", "test_without_nominal_scale"],
                        },
                    },
                    "f_img": {
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
                    },
                    "width": {
                        "name": "width",
                        "in": "query",
                        "description": "Width of the map in pixels. If omitted and `height` is specified, defaults to the width maintaining a 1:1 aspect ratio. If both `width` and `height` are omitted, the server will select default dimensions. When used together with the `center` and/or `scale-denominator` parameter, `width` takes on a subsetting role rather than scaling (resampling), defining the horizontal portion of the map to subset based on the scale (native scale, or specified by `scale-denominator`) and display resolution (0.28 mm/pixel, or specified by `mm-per-pixel`).",  # noqa
                        "required": False,
                        "style": "form",
                        "explode": False,
                        "schema": {"type": "integer", "maximum": 40000},
                    },
                    "height": {
                        "name": "height",
                        "in": "query",
                        "description": "Height of the map in pixels. If omitted and `width` is specified, defaults to the height maintaining a 1:1 aspect ratio. If both `width` and `height` are omitted, the server will select default dimensions. When used together with the `center` and/or `scale-denominator` parameter, `height` takes on a subsetting role rather than scaling (resampling), defining the vertical portion of the map to subset based on the scale (native scale, or specified by `scale-denominator`) and display resolution (0.28 mm/pixel, or specified by `mm-per-pixel`).",  # noqa
                        "required": False,
                        "style": "form",
                        "explode": False,
                        "schema": {"type": "integer", "maximum": 40000},
                    },
                },
            },
        }
        assert resp.json == expected_json

        if sys.version_info >= (3, 10):
            # jsonschema.validate() hangs for py 3.9
            openapi_schema_path = (
                importlib_resources.files(test_module.__package__)
                .joinpath("schemas")
                .joinpath("openapi")
                .joinpath("openapi-3.0.x.json")
            )
            openapi_schema = json.loads(open(openapi_schema_path, "rb").read())
            jsonschema.validate(resp.json, openapi_schema)

        resp = app.get("/ogcapi/api", {"f": "html"})
        assert resp.content_type == "text/html"
        assert (
            b"""SwaggerUIBundle({\n        url: \'http://localhost/ogcapi/api?f=json\'"""
            in resp.body
        )

        resp = app.get("/ogcapi/api", {}, {"Accept": "*/*, text/html"})
        assert resp.content_type == "text/html"

        resp = app.get("/ogcapi/api", {"f": "html", "ui": "swagger"})
        assert resp.content_type == "text/html"
        assert (
            b"""SwaggerUIBundle({\n        url: \'http://localhost/ogcapi/api?f=json\'"""
            in resp.body
        )

        resp = app.get("/ogcapi/api", {"f": "html", "ui": "redoc"})
        assert resp.content_type == "text/html"
        assert (
            b"""<redoc spec-url=\'http://localhost/ogcapi/api?f=json\'>""" in resp.body
        )

    def test_api_errors(self, app):
        resp = app.get("/ogcapi/api", {"f": "html", "ui": "invalid"}, status=400)
        assert resp.content_type == "text/html"
        assert b"<p>Invalid value for ui query parameter</p>" in resp.body

        resp = app.get("/ogcapi/api", {"f": "json", "ui": "swagger"}, status=400)
        assert resp.content_type == "application/json"
        assert resp.json == {
            "detail": "ui query parameter can only be used with HTML output",
            "status": 400,
            "title": "OGCAPI",
            "type": "Invalid Parameter",
        }

    def test_collections(self, app):
        resp = app.get("/ogcapi/collections")
        assert resp.content_type == "application/json"
        expected_json = {
            "collections": [
                {
                    "attribution": "[![Copyright 2025 "
                    "TyCoon](http://example.com/logo.png](http://example.com)",
                    "attributionMediaType": "text/markdown",
                    "crs": [
                        "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                        "http://www.opengis.net/def/crs/EPSG/0/4326",
                        "http://www.opengis.net/def/crs/EPSG/0/3857",
                    ],
                    "dataType": "map",
                    "description": "abstract",
                    "extent": {"spatial": {"bbox": [[-180, -90, 180, 90]]}},
                    "id": "test",
                    "links": [
                        {
                            "href": "http://localhost/ogcapi/collections/test?f=json",
                            "rel": "self",
                            "title": "The JSON representation of this data "
                            "collection",
                            "type": "application/json",
                        },
                        {
                            "href": "http://localhost/ogcapi/collections/test?f=html",
                            "rel": "alternate",
                            "title": "The HTML representation of this data "
                            "collection",
                            "type": "text/html",
                        },
                        {
                            "href": "http://localhost/ogcapi/collections/test/map.png",
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                            "title": "Default map (as PNG)",
                            "type": "image/png",
                        },
                        {
                            "href": "http://localhost/ogcapi/collections/test/map.jpg",
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                            "title": "Default map (as JPEG)",
                            "type": "image/jpeg",
                        },
                    ],
                    "storageCrs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                    "title": "title",
                }
            ],
            "links": [
                {
                    "href": "http://localhost/ogcapi/collections?f=json",
                    "rel": "self",
                    "title": "The JSON representation of the list of all data "
                    "collections served from this endpoint",
                    "type": "application/json",
                },
                {
                    "href": "http://localhost/ogcapi/collections?f=html",
                    "rel": "alternate",
                    "title": "The HTML representation of the list of all data "
                    "collections served from this endpoint",
                    "type": "text/html",
                },
            ],
        }
        resp_json = resp.json
        resp_json["collections"].pop()
        assert resp_json == expected_json

        self._test_links(app, resp.json)

        if sys.version_info >= (3, 10):
            # jsonschema.validate() hangs for py 3.9

            ogcapi_maps_schema_path = (
                importlib_resources.files(test_module.__package__)
                .joinpath("schemas")
                .joinpath("ogcapi")
                .joinpath("ogcapi-maps-1.bundled.json")
            )
            ogcapi_maps_schema = json.loads(open(ogcapi_maps_schema_path, "rb").read())
            schema = ogcapi_maps_schema["components"]["schemas"]["collections"]
            schema["components"] = ogcapi_maps_schema["components"]
            # Cf https://github.com/opengeospatial/ogcapi-maps/issues/140
            schema["components"]["schemas"]["collectionDesc"]["properties"]["extent"][
                "$ref"
            ] = "#/components/schemas/extent"
            jsonschema.validate(resp.json, schema)

        resp = app.get("/ogcapi/collections", {"f": "json"})
        assert resp.content_type == "application/json"
        resp_json = resp.json
        resp_json["collections"].pop()
        assert resp_json == expected_json

        resp = app.get("/ogcapi/collections", {}, {"Accept": "application/json"})
        assert resp.content_type == "application/json"
        resp_json = resp.json
        resp_json["collections"].pop()
        assert resp_json == expected_json

        resp = app.get("/ogcapi/collections", {"f": "html"})
        assert resp.content_type == "text/html"
        assert (
            b"""<td data-label="name">\n                    <a  title="title"\n                      href="http://localhost/ogcapi/collections/test">\n                      <span>title</span></a>\n                  </td>\n                  <td data-label="description">\n                    abstract\n                  </td>\n                </tr>"""  # noqa
            in resp.body
        )

        resp = app.get("/ogcapi/collections", {}, {"Accept": "*/*, text/html"})
        assert resp.content_type == "text/html"

    def test_collection(self, app):
        resp = app.get("/ogcapi/collections/test")
        assert resp.content_type == "application/json"
        expected_json = {
            "attribution": "[![Copyright 2025 "
            "TyCoon](http://example.com/logo.png](http://example.com)",
            "attributionMediaType": "text/markdown",
            "crs": [
                "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                "http://www.opengis.net/def/crs/EPSG/0/4326",
                "http://www.opengis.net/def/crs/EPSG/0/3857",
            ],
            "dataType": "map",
            "description": "abstract",
            "extent": {"spatial": {"bbox": [[-180, -90, 180, 90]]}},
            "id": "test",
            "links": [
                {
                    "href": "http://localhost/ogcapi/collections/test?f=json",
                    "rel": "self",
                    "title": "The JSON representation of this data " "collection",
                    "type": "application/json",
                },
                {
                    "href": "http://localhost/ogcapi/collections/test?f=html",
                    "rel": "alternate",
                    "title": "The HTML representation of this data " "collection",
                    "type": "text/html",
                },
                {
                    "href": "http://localhost/ogcapi/collections/test/map.png",
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                    "title": "Default map (as PNG)",
                    "type": "image/png",
                },
                {
                    "href": "http://localhost/ogcapi/collections/test/map.jpg",
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                    "title": "Default map (as JPEG)",
                    "type": "image/jpeg",
                },
            ],
            "storageCrs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
            "title": "title",
        }

        assert resp.json == expected_json

        self._test_links(app, resp.json)

        if sys.version_info >= (3, 10):
            # jsonschema.validate() hangs for py 3.9

            ogcapi_maps_schema_path = (
                importlib_resources.files(test_module.__package__)
                .joinpath("schemas")
                .joinpath("ogcapi")
                .joinpath("ogcapi-maps-1.bundled.json")
            )
            ogcapi_maps_schema = json.loads(open(ogcapi_maps_schema_path, "rb").read())
            schema = ogcapi_maps_schema["components"]["schemas"]["collectionDesc"]
            schema["components"] = ogcapi_maps_schema["components"]
            # Cf https://github.com/opengeospatial/ogcapi-maps/issues/140
            schema["components"]["schemas"]["collectionDesc"]["properties"]["extent"][
                "$ref"
            ] = "#/components/schemas/extent"
            jsonschema.validate(resp.json, schema)

        resp = app.get("/ogcapi/collections/test", {"f": "json"})
        assert resp.json == expected_json

        resp = app.get("/ogcapi/collections/test", {}, {"Accept": "application/json"})
        assert resp.json == expected_json

        resp = app.get("/ogcapi/collections/test", {"f": "html"})
        assert resp.content_type == "text/html"
        assert (
            b"""<a title="http://www.opengis.net/def/rel/ogc/1.0/map" href="http://localhost/ogcapi/collections/test/map.png">"""  # noqa
            in resp.body
        )

        resp = app.get("/ogcapi/collections/invalid", status=404)
        assert resp.content_type == "application/json"
        assert resp.json == {
            "detail": "Collection not found",
            "status": 404,
            "title": "OGCAPI",
            "type": "Not Found",
        }

    @pytest.mark.parametrize("extension", ["jpg", "jpeg"])
    def test_collection_map_jpeg(self, app, extension):
        with tmp_image((1, 1), format="jpeg", color=(255, 0, 0)) as img:
            img_bytes = img.read()

        expected_req = (
            {
                "path": r"/service?layers=test&bbox=-0.125764139776733,-0.125764139776733,0.125764139776733,0.125764139776733&width=1&height=1&srs=EPSG%3A4326&format=image%2Fjpeg&request=GetMap&version=1.1.1&service=WMS&styles="  # noqa
            },
            {"body": img_bytes, "headers": {"content-type": "image/jpeg"}},
        )
        with mock_httpd(
            ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
        ):
            resp = app.get(
                f"/ogcapi/collections/test/map.{extension}", {"width": 1, "height": 1}
            )
            assert resp.content_type == "image/jpeg"
            img = Image.open(BytesIO(resp.body))
            assert img.format == "JPEG"
            assert img.width == 1
            assert img.height == 1
            assert img.getextrema() == ((254, 254), (0, 0), (0, 0))

    # See https://docs.ogc.org/is/20-058/20-058.html#_56e245b6-53bf-4996-b579-062598191edd Table 9
    @pytest.mark.parametrize(
        "query_params,width,height,extent,wms_width,wms_height,wms_bbox,wms_srs",
        [
            # Test crs
            (
                {"crs": "EPSG:3857"},
                1024,
                1024,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                1024,
                1024,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                "EPSG%3A3857",
            ),
            # Test bbox-crs
            (
                {
                    "width": 2,
                    "height": 1,
                    "bbox": "-90,-180,90,180",
                    "bbox-crs": "http://www.opengis.net/def/crs/EPSG/0/4326",
                },
                2,
                1,
                "-180,-90,180,90",
                2,
                1,
                "-180,-90,180,90",
                "EPSG%3A4326",
            ),
            # No params. Table 5
            (
                {},
                1024,
                512,
                "-180,-90,180,90",
                1024,
                512,
                "-180,-90,180,90",
                "EPSG%3A4326",
            ),
            # Line 1 of Table 9
            (
                {"width": 2},
                2,
                1,
                "-0.25152827955346602,-0.12576413977673301,0.25152827955346602,0.12576413977673301",
                2,
                1,
                "-0.25152827955346602,-0.12576413977673301,0.25152827955346602,0.12576413977673301",
                "EPSG%3A4326",
            ),
            # Line 1 of Table 9
            (
                {"height": 1},
                2,
                1,
                "-0.25152827955346602,-0.12576413977673301,0.25152827955346602,0.12576413977673301",
                2,
                1,
                "-0.25152827955346602,-0.12576413977673301,0.25152827955346602,0.12576413977673301",
                "EPSG%3A4326",
            ),
            # Line 1 of Table 9
            (
                {"width": 3, "height": 1},
                3,
                1,
                "-0.37729241933019902,-0.12576413977673301,0.37729241933019902,0.12576413977673301",
                3,
                1,
                "-0.37729241933019902,-0.12576413977673301,0.37729241933019902,0.12576413977673301",
                "EPSG%3A4326",
            ),
            # Line 2 of Table 9
            (
                {
                    "bbox": "-0.25152827955346602,-0.12576413977673301,0.25152827955346602,0.12576413977673301"
                },
                1024,
                512,
                "-0.25152827955346602,-0.12576413977673301,0.25152827955346602,0.12576413977673301",
                1024,
                512,
                "-0.25152827955346602,-0.12576413977673301,0.25152827955346602,0.12576413977673301",
                "EPSG%3A4326",
            ),
            # Line 3 of Table 9 + test center-crs
            (
                {"center": "49,2", "center-crs": "[EPSG:4326]"},
                1024,
                512,
                "-126.7824791313746,-15.3912395656873,130.7824791313746,113.3912395656873",
                1024,
                420,
                "-126.7824791313746,-15.3912395656873,130.7824791313746,90",
                "EPSG%3A4326",
            ),
            # Line 4 of Table 9 with both width and height
            (
                {"center": "2,49", "width": 2, "height": 1},
                2,
                1,
                "1.7484717204465339,48.874235860223266,2.2515282795534661,49.125764139776734",
                2,
                1,
                "1.7484717204465339,48.874235860223266,2.2515282795534661,49.125764139776734",
                "EPSG%3A4326",
            ),
            # Line 4 of Table 9 with width
            (
                {
                    "center": "2,49",
                    "width": 2,
                },
                2,
                1,
                "1.7484717204465339,48.874235860223266,2.2515282795534661,49.125764139776734",
                2,
                1,
                "1.7484717204465339,48.874235860223266,2.2515282795534661,49.125764139776734",
                "EPSG%3A4326",
            ),
            # Line 4 of Table 9 with height
            (
                {
                    "center": "2,49",
                    "height": 1,
                },
                2,
                1,
                "1.7484717204465339,48.874235860223266,2.2515282795534661,49.125764139776734",
                2,
                1,
                "1.7484717204465339,48.874235860223266,2.2515282795534661,49.125764139776734",
                "EPSG%3A4326",
            ),
            # Line 5 of Table 9
            (
                {"scale-denominator": 50000000},
                1024,
                512,
                "-64.3912395656873,-32.19561978284365,64.3912395656873,32.19561978284365",
                1024,
                512,
                "-64.3912395656873,-32.19561978284365,64.3912395656873,32.19561978284365",
                "EPSG%3A4326",
            ),
            # Line 6 of Table 9
            (
                {"scale-denominator": 50000000, "center": "0,0"},
                1024,
                512,
                "-64.3912395656873,-32.19561978284365,64.3912395656873,32.19561978284365",
                1024,
                512,
                "-64.3912395656873,-32.19561978284365,64.3912395656873,32.19561978284365",
                "EPSG%3A4326",
            ),
            # Line 6 of Table 9
            (
                {"scale-denominator": 50000000, "center": "2,49"},
                1024,
                512,
                "-62.3912395656873,16.80438021715635,66.3912395656873,81.19561978284365",
                1024,
                512,
                "-62.3912395656873,16.80438021715635,66.3912395656873,81.19561978284365",
                "EPSG%3A4326",
            ),
            # Line 7 of Table 9 with width
            (
                {"scale-denominator": 50000000, "width": 10},
                10,
                5,
                "-0.6288206988836651,-0.31441034944183255,0.6288206988836651,0.31441034944183255",
                10,
                5,
                "-0.6288206988836651,-0.31441034944183255,0.6288206988836651,0.31441034944183255",
                "EPSG%3A4326",
            ),
            # Line 7 of Table with height
            (
                {"scale-denominator": 50000000, "height": 5},
                10,
                5,
                "-0.6288206988836651,-0.31441034944183255,0.6288206988836651,0.31441034944183255",
                10,
                5,
                "-0.6288206988836651,-0.31441034944183255,0.6288206988836651,0.31441034944183255",
                "EPSG%3A4326",
            ),
            # Line 7 of Table 9 with both width and height
            (
                {"scale-denominator": 50000000, "width": 10, "height": 5},
                10,
                5,
                "-0.6288206988836651,-0.31441034944183255,0.6288206988836651,0.31441034944183255",
                10,
                5,
                "-0.6288206988836651,-0.31441034944183255,0.6288206988836651,0.31441034944183255",
                "EPSG%3A4326",
            ),
            # Line 7 of Table 9 with both width and height
            (
                {"scale-denominator": 50000000, "width": 10, "height": 4},
                10,
                4,
                "-0.6288206988836651,-0.25152827955346602,0.6288206988836651,0.25152827955346602",
                10,
                4,
                "-0.6288206988836651,-0.25152827955346602,0.6288206988836651,0.25152827955346602",
                "EPSG%3A4326",
            ),
            # Line 8 of Table 9: this case is equivalent to WMS GetMap query.
            (
                {"bbox": "0.5,1.5,2.5,3.5", "width": 2, "height": 1},
                2,
                1,
                "0.5,1.5,2.5,3.5",
                2,
                1,
                "0.5,1.5,2.5,3.5",
                "EPSG%3A4326",
            ),
            # Line 9 of Table 9
            (
                {"scale-denominator": 50000000, "bbox": "-180,-90,180,90"},
                1024,
                512,
                "-180,-90,180,90",
                2863,
                1431,
                "-180,-90,180,90",
                "EPSG%3A4326",
            ),
            # Line 9 of Table 9
            (
                {
                    "scale-denominator": 50000000,
                    "bbox": "-64.3912395656873,-32.19561978284365,64.3912395656873,32.19561978284365",
                },
                1024,
                512,
                "-64.3912395656873,-32.19561978284365,64.3912395656873,32.19561978284365",
                1024,
                512,
                "-64.3912395656873,-32.19561978284365,64.3912395656873,32.19561978284365",
                "EPSG%3A4326",
            ),
            # Line 10 of Table 9, with width
            (
                {"scale-denominator": 50000000, "center": "2,49", "width": 10},
                10,
                5,
                "1.3711793011163349,48.685589650558164,2.6288206988836649,49.314410349441836",
                10,
                5,
                "1.3711793011163349,48.685589650558164,2.6288206988836649,49.314410349441836",
                "EPSG%3A4326",
            ),
            # Line 10 of Table 9, with height
            (
                {"scale-denominator": 50000000, "center": "2,49", "height": 5},
                10,
                5,
                "1.3711793011163349,48.685589650558164,2.6288206988836649,49.314410349441836",
                10,
                5,
                "1.3711793011163349,48.685589650558164,2.6288206988836649,49.314410349441836",
                "EPSG%3A4326",
            ),
            # Line 10 of Table 9, with both width and height
            (
                {
                    "scale-denominator": 50000000,
                    "center": "2,49",
                    "width": 11,
                    "height": 5,
                },
                11,
                5,
                "1.3082972312279684,48.685589650558164,2.6917027687720316,49.314410349441836",
                11,
                5,
                "1.3082972312279684,48.685589650558164,2.6917027687720316,49.314410349441836",
                "EPSG%3A4326",
            ),
            # Test mm-per-pixel
            (
                {
                    "scale-denominator": 50000000,
                    "bbox": "-180,-90,180,90",
                    "mm-per-pixel": 0.28,
                },
                1024,
                512,
                "-180,-90,180,90",
                2863,
                1431,
                "-180,-90,180,90",
                "EPSG%3A4326",
            ),
            # Test mm-per-pixel
            (
                {
                    "scale-denominator": 50000000,
                    "bbox": "-180,-90,180,90",
                    "mm-per-pixel": 0.56,
                },
                1024,
                512,
                "-180,-90,180,90",
                1431,
                716,
                "-180,-90,180,90",
                "EPSG%3A4326",
            ),
            # Test subset
            (
                {"subset": "lon(-90:90),lat(-45:45)"},
                1024,
                512,
                "-90,-45,90,45",
                1024,
                512,
                "-90,-45,90,45",
                "EPSG%3A4326",
            ),
            # Test subset-crs
            (
                {
                    "subset": "E(-20037508.342789244:20037508.342789244),N(-20037508.342789244:20037508.342789244)",
                    "subset-crs": "EPSG:3857",
                },
                1024,
                512,
                "-180,-85.051128779806604,180,85.051128779806604",
                1024,
                484,
                "-180,-85.051128779806604,180,85.051128779806604",
                "EPSG%3A4326",
            ),
            # Test transparent
            (
                {"center": "49,2", "center-crs": "EPSG:4326", "transparent": "false"},
                1024,
                512,
                "-126.7824791313746,-15.3912395656873,130.7824791313746,113.3912395656873",
                1024,
                420,
                "-126.7824791313746,-15.3912395656873,130.7824791313746,90",
                "EPSG%3A4326",
            ),
            # Test bgcolor W3C color
            (
                {"center": "49,2", "center-crs": "EPSG:4326", "bgcolor": "green"},
                1024,
                512,
                "-126.7824791313746,-15.3912395656873,130.7824791313746,113.3912395656873",
                1024,
                420,
                "-126.7824791313746,-15.3912395656873,130.7824791313746,90",
                "EPSG%3A4326",
            ),
            # Test bgcolor RGB in hex
            (
                {"center": "49,2", "center-crs": "EPSG:4326", "bgcolor": "0x123456"},
                1024,
                512,
                "-126.7824791313746,-15.3912395656873,130.7824791313746,113.3912395656873",
                1024,
                420,
                "-126.7824791313746,-15.3912395656873,130.7824791313746,90",
                "EPSG%3A4326",
            ),
            # Test bgcolor ARGB in hex
            (
                {"center": "49,2", "center-crs": "EPSG:4326", "bgcolor": "0x78123456"},
                1024,
                512,
                "-126.7824791313746,-15.3912395656873,130.7824791313746,113.3912395656873",
                1024,
                420,
                "-126.7824791313746,-15.3912395656873,130.7824791313746,90",
                "EPSG%3A4326",
            ),
        ],
    )
    def test_collection_map_query_params(
        self,
        app,
        query_params,
        width,
        height,
        extent,
        wms_width,
        wms_height,
        wms_bbox,
        wms_srs,
    ):
        with tmp_image((width, height), format="png", color=(255, 0, 0)) as img:
            img_bytes = img.read()

        expected_req = (
            {
                "path": f"/service?layers=test&bbox={wms_bbox}&width={wms_width}&height={wms_height}&srs={wms_srs}&format=image%2Fpng&request=GetMap&version=1.1.1&service=WMS&styles="  # noqa
            },
            {"body": img_bytes, "headers": {"content-type": "image/png"}},
        )
        with mock_httpd(
            ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
        ):
            resp = app.get("/ogcapi/collections/test/map", query_params)
            assert resp.content_type == "image/png"
            assert resp.headers["Content-Bbox"] == extent
            if "crs" in query_params:
                assert (
                    resp.headers["Content-Crs"]
                    == "<" + SRS(query_params["crs"]).to_ogc_url() + ">"
                )
            else:
                assert "Content-Crs" not in resp.headers, query_params
            img = Image.open(BytesIO(resp.body))
            assert img.format == "PNG"
            assert img.width == width
            assert img.height == height
            if wms_srs == "EPSG%3A4326" and float(extent.split(",")[3]) > 90:
                if query_params.get("transparent", True):
                    if query_params.get("bgcolor", "") == "green":
                        assert img.getextrema() == (
                            (0, 255),
                            (0, 0x80),
                            (0, 0),
                            (0, 255),
                        )
                    elif query_params.get("bgcolor", "") == "0x123456":
                        assert img.getextrema() == (
                            (0x12, 255),
                            (0, 0x34),
                            (0, 0x56),
                            (0, 255),
                        )
                    elif query_params.get("bgcolor", "") == "0x78123456":
                        assert img.getextrema() == (
                            (0x12, 255),
                            (0, 0x34),
                            (0, 0x56),
                            (0x78, 255),
                        )
                    else:
                        assert img.getextrema() == (
                            (255, 255),
                            (0, 255),
                            (0, 255),
                            (0, 255),
                        )
                else:
                    assert img.getextrema() == ((255, 255), (0, 255), (0, 255))
            else:
                assert img.getextrema() == ((255, 255), (0, 0), (0, 0))

    def test_collection_map_no_param_but_source_returns_error(self, app):
        expected_req = (
            {
                "path": r"/service?layers=test&bbox=-180,-90,180,90&width=1024&height=512&srs=EPSG%3A4326&format=image%2Fpng&request=GetMap&version=1.1.1&service=WMS&styles="  # noqa
            },
            {"body": b"notanimage", "headers": {"content-type": "image/png"}},
        )
        with mock_httpd(
            ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
        ):
            resp = app.get("/ogcapi/collections/test/map?f=png", expect_errors=True)
            assert resp.content_type == "application/json"
            assert resp.json["status"] == 500

    @pytest.mark.parametrize(
        "query_params,detail",
        [
            ({"width": "invalid"}, "width is not an integer"),
            ({"width": 0}, "width must be strictly positive"),
            ({"height": "invalid"}, "height is not an integer"),
            ({"height": 0}, "height must be strictly positive"),
            ({"width": 40001}, "width=40001 exceeds max_width=40000"),
            ({"width": 40000}, "number of pixels 800000000 exceed max_pixels=16000000"),
            ({"width": 1, "height": 40001}, "height=40001 exceeds max_height=40000"),
            (
                {"width": 4001, "height": 4000},
                "number of pixels 16004000 exceed max_pixels=16000000",
            ),
            ({"crs": "invalid"}, "crs is not a valid CRS"),
            (
                {"crs": "http://www.opengis.net/def/crs/EPSG/0/32631"},
                "crs is incompatible with this layer",
            ),
            (
                {"bbox": "-180,-90,180,90", "bbox-crs": "invalid"},
                "bbox-crs is not a valid CRS",
            ),
            (
                {
                    "bbox": "-180,-90,180,90",
                    "bbox-crs": "http://www.opengis.net/def/crs/IAU/2015/30100",
                },
                "bbox cannot be reprojected from SRS IAU_2015:30100 ('IAU_2015:30100') to SRS EPSG:4326 ('EPSG:4326')",  # noqa
            ),
            (
                {"center": "0,0", "center-crs": "invalid"},
                "center-crs is not a valid CRS",
            ),
            (
                {
                    "center": "0,0",
                    "center-crs": "http://www.opengis.net/def/crs/IAU/2015/30100",
                },
                "center cannot be reprojected from SRS IAU_2015:30100 ('IAU_2015:30100') to SRS EPSG:4326 ('EPSG:4326')",  # noqa
            ),
            (
                {"subset": "lon(-180:180),lat(-90:90)", "subset-crs": "invalid"},
                "subset-crs is not a valid CRS",
            ),
            (
                {
                    "subset": "lon(-180:180),lat(-90:90)",
                    "subset-crs": "http://www.opengis.net/def/crs/IAU/2015/30100",
                },
                "subset cannot be reprojected from SRS IAU_2015:30100 ('IAU_2015:30100') to SRS EPSG:4326 ('EPSG:4326')",  # noqa
            ),
            (
                {"bbox": "-180,-90,180,90", "center": "0,0"},
                "bbox and center are mutually exclusive",
            ),
            (
                {"bbox": "-180,-90,180,90", "subset": "lon(-180:180),lat(-90:90)"},
                "(bbox or center) and subset are mutually exclusive",
            ),
            (
                {"center": "0,0", "subset": "lon(-180:180),lat(-90:90)"},
                "(bbox or center) and subset are mutually exclusive",
            ),
            ({"subset": "lon(-180:180)"}, "subset must include 2 axis"),
            (
                {"subset": "lon(-180:180),invalid(-90:90)"},
                "Unsupported axis name invalid in subset part invalid(-90:90)",
            ),
            (
                {"subset": "lon(-180:180),lat(-90)"},
                "Only intervals are supported in subset part lat(-90)",
            ),
            (
                {"subset": "lon(-180:180),lat(90:-90)"},
                "Invalid range in subset: first value must be less than second one",
            ),
            (
                {"subset": "lon(-180:180),lon(-180:180)"},
                "Axis name lon has been specified in multiple subset parts",
            ),
            (
                {"subset": "lon(-180:180),lat(invalid:90)"},
                "Non numeric value found in range of subset part lat(invalid:90)",
            ),
            ({"subset": "lon(-180:180),lat"}, "Invalid subset part lat"),
            ({"subset": "lon(-180:180),lat("}, "Invalid subset part lat("),
            ({"subset": "lon(-180:180),lat(-90:"}, "Invalid subset part lat(-90:"),
            (
                {"subset": "lon(-180:180),lat()"},
                "Invalid subset part lat()",
            ),
            ({"bbox": "-180,-90,180"}, "bbox must be a list of 4 or 6 numeric values"),
            (
                {"bbox": "-180,-90,180,invalid"},
                "bbox must be a list of 4 or 6 numeric values",
            ),
            (
                {"bbox": "-180,90,180,-90"},
                "bbox[2] must be greater than bbox[0] and bbox[3] must be greater than bbox[1]",
            ),
            (
                {"bbox": "180,-90,-180,90"},
                "bbox[2] must be greater than bbox[0] and bbox[3] must be greater than bbox[1]",
            ),
            ({"center": "0"}, "center must be a list of 2 numeric values"),
            ({"center": "0,invalid"}, "center must be a list of 2 numeric values"),
            (
                {"scale-denominator": "invalid"},
                "scale-denominator must be a strictly positive numeric value",
            ),
            (
                {"scale-denominator": 0},
                "scale-denominator must be a strictly positive numeric value",
            ),
            (
                {"bbox": "-180,-90,180,90", "scale-denominator": 100000, "width": 1024},
                "bbox and scale-denominator and (width/height) are mutually exclusive",
            ),
            ({"bgcolor": "invalid"}, "invalid value for bgcolor"),
            ({"bgcolor": "0x------"}, "invalid value for bgcolor"),
            ({"bgcolor": "0x--------"}, "invalid value for bgcolor"),
            ({"transparent": "invalid"}, "invalid value for transparent"),
            ({"f": "json"}, "Invalid value for f query parameter"),
            (
                {"mm-per-pixel": "invalid"},
                "mm-per-pixel must be a strictly positive numeric value",
            ),
            (
                {"mm-per-pixel": 0},
                "mm-per-pixel must be a strictly positive numeric value",
            ),
            ({"collections": "test"}, "Unknown query parameter collections"),
        ],
    )
    def test_collection_map_errors(self, app, query_params, detail):
        resp = app.get("/ogcapi/collections/test/map", query_params, expect_errors=True)
        assert resp.content_type == "application/json"
        assert resp.json["status"] == 400, resp.json
        assert detail in resp.json["detail"]

    def test_collection_map_invalid_collection(self, app):
        resp = app.get("/ogcapi/collections/invalid/map", status=404)
        assert resp.content_type == "application/json"
        assert resp.json == {
            "detail": "Collection not found",
            "status": 404,
            "title": "OGCAPI",
            "type": "Not Found",
        }

    # Test a WMS query such as the one sent by the OpenLayers widget in the
    # HTML response of a collection
    def test_collection_map_wms_query(self, app):
        with tmp_image((10, 5), format="png", color=(255, 0, 0)) as img:
            img_bytes = img.read()
        expected_req = (
            {
                "path": r"/service?layers=test&bbox=-180,-90,180,90&width=10&height=5&srs=EPSG%3A4326&format=image%2Fpng&request=GetMap&version=1.1.1&service=WMS&styles="  # noqa
            },
            {"body": img_bytes, "headers": {"content-type": "image/png"}},
        )
        with mock_httpd(
            ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
        ):
            resp = app.get(
                "/ogcapi/collections/test/map?layers=test&bbox=-180,-90,180,90&width=10&height=5&srs=EPSG%3A4326&format=image%2Fpng&request=GetMap&version=1.1.1&service=WMS&styles="  # noqa
            )
            assert resp.content_type == "image/png"

    def test_collection_dataset_map(self, app):
        with tmp_image((2, 1), format="png", color=(255, 0, 0)) as img:
            img_bytes = img.read()
        expected_req = (
            {
                "path": r"/service?layers=test&bbox=-0.251528279553466,-0.125764139776733,0.251528279553466,0.125764139776733&width=2&height=1&srs=EPSG%3A4326&format=image%2Fpng&request=GetMap&version=1.1.1&service=WMS&styles="  # noqa
            },
            {"body": img_bytes, "headers": {"content-type": "image/png"}},
        )
        with mock_httpd(
            ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
        ):
            resp = app.get("/ogcapi/map", {"width": 2, "height": 1})
            assert resp.content_type == "image/png"

    def test_collection_dataset_map_collections(self, app):
        with tmp_image((2, 1), format="png", color=(255, 0, 0)) as img:
            img_bytes = img.read()
        expected_req = (
            {
                "path": r"/service?layers=test&bbox=-0.251528279553466,-0.125764139776733,0.251528279553466,0.125764139776733&width=2&height=1&srs=EPSG%3A4326&format=image%2Fpng&request=GetMap&version=1.1.1&service=WMS&styles="  # noqa
            },
            {"body": img_bytes, "headers": {"content-type": "image/png"}},
        )
        with mock_httpd(
            ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
        ):
            resp = app.get(
                "/ogcapi/map", {"width": 2, "height": 1, "collections": "test"}
            )
            assert resp.content_type == "image/png"

    def test_collection_dataset_map_collections_error(self, app):
        resp = app.get("/ogcapi/map", {"collections": "invalid"}, expect_errors=True)
        assert resp.content_type == "application/json"
        assert resp.json["status"] == 400, resp.json
        assert resp.json["detail"] == "unknown collection invalid"


# Tests where only OGC API Tiles is enabled
class TestOGCAPITilesService(TestOGCAPIService):
    @pytest.fixture(scope="class")
    def config_file(self):
        return "ogcapitiles_service.yaml"

    def test_invalid_resource(self, app):
        app.get("/ogcapi/invalid", expect_errors=True, status=404)

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/ogcapi",
            "/ogcapi/api",
            "/ogcapi/conformance",
            "/ogcapi/collections",
            "/ogcapi/collections/test",
            "/ogcapi/tileMatrixSets",
            "/ogcapi/tileMatrixSets/WebMercatorQuad",
            "/ogcapi/collections/test/map/tiles",
            "/ogcapi/collections/test/map/tiles/WebMercatorQuad",
            "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/0/0.png",
        ],
    )
    def test_generic_errors(self, app, endpoint):
        resp = app.get(endpoint, {"unexpected": "true"}, status=400)
        assert resp.content_type == "application/json"
        assert resp.json == {
            "detail": "Unknown query parameter unexpected",
            "status": 400,
            "title": "OGCAPI",
            "type": "Bad Request",
        }

        resp = app.get(endpoint, {"f": "unexpected"}, status=400)
        assert resp.content_type == "application/json"
        assert resp.json == {
            "detail": "Invalid value for f query parameter",
            "status": 400,
            "title": "OGCAPI",
            "type": "Invalid Parameter",
        }

    def _validate_response_against_schema(
        self, json_doc, schema_name=None, response_name=None
    ):
        if sys.version_info < (3, 10):
            # jsonschema.validate() hangs for py 3.9
            return

        ogcapi_tiles_schema_path = (
            importlib_resources.files(test_module.__package__)
            .joinpath("schemas")
            .joinpath("ogcapi")
            .joinpath("ogcapi-tiles-1.bundled.json")
        )
        ogcapi_tiles_schema = json.loads(open(ogcapi_tiles_schema_path, "rb").read())
        if schema_name:
            schema = ogcapi_tiles_schema["components"]["schemas"][schema_name]
        elif response_name:
            schema = ogcapi_tiles_schema["components"]["responses"][response_name][
                "content"
            ]["application/json"]["schema"]
        else:
            assert False, "one of schema_name or response_name must be specified"
        schema["components"] = ogcapi_tiles_schema["components"]
        jsonschema.validate(json_doc, schema)

    def test_landingpage(self, app):
        resp = app.get("/ogcapi")
        assert resp.content_type == "application/json"
        expected_json = {
            "links": [
                {
                    "rel": "self",
                    "type": "application/json",
                    "title": "The JSON representation of the landing page for this OGC (geospatial) API Service providing links to the API definition, the conformance declaration and information about the data collections offered at this endpoint.",  # noqa
                    "href": "http://localhost/ogcapi?f=json",
                },
                {
                    "rel": "alternate",
                    "type": "text/html",
                    "title": "The HTML representation of the landing page for this OGC (geospatial) API Service providing links to the API definition, the conformance declaration and information about the data collections offered at this endpoint.",  # noqa
                    "href": "http://localhost/ogcapi?f=html",
                },
                {
                    "rel": "conformance",
                    "type": "application/json",
                    "title": "The JSON representation of the conformance declaration for this server listing the requirement classes implemented by this server",  # noqa
                    "href": "http://localhost/ogcapi/conformance?f=json",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/conformance",
                    "type": "application/json",
                    "title": "The JSON representation of the conformance declaration for this server listing the requirement classes implemented by this server",  # noqa
                    "href": "http://localhost/ogcapi/conformance?f=json",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/conformance",
                    "type": "text/html",
                    "title": "The HTML representation of the conformance declaration for this server listing the requirement classes implemented by this server",  # noqa
                    "href": "http://localhost/ogcapi/conformance?f=html",
                },
                {
                    "rel": "service-desc",
                    "type": "application/vnd.oai.openapi+json;version=3.0",
                    "title": "The JSON OpenAPI 3.0 document that describes the API offered at this endpoint",
                    "href": "http://localhost/ogcapi/api?f=json",
                },
                {
                    "rel": "service-doc",
                    "type": "text/html",
                    "title": "The HTML documentation of the API offered at this endpoint",
                    "href": "http://localhost/ogcapi/api?f=html",
                },
                {
                    "rel": "data",
                    "type": "application/json",
                    "title": "The JSON representation of the list of all data collections served from this endpoint",
                    "href": "http://localhost/ogcapi/collections?f=json",
                },
                {
                    "rel": "data",
                    "type": "text/html",
                    "title": "The HTML representation of the list of all data collections served from this endpoint",
                    "href": "http://localhost/ogcapi/collections?f=html",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/data",
                    "type": "application/json",
                    "title": "The JSON representation of the list of all data collections served from this endpoint",
                    "href": "http://localhost/ogcapi/collections?f=json",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/data",
                    "type": "text/html",
                    "title": "The HTML representation of the list of all data collections served from this endpoint",
                    "href": "http://localhost/ogcapi/collections?f=html",
                },
                {
                    "href": "http://localhost/ogcapi/tileMatrixSets?f=json",
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-schemes",
                    "title": "The list of supported tiling schemes (as JSON)",
                    "type": "application/json",
                },
                {
                    "href": "http://localhost/ogcapi/tileMatrixSets?f=html",
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-schemes",
                    "title": "The list of supported tiling schemes (as HTML)",
                    "type": "text/html",
                },
            ]
        }
        assert resp.json == expected_json

        self._test_links(app, resp.json)

        self._validate_response_against_schema(resp.json, schema_name="landingPage")

        resp = app.get("/ogcapi", {"f": "html"})
        assert resp.content_type == "text/html"
        assert (
            b'<link rel="http://www.opengis.net/def/rel/ogc/1.0/tiling-schemes" type="application/json" title="The list of supported tiling schemes (as JSON)" href="http://localhost/ogcapi/tileMatrixSets?f=json"/>'  # noqa
            in resp.body
        )

    def test_conformance(self, app):
        resp = app.get("/ogcapi/conformance")
        assert resp.content_type == "application/json"
        expected_json = {
            "conformsTo": [
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/html",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/json",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/landing-page",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/oas30",
                "http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections",
                "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/oas30",
                "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/tileset",
                "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/tilesets-list",
                "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/geodata-tilesets",
                "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/dataset-tilesets",
            ]
        }
        assert resp.json == expected_json

        self._validate_response_against_schema(resp.json, schema_name="confClasses")

    def test_api(self, app):
        resp = app.get("/ogcapi/api")
        assert (
            resp.headers["Content-type"]
            == "application/vnd.oai.openapi+json;version=3.0"
        )

        assert "/tileMatrixSets" in resp.json["paths"]

        openapi_schema_path = (
            importlib_resources.files(test_module.__package__)
            .joinpath("schemas")
            .joinpath("openapi")
            .joinpath("openapi-3.0.x.json")
        )
        openapi_schema = json.loads(open(openapi_schema_path, "rb").read())
        jsonschema.validate(resp.json, openapi_schema)

    def test_tileMatrixSets(self, app):
        resp = app.get("/ogcapi/tileMatrixSets")
        assert resp.content_type == "application/json"

        expected_json = {
            "tileMatrixSets": [
                {
                    "id": "GLOBAL_GEODETIC",
                    "title": "GLOBAL_GEODETIC",
                    "links": [
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "The JSON representation of the GLOBAL_GEODETIC tiling scheme definition",
                            "href": "http://localhost/ogcapi/tileMatrixSets/GLOBAL_GEODETIC?f=json",
                        },
                        {
                            "rel": "alternate",
                            "type": "text/html",
                            "title": "The HTML representation of the GLOBAL_GEODETIC tiling scheme definition",
                            "href": "http://localhost/ogcapi/tileMatrixSets/GLOBAL_GEODETIC?f=html",
                        },
                    ],
                },
                {
                    "id": "GLOBAL_MERCATOR",
                    "title": "GLOBAL_MERCATOR",
                    "links": [
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "The JSON representation of the GLOBAL_MERCATOR tiling scheme definition",
                            "href": "http://localhost/ogcapi/tileMatrixSets/GLOBAL_MERCATOR?f=json",
                        },
                        {
                            "rel": "alternate",
                            "type": "text/html",
                            "title": "The HTML representation of the GLOBAL_MERCATOR tiling scheme definition",
                            "href": "http://localhost/ogcapi/tileMatrixSets/GLOBAL_MERCATOR?f=html",
                        },
                    ],
                },
                {
                    "id": "WebMercatorQuad",
                    "title": "WebMercatorQuad",
                    "links": [
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "The JSON representation of the WebMercatorQuad tiling scheme definition",
                            "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=json",
                        },
                        {
                            "rel": "alternate",
                            "type": "text/html",
                            "title": "The HTML representation of the WebMercatorQuad tiling scheme definition",
                            "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=html",
                        },
                    ],
                    "uri": "http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad",
                },
            ]
        }
        assert resp.json == expected_json

        self._test_links(app, resp.json)

        self._validate_response_against_schema(
            resp.json, response_name="TileMatrixSetsList"
        )

        resp = app.get("/ogcapi/tileMatrixSets", {"f": "html"})
        assert resp.content_type == "text/html"
        assert (
            b'<a title="WebMercatorQuad" href="http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=html">WebMercatorQuad</a>'  # noqa
            in resp.body
        )

    def test_invalid_tilematrixset(self, app):
        app.get("/ogcapi/tileMatrixSets/invalid", expect_errors=True, status=404)

    def test_tilematrixset_WebMercatorQuad(self, app):
        resp = app.get("/ogcapi/tileMatrixSets/WebMercatorQuad")
        assert resp.content_type == "application/json"

        expected_json = {
            "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
            "id": "WebMercatorQuad",
            "tileMatrices": [
                {
                    "cellSize": 156543.03392804097,
                    "cornerOfOrigin": "topLeft",
                    "id": "0",
                    "matrixHeight": 1,
                    "matrixWidth": 1,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 559082264.0287178,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 78271.51696402048,
                    "cornerOfOrigin": "topLeft",
                    "id": "1",
                    "matrixHeight": 2,
                    "matrixWidth": 2,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 279541132.0143589,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 39135.75848201024,
                    "cornerOfOrigin": "topLeft",
                    "id": "2",
                    "matrixHeight": 4,
                    "matrixWidth": 4,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 139770566.00717944,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 19567.87924100512,
                    "cornerOfOrigin": "topLeft",
                    "id": "3",
                    "matrixHeight": 8,
                    "matrixWidth": 8,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 69885283.00358972,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 9783.93962050256,
                    "cornerOfOrigin": "topLeft",
                    "id": "4",
                    "matrixHeight": 16,
                    "matrixWidth": 16,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 34942641.50179486,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 4891.96981025128,
                    "cornerOfOrigin": "topLeft",
                    "id": "5",
                    "matrixHeight": 32,
                    "matrixWidth": 32,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 17471320.75089743,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 2445.98490512564,
                    "cornerOfOrigin": "topLeft",
                    "id": "6",
                    "matrixHeight": 64,
                    "matrixWidth": 64,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 8735660.375448715,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 1222.99245256282,
                    "cornerOfOrigin": "topLeft",
                    "id": "7",
                    "matrixHeight": 128,
                    "matrixWidth": 128,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 4367830.1877243575,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 611.49622628141,
                    "cornerOfOrigin": "topLeft",
                    "id": "8",
                    "matrixHeight": 256,
                    "matrixWidth": 256,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 2183915.0938621787,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 305.748113140705,
                    "cornerOfOrigin": "topLeft",
                    "id": "9",
                    "matrixHeight": 512,
                    "matrixWidth": 512,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 1091957.5469310894,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 152.8740565703525,
                    "cornerOfOrigin": "topLeft",
                    "id": "10",
                    "matrixHeight": 1024,
                    "matrixWidth": 1024,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 545978.7734655447,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 76.43702828517625,
                    "cornerOfOrigin": "topLeft",
                    "id": "11",
                    "matrixHeight": 2048,
                    "matrixWidth": 2048,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 272989.38673277234,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 38.21851414258813,
                    "cornerOfOrigin": "topLeft",
                    "id": "12",
                    "matrixHeight": 4096,
                    "matrixWidth": 4096,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 136494.69336638617,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 19.109257071294063,
                    "cornerOfOrigin": "topLeft",
                    "id": "13",
                    "matrixHeight": 8192,
                    "matrixWidth": 8192,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 68247.34668319309,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 9.554628535647032,
                    "cornerOfOrigin": "topLeft",
                    "id": "14",
                    "matrixHeight": 16384,
                    "matrixWidth": 16384,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 34123.67334159654,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 4.777314267823516,
                    "cornerOfOrigin": "topLeft",
                    "id": "15",
                    "matrixHeight": 32768,
                    "matrixWidth": 32768,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 17061.83667079827,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 2.388657133911758,
                    "cornerOfOrigin": "topLeft",
                    "id": "16",
                    "matrixHeight": 65536,
                    "matrixWidth": 65536,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 8530.918335399136,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 1.194328566955879,
                    "cornerOfOrigin": "topLeft",
                    "id": "17",
                    "matrixHeight": 131072,
                    "matrixWidth": 131072,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 4265.459167699568,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 0.5971642834779395,
                    "cornerOfOrigin": "topLeft",
                    "id": "18",
                    "matrixHeight": 262144,
                    "matrixWidth": 262144,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 2132.729583849784,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
                {
                    "cellSize": 0.29858214173896974,
                    "cornerOfOrigin": "topLeft",
                    "id": "19",
                    "matrixHeight": 524288,
                    "matrixWidth": 524288,
                    "pointOfOrigin": [-20037508.342789244, 20037508.342789244],
                    "scaleDenominator": 1066.364791924892,
                    "tileHeight": 256,
                    "tileWidth": 256,
                },
            ],
            "title": "WebMercatorQuad",
            "uri": "http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad",
            "wellKnownScaleSet": "http://www.opengis.net/def/wkss/OGC/1.0/GoogleMapsCompatible",
        }
        assert resp.json == expected_json

        self._test_links(app, resp.json)

        self._validate_response_against_schema(resp.json, response_name="TileMatrixSet")

        resp = app.get("/ogcapi/tileMatrixSets/WebMercatorQuad", {"f": "html"})
        assert resp.content_type == "text/html"
        assert b"CRS: <i>http://www.opengis.net/def/crs/EPSG/0/3857</i>" in resp.body
        assert (
            b"Uri: <i>http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad</i>"
            in resp.body
        )
        assert (
            b"Well Known Scale Set: <i>http://www.opengis.net/def/wkss/OGC/1.0/GoogleMapsCompatible</i>"
            in resp.body
        )

    def test_tilematrixset_GLOBAL_GEODETIC(self, app):
        resp = app.get("/ogcapi/tileMatrixSets/GLOBAL_GEODETIC")
        assert resp.content_type == "application/json"

        self._validate_response_against_schema(resp.json, response_name="TileMatrixSet")

    def test_tilesets(self, app):
        resp = app.get("/ogcapi/collections/test/map/tiles")
        assert resp.content_type == "application/json"

        expected_json = {
            "links": [
                {
                    "rel": "self",
                    "type": "application/json",
                    "title": "The JSON representation of the available map tilesets for test (as JSON)",
                    "href": "http://localhost/ogcapi/collections/test/map/tiles?f=json",
                },
                {
                    "rel": "alternate",
                    "type": "text/html",
                    "title": "The HTML representation of the available map tilesets for test (as HTML)",
                    "href": "http://localhost/ogcapi/collections/test/map/tiles?f=html",
                },
            ],
            "tilesets": [
                {
                    "title": "test with GLOBAL_GEODETIC tile matrix set",
                    "dataType": "map",
                    "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                    "links": [
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "application/json",
                            "title": "GLOBAL_GEODETIC definition (as JSON)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/GLOBAL_GEODETIC?f=json",
                        },
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "text/html",
                            "title": "GLOBAL_GEODETIC definition (as HTML)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/GLOBAL_GEODETIC?f=html",
                        },
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "GLOBAL_GEODETIC map tileset for test (as JSON)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/GLOBAL_GEODETIC?f=json",
                        },
                        {
                            "rel": "alternate",
                            "type": "text/html",
                            "title": "GLOBAL_GEODETIC map tileset for test (as HTML)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/GLOBAL_GEODETIC?f=html",
                        },
                        {
                            "rel": "item",
                            "type": "image/png",
                            "title": "GLOBAL_GEODETIC map tiles for test (as PNG)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/GLOBAL_GEODETIC/{tileMatrix}/{tileRow}/{tileCol}.png",  # noqa
                            "templated": True,
                        },
                        {
                            "rel": "item",
                            "type": "image/jpeg",
                            "title": "GLOBAL_GEODETIC map tiles for test (as JPEG)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/GLOBAL_GEODETIC/{tileMatrix}/{tileRow}/{tileCol}.jpg",  # noqa
                            "templated": True,
                        },
                    ],
                },
                {
                    "title": "test with GLOBAL_MERCATOR tile matrix set",
                    "dataType": "map",
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
                    "links": [
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "application/json",
                            "title": "GLOBAL_MERCATOR definition (as JSON)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/GLOBAL_MERCATOR?f=json",
                        },
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "text/html",
                            "title": "GLOBAL_MERCATOR definition (as HTML)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/GLOBAL_MERCATOR?f=html",
                        },
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "GLOBAL_MERCATOR map tileset for test (as JSON)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/GLOBAL_MERCATOR?f=json",
                        },
                        {
                            "rel": "alternate",
                            "type": "text/html",
                            "title": "GLOBAL_MERCATOR map tileset for test (as HTML)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/GLOBAL_MERCATOR?f=html",
                        },
                        {
                            "rel": "item",
                            "type": "image/png",
                            "title": "GLOBAL_MERCATOR map tiles for test (as PNG)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/GLOBAL_MERCATOR/{tileMatrix}/{tileRow}/{tileCol}.png",  # noqa
                            "templated": True,
                        },
                        {
                            "rel": "item",
                            "type": "image/jpeg",
                            "title": "GLOBAL_MERCATOR map tiles for test (as JPEG)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/GLOBAL_MERCATOR/{tileMatrix}/{tileRow}/{tileCol}.jpg",  # noqa
                            "templated": True,
                        },
                    ],
                },
                {
                    "title": "test with WebMercatorQuad tile matrix set",
                    "tileMatrixSetURI": "http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad",
                    "dataType": "map",
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
                    "links": [
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "application/json",
                            "title": "WebMercatorQuad definition (as JSON)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=json",
                        },
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "text/html",
                            "title": "WebMercatorQuad definition (as HTML)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=html",
                        },
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "WebMercatorQuad map tileset for test (as JSON)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/WebMercatorQuad?f=json",
                        },
                        {
                            "rel": "alternate",
                            "type": "text/html",
                            "title": "WebMercatorQuad map tileset for test (as HTML)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/WebMercatorQuad?f=html",
                        },
                        {
                            "rel": "item",
                            "type": "image/png",
                            "title": "WebMercatorQuad map tiles for test (as PNG)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/WebMercatorQuad/{tileMatrix}/{tileRow}/{tileCol}.png",  # noqa
                            "templated": True,
                        },
                        {
                            "rel": "item",
                            "type": "image/jpeg",
                            "title": "WebMercatorQuad map tiles for test (as JPEG)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/WebMercatorQuad/{tileMatrix}/{tileRow}/{tileCol}.jpg",  # noqa
                            "templated": True,
                        },
                    ],
                },
            ],
        }
        assert resp.json == expected_json

        self._test_links(app, resp.json)

        self._validate_response_against_schema(resp.json, response_name="TileSetsList")

        resp = app.get("/ogcapi/collections/test/map/tiles", {"f": "html"})
        assert resp.content_type == "text/html"

    def test_tilesets_invalid(self, app):
        app.get("/ogcapi/collections/invalid/map/tiles", expect_errors=True, status=404)

    def test_dataset_tilesets(self, app):
        resp = app.get("/ogcapi/map/tiles")
        assert resp.content_type == "application/json"

        expected_json = {
            "links": [
                {
                    "rel": "self",
                    "type": "application/json",
                    "title": "The JSON representation of the available map tilesets for the whole dataset (as JSON)",
                    "href": "http://localhost/ogcapi/map/tiles?f=json",
                },
                {
                    "rel": "alternate",
                    "type": "text/html",
                    "title": "The HTML representation of the available map tilesets for the whole dataset (as HTML)",
                    "href": "http://localhost/ogcapi/map/tiles?f=html",
                },
            ],
            "tilesets": [
                {
                    "title": "Whole dataset with GLOBAL_GEODETIC tile matrix set",
                    "dataType": "map",
                    "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                    "links": [
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "application/json",
                            "title": "GLOBAL_GEODETIC definition (as JSON)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/GLOBAL_GEODETIC?f=json",
                        },
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "text/html",
                            "title": "GLOBAL_GEODETIC definition (as HTML)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/GLOBAL_GEODETIC?f=html",
                        },
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "GLOBAL_GEODETIC map tileset for the whole dataset (as JSON)",
                            "href": "http://localhost/ogcapi/map/tiles/GLOBAL_GEODETIC?f=json",
                        },
                        {
                            "rel": "alternate",
                            "type": "text/html",
                            "title": "GLOBAL_GEODETIC map tileset for the whole dataset (as HTML)",
                            "href": "http://localhost/ogcapi/map/tiles/GLOBAL_GEODETIC?f=html",
                        },
                        {
                            "rel": "item",
                            "type": "image/png",
                            "title": "GLOBAL_GEODETIC map tiles for the whole dataset (as PNG)",
                            "href": "http://localhost/ogcapi/map/tiles/GLOBAL_GEODETIC/{tileMatrix}/{tileRow}/{tileCol}.png",  # noqa
                            "templated": True,
                        },
                        {
                            "rel": "item",
                            "type": "image/jpeg",
                            "title": "GLOBAL_GEODETIC map tiles for the whole dataset (as JPEG)",
                            "href": "http://localhost/ogcapi/map/tiles/GLOBAL_GEODETIC/{tileMatrix}/{tileRow}/{tileCol}.jpg",  # noqa
                            "templated": True,
                        },
                    ],
                },
                {
                    "title": "Whole dataset with GLOBAL_MERCATOR tile matrix set",
                    "dataType": "map",
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
                    "links": [
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "application/json",
                            "title": "GLOBAL_MERCATOR definition (as JSON)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/GLOBAL_MERCATOR?f=json",
                        },
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "text/html",
                            "title": "GLOBAL_MERCATOR definition (as HTML)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/GLOBAL_MERCATOR?f=html",
                        },
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "GLOBAL_MERCATOR map tileset for the whole dataset (as JSON)",
                            "href": "http://localhost/ogcapi/map/tiles/GLOBAL_MERCATOR?f=json",
                        },
                        {
                            "rel": "alternate",
                            "type": "text/html",
                            "title": "GLOBAL_MERCATOR map tileset for the whole dataset (as HTML)",
                            "href": "http://localhost/ogcapi/map/tiles/GLOBAL_MERCATOR?f=html",
                        },
                        {
                            "rel": "item",
                            "type": "image/png",
                            "title": "GLOBAL_MERCATOR map tiles for the whole dataset (as PNG)",
                            "href": "http://localhost/ogcapi/map/tiles/GLOBAL_MERCATOR/{tileMatrix}/{tileRow}/{tileCol}.png",  # noqa
                            "templated": True,
                        },
                        {
                            "rel": "item",
                            "type": "image/jpeg",
                            "title": "GLOBAL_MERCATOR map tiles for the whole dataset (as JPEG)",
                            "href": "http://localhost/ogcapi/map/tiles/GLOBAL_MERCATOR/{tileMatrix}/{tileRow}/{tileCol}.jpg",  # noqa
                            "templated": True,
                        },
                    ],
                },
                {
                    "title": "Whole dataset with WebMercatorQuad tile matrix set",
                    "tileMatrixSetURI": "http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad",
                    "dataType": "map",
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
                    "links": [
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "application/json",
                            "title": "WebMercatorQuad definition (as JSON)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=json",
                        },
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "text/html",
                            "title": "WebMercatorQuad definition (as HTML)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=html",
                        },
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "WebMercatorQuad map tileset for the whole dataset (as JSON)",
                            "href": "http://localhost/ogcapi/map/tiles/WebMercatorQuad?f=json",
                        },
                        {
                            "rel": "alternate",
                            "type": "text/html",
                            "title": "WebMercatorQuad map tileset for the whole dataset (as HTML)",
                            "href": "http://localhost/ogcapi/map/tiles/WebMercatorQuad?f=html",
                        },
                        {
                            "rel": "item",
                            "type": "image/png",
                            "title": "WebMercatorQuad map tiles for the whole dataset (as PNG)",
                            "href": "http://localhost/ogcapi/map/tiles/WebMercatorQuad/{tileMatrix}/{tileRow}/{tileCol}.png",  # noqa
                            "templated": True,
                        },
                        {
                            "rel": "item",
                            "type": "image/jpeg",
                            "title": "WebMercatorQuad map tiles for the whole dataset (as JPEG)",
                            "href": "http://localhost/ogcapi/map/tiles/WebMercatorQuad/{tileMatrix}/{tileRow}/{tileCol}.jpg",  # noqa
                            "templated": True,
                        },
                    ],
                },
            ],
        }
        assert resp.json == expected_json

        self._test_links(app, resp.json)

        self._validate_response_against_schema(resp.json, response_name="TileSetsList")

        resp = app.get("/ogcapi/map/tiles", {"f": "html"})
        assert resp.content_type == "text/html"

    def test_tileset(self, app):
        resp = app.get("/ogcapi/collections/test/map/tiles/WebMercatorQuad")
        assert resp.content_type == "application/json"

        expected_json = {
            "title": "test with WebMercatorQuad tile matrix set",
            "tileMatrixSetURI": "http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad",
            "dataType": "map",
            "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
            "links": [
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                    "type": "application/json",
                    "title": "WebMercatorQuad definition (as JSON)",
                    "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=json",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                    "type": "text/html",
                    "title": "WebMercatorQuad definition (as HTML)",
                    "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=html",
                },
                {
                    "rel": "self",
                    "type": "application/json",
                    "title": "WebMercatorQuad map tileset for test (as JSON)",
                    "href": "http://localhost/ogcapi/collections/test/map/tiles/WebMercatorQuad?f=json",
                },
                {
                    "rel": "alternate",
                    "type": "text/html",
                    "title": "WebMercatorQuad map tileset for test (as HTML)",
                    "href": "http://localhost/ogcapi/collections/test/map/tiles/WebMercatorQuad?f=html",
                },
                {
                    "rel": "item",
                    "type": "image/png",
                    "title": "WebMercatorQuad map tiles for test (as PNG)",
                    "href": "http://localhost/ogcapi/collections/test/map/tiles/WebMercatorQuad/{tileMatrix}/{tileRow}/{tileCol}.png",  # noqa
                    "templated": True,
                },
                {
                    "rel": "item",
                    "type": "image/jpeg",
                    "title": "WebMercatorQuad map tiles for test (as JPEG)",
                    "href": "http://localhost/ogcapi/collections/test/map/tiles/WebMercatorQuad/{tileMatrix}/{tileRow}/{tileCol}.jpg",  # noqa
                    "templated": True,
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                    "type": "application/json",
                    "title": "WebMercatorQuad definition (as JSON)",
                    "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=json",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                    "type": "text/html",
                    "title": "WebMercatorQuad definition (as HTML)",
                    "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=html",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/geodata",
                    "type": "application/json",
                    "title": "test collection (as JSON)",
                    "href": "http://localhost/ogcapi/collections/test?f=json",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/geodata",
                    "type": "text/html",
                    "title": "test collection (as HTML)",
                    "href": "http://localhost/ogcapi/collections/test?f=html",
                },
            ],
        }
        assert resp.json == expected_json

        self._test_links(app, resp.json)

        self._validate_response_against_schema(resp.json, response_name="TileSet")

        resp = app.get(
            "/ogcapi/collections/test/map/tiles/WebMercatorQuad", {"f": "html"}
        )
        assert resp.content_type == "text/html"

    def test_tileset_invalid_path(self, app):
        app.get(
            "/ogcapi/collections/test/map/tiles/INVALID", expect_errors=True, status=404
        )
        app.get(
            "/ogcapi/collections/INVALID/map/tiles/WebMercatorQuad",
            expect_errors=True,
            status=404,
        )

    def test_dataset_tileset(self, app):
        resp = app.get("/ogcapi/map/tiles/WebMercatorQuad")
        assert resp.content_type == "application/json"

        expected_json = {
            "title": "Whole dataset with WebMercatorQuad tile matrix set",
            "tileMatrixSetURI": "http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad",
            "dataType": "map",
            "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
            "links": [
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                    "type": "application/json",
                    "title": "WebMercatorQuad definition (as JSON)",
                    "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=json",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                    "type": "text/html",
                    "title": "WebMercatorQuad definition (as HTML)",
                    "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=html",
                },
                {
                    "rel": "self",
                    "type": "application/json",
                    "title": "WebMercatorQuad map tileset for the whole dataset (as JSON)",
                    "href": "http://localhost/ogcapi/map/tiles/WebMercatorQuad?f=json",
                },
                {
                    "rel": "alternate",
                    "type": "text/html",
                    "title": "WebMercatorQuad map tileset for the whole dataset (as HTML)",
                    "href": "http://localhost/ogcapi/map/tiles/WebMercatorQuad?f=html",
                },
                {
                    "rel": "item",
                    "type": "image/png",
                    "title": "WebMercatorQuad map tiles for the whole dataset (as PNG)",
                    "href": "http://localhost/ogcapi/map/tiles/WebMercatorQuad/{tileMatrix}/{tileRow}/{tileCol}.png",
                    "templated": True,
                },
                {
                    "rel": "item",
                    "type": "image/jpeg",
                    "title": "WebMercatorQuad map tiles for the whole dataset (as JPEG)",
                    "href": "http://localhost/ogcapi/map/tiles/WebMercatorQuad/{tileMatrix}/{tileRow}/{tileCol}.jpg",
                    "templated": True,
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                    "type": "application/json",
                    "title": "WebMercatorQuad definition (as JSON)",
                    "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=json",
                },
                {
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                    "type": "text/html",
                    "title": "WebMercatorQuad definition (as HTML)",
                    "href": "http://localhost/ogcapi/tileMatrixSets/WebMercatorQuad?f=html",
                },
            ],
        }
        assert resp.json == expected_json

        self._test_links(app, resp.json)

        self._validate_response_against_schema(resp.json, response_name="TileSet")

        resp = app.get("/ogcapi/map/tiles/WebMercatorQuad", {"f": "html"})
        assert resp.content_type == "text/html"

    @pytest.mark.parametrize(
        "url,query_params,width,height,extent,wms_width,wms_height,wms_bbox,wms_srs,content_crs",
        [
            (
                "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/0/0.png",
                {},
                256,
                256,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                256,
                256,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                "EPSG:3857",
                "<http://www.opengis.net/def/crs/EPSG/0/3857>",
            ),
            # Test dataset tile
            (
                "/ogcapi/map/tiles/WebMercatorQuad/2/1/0.png",
                {},
                256,
                256,
                "-20037508.342789244,0,-10018754.171394622,10018754.171394622",
                256,
                256,
                "-20037508.342789244,0,-10018754.171394622,10018754.171394622",
                "EPSG:3857",
                "<http://www.opengis.net/def/crs/EPSG/0/3857>",
            ),
            # Test dataset tile with collections
            (
                "/ogcapi/map/tiles/WebMercatorQuad/2/1/0.png",
                {"collections": "test_without_nominal_scale"},
                256,
                256,
                "-20037508.342789244,0,-10018754.171394622,10018754.171394622",
                256,
                256,
                "-20037508.342789244,0,-10018754.171394622,10018754.171394622",
                "EPSG:3857",
                "<http://www.opengis.net/def/crs/EPSG/0/3857>",
            ),
            (
                "/ogcapi/collections/test/map/tiles/GLOBAL_GEODETIC/0/0/0.png",
                {"bgcolor": "0x123456", "transparent": "true"},
                256,
                256,
                "-180,-90,180,270",
                256,
                128,
                "-180,-90,180,90",
                "EPSG%3A4326",
                None,
            ),
            (
                "/ogcapi/collections/test/map/tiles/GLOBAL_GEODETIC/0/0/0.png",
                {"bgcolor": "0x78123456"},
                256,
                256,
                "-180,-90,180,270",
                256,
                128,
                "-180,-90,180,90",
                "EPSG%3A4326",
                None,
            ),
            (
                "/ogcapi/collections/test/map/tiles/GLOBAL_GEODETIC/0/0/0.png",
                {"bgcolor": "green"},
                256,
                256,
                "-180,-90,180,270",
                256,
                128,
                "-180,-90,180,90",
                "EPSG%3A4326",
                None,
            ),
        ],
    )
    def test_tile(
        self,
        app,
        url,
        query_params,
        width,
        height,
        extent,
        wms_width,
        wms_height,
        wms_bbox,
        wms_srs,
        content_crs,
    ):
        with tmp_image((width, height), format="png", color=(255, 0, 0)) as img:
            img_bytes = img.read()

        expected_req = (
            {
                "path": f"/service?layers=test&bbox={wms_bbox}&width={wms_width}&height={wms_height}&srs={wms_srs}&format=image%2Fpng&request=GetMap&version=1.1.1&service=WMS&styles="  # noqa
            },
            {"body": img_bytes, "headers": {"content-type": "image/png"}},
        )
        with mock_httpd(
            ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
        ):
            resp = app.get(url, query_params)
            assert resp.content_type == "image/png"
            assert resp.headers["Content-Bbox"] == extent
            if content_crs:
                assert resp.headers["Content-Crs"] == content_crs
            else:
                assert "Content-Crs" not in resp.headers
            img = Image.open(BytesIO(resp.body))
            assert img.format == "PNG"
            assert img.width == width
            assert img.height == height
            if wms_srs == "EPSG%3A4326" and float(extent.split(",")[3]) > 90:
                if query_params.get("transparent", True):
                    if query_params.get("bgcolor", "") == "green":
                        assert img.getextrema() == (
                            (0, 255),
                            (0, 0x80),
                            (0, 0),
                            (0, 255),
                        )
                    elif query_params.get("bgcolor", "") == "0x123456":
                        assert img.getextrema() == (
                            (0x12, 255),
                            (0, 0x34),
                            (0, 0x56),
                            (0, 255),
                        )
                    elif query_params.get("bgcolor", "") == "0x78123456":
                        assert img.getextrema() == (
                            (0x12, 255),
                            (0, 0x34),
                            (0, 0x56),
                            (0x78, 255),
                        )
                    else:
                        assert img.getextrema() == (
                            (255, 255),
                            (0, 255),
                            (0, 255),
                            (0, 255),
                        )
                else:
                    assert img.getextrema() == ((255, 255), (0, 255), (0, 255))
            else:
                assert img.getextrema() == ((255, 255), (0, 0), (0, 0))

    @pytest.mark.parametrize(
        "url,status,detail",
        [
            ("/ogcapi/collections/test/map/tiles/INVALID/0/0/0.png", 404, None),
            (
                "/ogcapi/collections/INVALID/map/tiles/WebMercatorQuad/0/0/0.png",
                404,
                None,
            ),
            (
                "/ogcapi/collections/test/map/tiles/WebMercatorQuad/-1/0/0.png",
                400,
                "Invalid zoom level. Valid range is [0,19]",
            ),
            (
                "/ogcapi/collections/test/map/tiles/WebMercatorQuad/20/0/0.png",
                400,
                "Invalid zoom level. Valid range is [0,19]",
            ),
            (
                "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/-1/0.png",
                400,
                "Invalid row number. Valid range is [0,0]",
            ),
            (
                "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/1/0.png",
                400,
                "Invalid row number. Valid range is [0,0]",
            ),
            (
                "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/0/-1.png",
                400,
                "Invalid col number. Valid range is [0,0]",
            ),
            (
                "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/0/1.png",
                400,
                "Invalid col number. Valid range is [0,0]",
            ),
            (
                "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/0/0.INVALID",
                406,
                "Unsupported image format INVALID",
            ),
        ],
    )
    def test_tile_invalid_path(self, app, url, status, detail):
        resp = app.get(url, expect_errors=True, status=status)
        assert resp.content_type == "application/json"
        assert resp.json["status"] == status, resp.json
        if detail:
            assert resp.json["detail"] == detail, resp.json

    @pytest.mark.parametrize(
        "query_params,detail",
        [
            ({"bgcolor": "invalid"}, "invalid value for bgcolor"),
            ({"transparent": "invalid"}, "invalid value for transparent"),
            ({"width": "256"}, "Unknown query parameter width"),
        ],
    )
    def test_tile_errors(self, app, query_params, detail):
        resp = app.get(
            "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/0/0.png",
            query_params,
            expect_errors=True,
        )
        assert resp.content_type == "application/json"
        assert resp.json["status"] == 400, resp.json
        assert resp.json["detail"] == detail, resp.json

    def test_dataset_tile_error(self, app):
        resp = app.get(
            "/ogcapi/map/tiles/WebMercatorQuad/0/0/0.png",
            {"collections": "invalid_coll"},
            expect_errors=True,
        )
        assert resp.content_type == "application/json"
        assert resp.json["status"] == 400, resp.json
        assert resp.json["detail"] == "unknown collection invalid_coll", resp.json


# Tests where both OGC API Maps and Tiles are enabled
class TestOGCAPIMapsAndTilesService(TestOGCAPIService):
    @pytest.fixture(scope="class")
    def config_file(self):
        return "ogcapi_maps_and_tiles_service.yaml"

    def _validate_response_against_schema(
        self, json_doc, schema_name=None, response_name=None
    ):
        ogcapi_tiles_schema_path = (
            importlib_resources.files(test_module.__package__)
            .joinpath("schemas")
            .joinpath("ogcapi")
            .joinpath("ogcapi-maps-1.bundled.json")
        )
        ogcapi_tiles_schema = json.loads(open(ogcapi_tiles_schema_path, "rb").read())
        if schema_name:
            schema = ogcapi_tiles_schema["components"]["schemas"][schema_name]
        elif response_name:
            schema = ogcapi_tiles_schema["components"]["responses"][response_name][
                "content"
            ]["application/json"]["schema"]
        else:
            assert False, "one of schema_name or response_name must be specified"
        schema["components"] = ogcapi_tiles_schema["components"]
        jsonschema.validate(json_doc, schema)

    def test_conformance(self, app):
        resp = app.get("/ogcapi/conformance")
        assert resp.content_type == "application/json"
        expected_json = {
            "conformsTo": [
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/html",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/json",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/landing-page",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/oas30",
                "http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/scaling",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/spatial-subsetting",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/crs",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/display-resolution",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/background",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/collection-map",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/collections-selection",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/png",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/jpeg",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/dataset-map",
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/tilesets",
                "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/oas30",
                "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/tileset",
                "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/tilesets-list",
                "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/geodata-tilesets",
                "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/dataset-tilesets",
            ]
        }
        assert resp.json == expected_json

        self._validate_response_against_schema(resp.json, schema_name="confClasses")

    def test_api(self, app):
        resp = app.get("/ogcapi/api")
        assert (
            resp.headers["Content-type"]
            == "application/vnd.oai.openapi+json;version=3.0"
        )

        assert [path for path in resp.json["paths"]] == [
            "/",
            "/api",
            "/collections",
            "/collections/{collectionId}",
            "/collections/{collectionId}/map",
            "/collections/{collectionId}/map/tiles",
            "/collections/{collectionId}/map/tiles/{tileMatrixSetId}",
            "/collections/{collectionId}/map/tiles/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}",
            "/map",
            "/map/tiles",
            "/map/tiles/{tileMatrixSetId}",
            "/map/tiles/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}",
            "/tileMatrixSets",
            "/tileMatrixSets/{tileMatrixSetId}",
            "/conformance",
        ]

        assert "/tileMatrixSets" in resp.json["paths"]

        openapi_schema_path = (
            importlib_resources.files(test_module.__package__)
            .joinpath("schemas")
            .joinpath("openapi")
            .joinpath("openapi-3.0.x.json")
        )
        openapi_schema = json.loads(open(openapi_schema_path, "rb").read())
        jsonschema.validate(resp.json, openapi_schema)

    @pytest.mark.parametrize(
        "url,query_params,width,height,extent,wms_width,wms_height,wms_bbox,wms_srs,content_crs",
        [
            (
                "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/0/0.png",
                {"width": 512, "height": 256},
                512,
                256,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                512,
                256,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                "EPSG:3857",
                "<http://www.opengis.net/def/crs/EPSG/0/3857>",
            ),
            (
                "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/0/0.png",
                {"width": 512},
                512,
                512,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                512,
                512,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                "EPSG:3857",
                "<http://www.opengis.net/def/crs/EPSG/0/3857>",
            ),
            (
                "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/0/0.png",
                {"height": 512},
                512,
                512,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                512,
                512,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                "EPSG:3857",
                "<http://www.opengis.net/def/crs/EPSG/0/3857>",
            ),
            (
                "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/0/0.png",
                {"mm-per-pixel": "0.14"},
                512,
                512,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                512,
                512,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                "EPSG:3857",
                "<http://www.opengis.net/def/crs/EPSG/0/3857>",
            ),
            (
                "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/0/0.png",
                {"scale-denominator": "500000000"},
                286,
                286,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                286,
                286,
                "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244",
                "EPSG:3857",
                "<http://www.opengis.net/def/crs/EPSG/0/3857>",
            ),
        ],
    )
    def test_tile(
        self,
        app,
        url,
        query_params,
        width,
        height,
        extent,
        wms_width,
        wms_height,
        wms_bbox,
        wms_srs,
        content_crs,
    ):
        with tmp_image((width, height), format="png", color=(255, 0, 0)) as img:
            img_bytes = img.read()

        expected_req = (
            {
                "path": f"/service?layers=test&bbox={wms_bbox}&width={wms_width}&height={wms_height}&srs={wms_srs}&format=image%2Fpng&request=GetMap&version=1.1.1&service=WMS&styles="  # noqa
            },
            {"body": img_bytes, "headers": {"content-type": "image/png"}},
        )
        with mock_httpd(
            ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
        ):
            resp = app.get(url, query_params)
            assert resp.content_type == "image/png"
            assert resp.headers["Content-Bbox"] == extent
            if content_crs:
                assert resp.headers["Content-Crs"] == content_crs
            else:
                assert "Content-Crs" not in resp.headers
            img = Image.open(BytesIO(resp.body))
            assert img.format == "PNG"
            assert img.width == width
            assert img.height == height
            assert img.getextrema() == ((255, 255), (0, 0), (0, 0))

    @pytest.mark.parametrize(
        "query_params,detail",
        [
            ({"width": "invalid"}, "width is not an integer"),
            ({"width": 0}, "width must be strictly positive"),
            ({"height": "invalid"}, "height is not an integer"),
            ({"height": 0}, "height must be strictly positive"),
            ({"width": 40001}, "width=40001 exceeds max_width=40000"),
            (
                {"width": 40000},
                "number of pixels 1600000000 exceed max_pixels=16000000",
            ),
            ({"width": 1, "height": 40001}, "height=40001 exceeds max_height=40000"),
            (
                {"width": 4001, "height": 4000},
                "number of pixels 16004000 exceed max_pixels=16000000",
            ),
            (
                {"width": 1, "height": 1, "scale-denominator": 50000000},
                "scale-denominator is mutually exclusive with width or height",
            ),
        ],
    )
    def test_tile_errors(self, app, query_params, detail):
        resp = app.get(
            "/ogcapi/collections/test/map/tiles/WebMercatorQuad/0/0/0.png",
            query_params,
            expect_errors=True,
        )
        assert resp.content_type == "application/json"
        assert resp.json["status"] == 400, resp.json
        assert resp.json["detail"] == detail, resp.json


# Tests support for non Earth CRS
class TestOGCAPIMapsAndTilesNonEarthService(TestOGCAPIService):
    @pytest.fixture(scope="class")
    def config_file(self):
        return "ogcapi_maps_and_tiles_non_earth_service.yaml"

    def _validate_response_against_schema(
        self, json_doc, schema_name=None, response_name=None
    ):
        if sys.version_info < (3, 10):
            # jsonschema.validate() hangs for py 3.9
            return
        ogcapi_tiles_schema_path = (
            importlib_resources.files(test_module.__package__)
            .joinpath("schemas")
            .joinpath("ogcapi")
            .joinpath("ogcapi-maps-1.bundled.json")
        )
        ogcapi_tiles_schema = json.loads(open(ogcapi_tiles_schema_path, "rb").read())
        if schema_name:
            schema = ogcapi_tiles_schema["components"]["schemas"][schema_name]
        elif response_name:
            schema = ogcapi_tiles_schema["components"]["responses"][response_name][
                "content"
            ]["application/json"]["schema"]
        else:
            assert False, "one of schema_name or response_name must be specified"
        schema["components"] = ogcapi_tiles_schema["components"]
        jsonschema.validate(json_doc, schema)

    def test_collection(self, app):
        resp = app.get("/ogcapi/collections/test")
        assert resp.content_type == "application/json"
        expected_json = {
            "crs": [
                "http://www.opengis.net/def/crs/IAU/2015/30100",
                "http://www.opengis.net/def/crs/IAU/2015/30110",
            ],
            "dataType": "map",
            "extent": {
                "spatial": {
                    "bbox": [[-180, -90, 180, 90]],
                    "crs": "http://www.opengis.net/def/crs/IAU/2015/30100",
                }
            },
            "id": "test",
            "links": [
                {
                    "href": "http://localhost/ogcapi/collections/test?f=json",
                    "rel": "self",
                    "title": "The JSON representation of this data collection",
                    "type": "application/json",
                },
                {
                    "href": "http://localhost/ogcapi/collections/test?f=html",
                    "rel": "alternate",
                    "title": "The HTML representation of this data collection",
                    "type": "text/html",
                },
                {
                    "href": "http://localhost/ogcapi/collections/test/map.png",
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                    "title": "Default map (as PNG)",
                    "type": "image/png",
                },
                {
                    "href": "http://localhost/ogcapi/collections/test/map.jpg",
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                    "title": "Default map (as JPEG)",
                    "type": "image/jpeg",
                },
                {
                    "href": "http://localhost/ogcapi/collections/test/map/tiles?f=json",
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tilesets-map",
                    "title": "Map tilesets available for this collection (as JSON)",
                    "type": "application/json",
                },
                {
                    "href": "http://localhost/ogcapi/collections/test/map/tiles?f=html",
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tilesets-map",
                    "title": "Map tilesets available for this collection (as HTML)",
                    "type": "text/html",
                },
            ],
            "storageCrs": "http://www.opengis.net/def/crs/IAU/2015/30100",
            "title": "title",
        }

        assert resp.json == expected_json

        self._test_links(app, resp.json)

        if sys.version_info < (3, 10):
            # jsonschema.validate() hangs for py 3.9
            return
        ogcapi_maps_schema_path = (
            importlib_resources.files(test_module.__package__)
            .joinpath("schemas")
            .joinpath("ogcapi")
            .joinpath("ogcapi-maps-1.bundled.json")
        )
        ogcapi_maps_schema = json.loads(open(ogcapi_maps_schema_path, "rb").read())
        schema = ogcapi_maps_schema["components"]["schemas"]["collectionDesc"]
        schema["components"] = ogcapi_maps_schema["components"]
        # Cf https://github.com/opengeospatial/ogcapi-maps/issues/140
        schema["components"]["schemas"]["collectionDesc"]["properties"]["extent"][
            "$ref"
        ] = "#/components/schemas/extent"
        # Cf https://github.com/opengeospatial/ogcapi-maps/issues/141
        del schema["components"]["schemas"]["extent"]["properties"]["spatial"][
            "properties"
        ]["crs"]["enum"]
        jsonschema.validate(resp.json, schema)

    def test_tilesets(self, app):
        resp = app.get("/ogcapi/collections/test/map/tiles")
        assert resp.content_type == "application/json"

        expected_json = {
            "links": [
                {
                    "rel": "self",
                    "type": "application/json",
                    "title": "The JSON representation of the available map tilesets for test (as JSON)",
                    "href": "http://localhost/ogcapi/collections/test/map/tiles?f=json",
                },
                {
                    "rel": "alternate",
                    "type": "text/html",
                    "title": "The HTML representation of the available map tilesets for test (as HTML)",
                    "href": "http://localhost/ogcapi/collections/test/map/tiles?f=html",
                },
            ],
            "tilesets": [
                {
                    "title": "test with moon_grid tile matrix set",
                    "dataType": "map",
                    "crs": "http://www.opengis.net/def/crs/IAU/2015/30100",
                    "links": [
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "application/json",
                            "title": "moon_grid definition (as JSON)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/moon_grid?f=json",
                        },
                        {
                            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
                            "type": "text/html",
                            "title": "moon_grid definition (as HTML)",
                            "href": "http://localhost/ogcapi/tileMatrixSets/moon_grid?f=html",
                        },
                        {
                            "rel": "self",
                            "type": "application/json",
                            "title": "moon_grid map tileset for test (as JSON)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/moon_grid?f=json",
                        },
                        {
                            "rel": "alternate",
                            "type": "text/html",
                            "title": "moon_grid map tileset for test (as HTML)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/moon_grid?f=html",
                        },
                        {
                            "rel": "item",
                            "type": "image/png",
                            "title": "moon_grid map tiles for test (as PNG)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/moon_grid/{tileMatrix}/{tileRow}/{tileCol}.png",  # noqa
                            "templated": True,
                        },
                        {
                            "rel": "item",
                            "type": "image/jpeg",
                            "title": "moon_grid map tiles for test (as JPEG)",
                            "href": "http://localhost/ogcapi/collections/test/map/tiles/moon_grid/{tileMatrix}/{tileRow}/{tileCol}.jpg",  # noqa
                            "templated": True,
                        },
                    ],
                }
            ],
        }
        assert resp.json == expected_json

        self._test_links(app, resp.json)

        self._validate_response_against_schema(resp.json, response_name="TileSetsList")

        resp = app.get("/ogcapi/collections/test/map/tiles", {"f": "html"})
        assert resp.content_type == "text/html"

    @pytest.mark.parametrize(
        "url,query_params,width,height,extent,wms_width,wms_height,wms_bbox,wms_srs,content_crs",
        [
            (
                "/ogcapi/collections/test/map/tiles/moon_grid/0/0/0.png",
                {},
                256,
                256,
                "-270,-180,90,180",
                256,
                128,
                "-180,-90,180,90",
                "IAU_2015:30100",
                "<http://www.opengis.net/def/crs/IAU/2015/30100>",
            ),
        ],
    )
    def test_tile(
        self,
        app,
        url,
        query_params,
        width,
        height,
        extent,
        wms_width,
        wms_height,
        wms_bbox,
        wms_srs,
        content_crs,
    ):
        with tmp_image((width, height), format="png", color=(255, 0, 0)) as img:
            img_bytes = img.read()

        expected_req = (
            {
                "path": f"/service?layers=test&bbox={wms_bbox}&width={wms_width}&height={wms_height}&srs={wms_srs}&format=image%2Fpng&request=GetMap&version=1.1.1&service=WMS&styles="  # noqa
            },
            {"body": img_bytes, "headers": {"content-type": "image/png"}},
        )
        with mock_httpd(
            ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
        ):
            resp = app.get(url, query_params)
            assert resp.content_type == "image/png"
            assert resp.headers["Content-Bbox"] == extent
            if content_crs:
                assert resp.headers["Content-Crs"] == content_crs
            else:
                assert "Content-Crs" not in resp.headers
            img = Image.open(BytesIO(resp.body))
            assert img.format == "PNG"
            assert img.width == width
            assert img.height == height
            assert img.getextrema() == ((255, 255), (0, 0), (0, 0), (255, 255))
