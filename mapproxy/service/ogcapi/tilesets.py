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

from typing import Optional, Any

from mapproxy.config.config import base_config
from mapproxy.request.base import Request
from mapproxy.srs import SRS
from mapproxy.service.ogcapi.server import OGCAPIException, OGCAPIServer
from mapproxy.service.ogcapi.constants import (
    FORMAT_TYPES,
    F_JSON,
    F_HTML,
    F_PNG,
    F_JPEG,
)
from mapproxy.service.wms import WMSGroupLayer


def _base_tileset(
    server: OGCAPIServer, req: Request, is_html: bool, coll_id: Optional[str], tms_name: str
):
    tileset: dict[str, Any] = {}
    tileset["title"] = (
        f"{coll_id} with {tms_name} tile matrix set"
        if coll_id
        else f"Whole dataset with {tms_name} tile matrix set"
    )
    if tms_name == "WebMercatorQuad":
        tileset[
            "tileMatrixSetURI"
        ] = "http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad"
    tileset["dataType"] = "map"

    srs = server.grid_configs[tms_name].tile_grid().srs
    if srs.srs_code == "EPSG:4326":
        srs = SRS("OGC:CRS84")
    elif srs.srs_code == "EPSG:900913":
        srs = SRS("EPSG:3857")
    tileset["crs"] = srs.to_ogc_url()

    if coll_id is None:
        base_url = "/ogcapi"
    else:
        base_url = f"/ogcapi/collections/{coll_id}"

    title_end = f"for {coll_id}" if coll_id else "for the whole dataset"
    tileset["links"] = [
        {
            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
            "type": FORMAT_TYPES[F_JSON],
            "title": f"{tms_name} definition (as JSON)",
            "href": server.create_href(
                req, f"/ogcapi/tileMatrixSets/{tms_name}?f={F_JSON}"
            ),
        },
        {
            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
            "type": FORMAT_TYPES[F_HTML],
            "title": f"{tms_name} definition (as HTML)",
            "href": server.create_href(
                req, f"/ogcapi/tileMatrixSets/{tms_name}?f={F_HTML}"
            ),
        },
        {
            "rel": ("self" if not is_html else "alternate"),
            "type": FORMAT_TYPES[F_JSON],
            "title": f"{tms_name} map tileset {title_end} (as JSON)",
            "href": server.create_href(
                req, f"{base_url}/map/tiles/{tms_name}?f={F_JSON}"
            ),
        },
        {
            "rel": ("alternate" if not is_html else "self"),
            "type": FORMAT_TYPES[F_HTML],
            "title": f"{tms_name} map tileset {title_end} (as HTML)",
            "href": server.create_href(
                req, f"{base_url}/map/tiles/{tms_name}?f={F_HTML}"
            ),
        },
        # Below links are not required in the tileSetsList response (only in
        # full tileSet response), but are provided for convenience
        {
            "rel": "item",
            "type": FORMAT_TYPES[F_PNG],
            "title": f"{tms_name} map tiles {title_end} (as PNG)",
            "href": server.create_href(
                req,
                f"{base_url}/map/tiles/{tms_name}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}.png",
            ),
            "templated": True,
        },
        {
            "rel": "item",
            "type": FORMAT_TYPES[F_JPEG],
            "title": f"{tms_name} map tiles {title_end} (as JPEG)",
            "href": server.create_href(
                req,
                f"{base_url}/map/tiles/{tms_name}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}.jpg",
            ),
            "templated": True,
        },
    ]
    return tileset


def tilesets(server: OGCAPIServer, req: Request, coll_id: Optional[str]):
    log = server.log
    log.debug("TileSets")

    for arg in req.args:
        if arg != "f":
            raise OGCAPIServer.unknown_query_parameter(arg)
    if req.args.get("f", None) not in (None, F_JSON, F_HTML):
        raise OGCAPIServer.invalid_parameter("Invalid value for f query parameter")

    if coll_id is None:
        if server.default_dataset_layers is None:
            raise OGCAPIServer.exception(
                "InternalError",
                "Dataset tilesets request but no default_dataset_layers defined in server configuration",
                status=500,
            )
        base_url = "/ogcapi"
    else:
        if coll_id not in server.layers:
            raise OGCAPIServer.collection_not_found()
        base_url = f"/ogcapi/collections/{coll_id}"

    is_html = server.is_html_req(req)

    title_end = f"for {coll_id}" if coll_id else "for the whole dataset"
    json_resp: dict[str, Any] = {
        "links": [
            {
                "rel": ("self" if not is_html else "alternate"),
                "type": FORMAT_TYPES[F_JSON],
                "title": f"The JSON representation of the available map tilesets {title_end} (as JSON)",
                "href": server.create_href(req, f"{base_url}/map/tiles?f={F_JSON}"),
            },
            {
                "rel": ("alternate" if not is_html else "self"),
                "type": FORMAT_TYPES[F_HTML],
                "title": f"The HTML representation of the available map tilesets {title_end} (as HTML)",
                "href": server.create_href(req, f"{base_url}/map/tiles?f={F_HTML}"),
            },
        ]
    }

    if coll_id:
        layer = server.layers[coll_id]
    else:
        layer = WMSGroupLayer(
            "group_layer", "group_layer", None, server.default_dataset_layers
        )

    tilesets = []
    for tms_name in server.grid_configs:
        is_earth_layer = layer.extent.srs.srs_code.startswith("EPSG:")
        tile_grid_srs = server.grid_configs[tms_name].tile_grid().srs
        is_earth_tilegrid = tile_grid_srs.srs_code.startswith("EPSG:")
        if is_earth_layer != is_earth_tilegrid:
            continue

        tileset = _base_tileset(server, req, is_html, coll_id, tms_name)
        if is_html:
            tileset["tileMatrixSet"] = tms_name

        tilesets.append(tileset)

    if is_html:
        if coll_id:
            json_resp["collections_path"] = server.create_href(
                req, "/ogcapi/collections"
            )
            json_resp["collection_path"] = server.create_href(req, base_url)
        json_resp["collection_title"] = (
            server.layers[coll_id].title if coll_id else "Dataset tiles"
        )
        json_resp["collection_tilesets_path"] = server.create_href(
            req, f"{base_url}/map/tiles"
        )

    json_resp["tilesets"] = tilesets

    return server.create_json_or_html_response(req, json_resp, "tilesets/index.html")


