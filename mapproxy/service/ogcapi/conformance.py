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

from mapproxy.request.base import Request
from mapproxy.service.ogcapi.server import OGCAPIServer
from mapproxy.service.ogcapi.constants import F_JSON, F_HTML


def conformance(server: OGCAPIServer, req: Request):
    log = server.log
    log.info("Conformance")

    for arg in req.args:
        if arg != "f":
            raise OGCAPIServer.unknown_query_parameter(arg)
    if req.args.get("f", None) not in (None, F_JSON, F_HTML):
        raise OGCAPIServer.invalid_parameter("Invalid value for f query parameter")

    conformsTo = [
        "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
        "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/html",
        "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/json",
        "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/landing-page",
        "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/oas30",
        "http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections",
    ]

    if server.enable_maps:
        conformsTo += [
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
        ]
        if server.default_dataset_layers:
            conformsTo.append(
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/dataset-map"
            )
        if server.enable_tiles:
            conformsTo.append(
                "http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/tilesets"
            )

    if server.enable_tiles:
        conformsTo += [
            "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/core",
            "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/oas30",
            "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/tileset",
            "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/tilesets-list",
            "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/geodata-tilesets",
        ]
        if server.default_dataset_layers:
            conformsTo.append(
                "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/dataset-tilesets"
            )
    json_resp = {"conformsTo": conformsTo}

    return server.create_json_or_html_response(req, json_resp, "conformance.html")
