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
from typing import Any

from mapproxy.request.base import Request
from mapproxy.service.ogcapi.server import OGCAPIServer
from mapproxy.service.ogcapi.constants import (
    FORMAT_TYPES,
    F_JSON,
    F_HTML,
    F_PNG,
    F_JPEG,
    MEDIA_TYPE_OPENAPI_3_0,
)


def landing_page(server: OGCAPIServer, req: Request):
    log = server.log
    log.debug("Landing page")

    for arg in req.args:
        if arg != "f":
            raise OGCAPIServer.unknown_query_parameter(arg)
    if req.args.get("f", None) not in (None, F_JSON, F_HTML):
        raise OGCAPIServer.invalid_parameter("Invalid value for f query parameter")

    is_html = server.is_html_req(req)
    json_resp: dict[str, Any] = {
        "links": [
            {
                "rel": ("self" if not is_html else "alternate"),
                "type": FORMAT_TYPES[F_JSON],
                "title": "The JSON representation of the landing page for "
                "this OGC (geospatial) API Service providing links "
                "to the API definition, the conformance declaration "
                "and information about the data collections offered "
                "at this endpoint.",
                "href": server.create_href(req, f"/ogcapi?f={F_JSON}"),
            },
            {
                "rel": ("alternate" if not is_html else "self"),
                "type": FORMAT_TYPES[F_HTML],
                "title": "The HTML representation of the landing page for "
                "this OGC (geospatial) API Service providing links "
                "to the API definition, the conformance declaration "
                "and information about the data collections offered "
                "at this endpoint.",
                "href": server.create_href(req, f"/ogcapi?f={F_HTML}"),
            },
            {
                "rel": "conformance",  # Deprecated way
                "type": FORMAT_TYPES[F_JSON],
                "title": "The JSON representation of the conformance "
                "declaration for this server listing the "
                "requirement classes implemented by this server",
                "href": server.create_href(req, f"/ogcapi/conformance?f={F_JSON}"),
            },
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/conformance",
                "type": FORMAT_TYPES[F_JSON],
                "title": "The JSON representation of the conformance "
                "declaration for this server listing the "
                "requirement classes implemented by this server",
                "href": server.create_href(req, f"/ogcapi/conformance?f={F_JSON}"),
            },
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/conformance",
                "type": FORMAT_TYPES[F_HTML],
                "title": "The HTML representation of the conformance "
                "declaration for this server listing the "
                "requirement classes implemented by this server",
                "href": server.create_href(req, f"/ogcapi/conformance?f={F_HTML}"),
            },
            {
                "rel": "service-desc",
                "type": MEDIA_TYPE_OPENAPI_3_0,
                "title": "The JSON OpenAPI 3.0 document that describes the API offered at this endpoint",
                "href": server.create_href(req, f"/ogcapi/api?f={F_JSON}"),
            },
            {
                "rel": "service-doc",
                "type": FORMAT_TYPES[F_HTML],
                "title": "The HTML documentation of the API offered at this endpoint",
                "href": server.create_href(req, f"/ogcapi/api?f={F_HTML}"),
            },
            {
                "rel": "data",
                "type": FORMAT_TYPES[F_JSON],
                "title": "The JSON representation of the list of all data collections served from this endpoint",
                "href": server.create_href(req, f"/ogcapi/collections?f={F_JSON}"),
            },
            {
                "rel": "data",
                "type": FORMAT_TYPES[F_HTML],
                "title": "The HTML representation of the list of all data collections served from this endpoint",
                "href": server.create_href(req, f"/ogcapi/collections?f={F_HTML}"),
            },
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/data",
                "type": FORMAT_TYPES[F_JSON],
                "title": "The JSON representation of the list of all data collections served from this endpoint",
                "href": server.create_href(req, f"/ogcapi/collections?f={F_JSON}"),
            },
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/data",
                "type": FORMAT_TYPES[F_HTML],
                "title": "The HTML representation of the list of all data collections served from this endpoint",
                "href": server.create_href(req, f"/ogcapi/collections?f={F_HTML}"),
            },
        ]
    }

    if server.enable_maps and server.default_dataset_layers:
        if is_html:
            json_resp["has_dataset_map"] = True

        json_resp["links"] += [
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                "type": FORMAT_TYPES[F_PNG],
                "title": "Default map of the whole datase (as PNG)",
                "href": server.create_href(req, "/ogcapi/map.png"),
            },
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                "type": FORMAT_TYPES[F_JPEG],
                "title": "Default map of the whole datase (as JPEG)",
                "href": server.create_href(req, "/ogcapi/map.jpg"),
            },
        ]

    if server.enable_tiles and server.grid_configs:
        if is_html:
            json_resp["tile"] = True

        json_resp["links"] += [
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-schemes",
                "type": FORMAT_TYPES[F_JSON],
                "title": "The list of supported tiling schemes (as JSON)",
                "href": server.create_href(req, f"/ogcapi/tileMatrixSets?f={F_JSON}"),
            },
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-schemes",
                "type": FORMAT_TYPES[F_HTML],
                "title": "The list of supported tiling schemes (as HTML)",
                "href": server.create_href(req, f"/ogcapi/tileMatrixSets?f={F_HTML}"),
            },
        ]

    if is_html and server.layers:
        json_resp["collection"] = True

    return server.create_json_or_html_response(req, json_resp, "landing_page.html")