def tileset(server: OGCAPIServer, req: Request, coll_id: Optional[str], tms_name: str):
    log = server.log
    log.debug("TileSet")

    for arg in req.args:
        if arg != "f":
            raise OGCAPIServer.unknown_query_parameter(arg)
    if req.args.get("f", None) not in (None, F_JSON, F_HTML):
        raise OGCAPIServer.invalid_parameter("Invalid value for f query parameter")

    if coll_id is None:
        if server.default_dataset_layers is None:
            raise OGCAPIServer.exception(
                "InternalError",
                "Dataset tileset request but no default_dataset_layers defined in server configuration",
                status=500,
            )
        base_url = "/ogcapi"
    else:
        if coll_id not in server.layers:
            raise OGCAPIServer.collection_not_found()
        base_url = f"/ogcapi/collections/{coll_id}"

    if tms_name not in server.grid_configs:
        raise OGCAPIException("Not Found", "TileMatrixSet not found", status=404)

    is_html = server.is_html_req(req)

    json_resp = _base_tileset(server, req, is_html, coll_id, tms_name)

    json_resp["links"] += [
        {
            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
            "type": FORMAT_TYPES[F_JSON],
            "title": f"{tms_name} definition (as JSON)",
            "href": server.create_href(
                req, f"/ogcapi/tileMatrixSets/{tms_name}?f={F_JSON}"
            ),
        },
        {
            "rel": "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
            "type": FORMAT_TYPES[F_HTML],
            "title": f"{tms_name} definition (as HTML)",
            "href": server.create_href(
                req, f"/ogcapi/tileMatrixSets/{tms_name}?f={F_HTML}"
            ),
        },
    ]
    if coll_id:
        json_resp["links"] += [
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/geodata",
                "type": FORMAT_TYPES[F_JSON],
                "title": f"{coll_id} collection (as JSON)",
                "href": server.create_href(req, f"{base_url}?f={F_JSON}"),
            },
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/geodata",
                "type": FORMAT_TYPES[F_HTML],
                "title": f"{coll_id} collection (as HTML)",
                "href": server.create_href(req, f"{base_url}?f={F_HTML}"),
            },
        ]

    if is_html:
        if coll_id:
            layer = server.layers[coll_id]
        else:
            layer = WMSGroupLayer(
                "group_layer", "group_layer", None, server.default_dataset_layers
            )

        if coll_id:
            json_resp["collections_path"] = server.create_href(
                req, "/ogcapi/collections"
            )
            json_resp["collection_path"] = server.create_href(req, base_url)
        json_resp["collection_title"] = layer.title
        json_resp["collection_tilesets_path"] = server.create_href(
            req, f"{base_url}/map/tiles"
        )
        json_resp["id"] = tms_name
        json_resp["png_tiles_href"] = server.create_href(
            req,
            f"{base_url}/map/tiles/{tms_name}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}.png",
        )
        json_resp["sample_png_tile_href"] = server.create_href(
            req, f"{base_url}/map/tiles/{tms_name}/0/0/0.png"
        )
        json_resp["jpeg_tiles_href"] = server.create_href(
            req,
            f"{base_url}/map/tiles/{tms_name}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}.jpg",
        )
        json_resp["tms_def_href"] = server.create_href(
            req, f"/ogcapi/tileMatrixSets/{tms_name}"
        )

        tile_grid = server.grid_configs[tms_name].tile_grid()
        srs = tile_grid.srs
        json_resp["srs"] = srs.srs_code
        json_resp["extent"] = list(layer.extent.transform(srs).bbox)
        json_resp["background_url"] = base_config().background.url
        if tile_grid.origin == "ul":
            json_resp["tileset_xyz_url"] = server.create_href(
                req,
                f"{base_url}/map/tiles/{tms_name}/{{z}}/{{y}}/{{x}}.png",
            )
        else:
            json_resp["tileset_xyz_url"] = server.create_href(
                req,
                f"{base_url}/map/tiles/{tms_name}/{{z}}/{{-y}}/{{x}}.png",
            )

    # Recommendation 5.A
    headers = {
        "Link-Template": f'<{base_url}/map/tiles/{tms_name}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}.png>; rel="item"; type="image/png"'  # noqa
    }

    return server.create_json_or_html_response(
        req, json_resp, "tilesets/tileset.html", headers=headers
    )
