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
from mapproxy.grid.tile_grid import tile_grid_to_ogc_tile_matrix_set
from mapproxy.service.ogcapi.server import OGCAPIException, OGCAPIServer
from mapproxy.service.ogcapi.constants import FORMAT_TYPES, F_JSON, F_HTML


def tilematrixsets(server: OGCAPIServer, req: Request):
    log = server.log
    log.debug("TileMatrixSets")

    for arg in req.args:
        if arg != "f":
            raise OGCAPIServer.unknown_query_parameter(arg)
    if req.args.get("f", None) not in (None, F_JSON, F_HTML):
        raise OGCAPIServer.invalid_parameter("Invalid value for f query parameter")

    tileMatrixSets = []

    is_html = server.is_html_req(req)

    for name in server.grid_configs:
        tms = {
            "id": name,
            "title": name,
            "links": [
                {
                    "rel": ("self" if not is_html else "alternate"),
                    "type": FORMAT_TYPES[F_JSON],
                    "title": f"The JSON representation of the {name} tiling scheme definition",
                    "href": server.create_href(
                        req, f"/ogcapi/tileMatrixSets/{name}?f={F_JSON}"
                    ),
                },
                {
                    "rel": ("alternate" if not is_html else "self"),
                    "type": FORMAT_TYPES[F_HTML],
                    "title": f"The HTML representation of the {name} tiling scheme definition",
                    "href": server.create_href(
                        req, f"/ogcapi/tileMatrixSets/{name}?f={F_HTML}"
                    ),
                },
            ],
        }
        if name == "WebMercatorQuad":
            tms[
                "uri"
            ] = "http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad"

        tileMatrixSets.append(tms)

    json_resp = {"tileMatrixSets": tileMatrixSets}

    return server.create_json_or_html_response(
        req, json_resp, "tilematrixsets/index.html"
    )


def tilematrixset(server: OGCAPIServer, req: Request, id: str):
    log = server.log
    log.info("TileMatrixSet")

    for arg in req.args:
        if arg != "f":
            raise OGCAPIServer.unknown_query_parameter(arg)
    if req.args.get("f", None) not in (None, F_JSON, F_HTML):
        raise OGCAPIServer.invalid_parameter("Invalid value for f query parameter")

    if id not in server.grid_configs:
        raise OGCAPIException("Not Found", "TileMatrixSet not found", status=404)

    uri = None
    wellKnownScaleSet = None
    if id == "WebMercatorQuad":
        uri = "http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad"
        wellKnownScaleSet = (
            "http://www.opengis.net/def/wkss/OGC/1.0/GoogleMapsCompatible"
        )

    json_resp = tile_grid_to_ogc_tile_matrix_set(
        server.grid_configs[id].tile_grid(),
        id,
        title=id,
        uri=uri,
        well_known_scale_set=wellKnownScaleSet,
    )

    return server.create_json_or_html_response(
        req, json_resp, "tilematrixsets/tilematrixset.html"
    )
