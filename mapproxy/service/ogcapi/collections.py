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

from mapproxy.config.config import base_config
from mapproxy.grid.resolutions import res_to_ogc_scale
from mapproxy.request.base import Request
from mapproxy.service.ogcapi.constants import (
    FORMAT_TYPES,
    F_JSON,
    F_HTML,
    F_PNG,
    F_JPEG,
)
from mapproxy.service.ogcapi.server import OGCAPIServer
from mapproxy.service.wms import WMSLayerBase
from mapproxy.srs import SRS


def _get(d: dict, *path):
    for p in path:
        if p not in d:
            return None
        d = d[p]
    return d


def get_collection(server: OGCAPIServer, req: Request, layer: WMSLayerBase):
    id = layer.name
    col: dict[str, Any] = {}
    col["dataType"] = "map"
    col["id"] = id
    col["title"] = layer.title
    abstract = _get(layer.md, "abstract")
    if abstract:
        col["description"] = abstract

    attribution = layer.md.get("attribution", None)
    if attribution:
        attribution_title = attribution.get("title", None)
        if attribution_title:
            col["attribution"] = attribution_title
            attribution_url = attribution.get("url", None)
            if attribution_url:
                attribution_logo_url = _get(attribution, "logo", "url")
                if attribution_logo_url:
                    col[
                        "attribution"
                    ] = f"[![{attribution_title}]({attribution_logo_url}]({attribution_url})"
                else:
                    col["attribution"] = f"[{attribution_title}]({attribution_url})"
                col["attributionMediaType"] = "text/markdown"

    #  The OGC API Common specfication required that the
    # ``"extent": { "spatial": { "bbox": [ [xmin,ymin,xmax,ymal] ] }`` property
    # is always presented in CRS84 (or for planetary datasets in the applicable
    # global geographic CRS, that you then set as a ``crs`` child member of crs.
    if layer.extent.srs.srs_code.startswith("EPSG:"):
        bbox_crs = SRS(4326)
    else:
        # Non-Earth data
        bbox_crs = layer.extent.srs.get_geographic_srs()

    bbox = layer.extent.transform(bbox_crs).bbox
    col["extent"] = {"spatial": {"bbox": [bbox]}}
    if bbox_crs.srs_code != "EPSG:4326":
        col["extent"]["spatial"]["crs"] = bbox_crs.to_ogc_url()

    # When the native bbox is not in CRS84/EPSG:4326, you can add an optional
    # "extent"["spatial"]["storageCrsBbox"] member to express it also in its #
    # native CRS.
    if layer.extent.srs != bbox_crs:
        col["extent"]["spatial"]["storageCrsBbox"] = [layer.extent.bbox]

    crs = []
    if layer.extent.srs.srs_code.startswith("EPSG:"):
        crs.append(SRS("OGC:CRS84").to_ogc_url())
        crs.append(SRS(4326).to_ogc_url())
    for srs in server.map_srs:
        if srs.srs_code != "EPSG:4326":
            crs.append(srs.to_ogc_url())
    col["crs"] = crs

    storageSRS = layer.extent.srs
    if storageSRS.srs_code == "EPSG:4326":
        col["storageCrs"] = SRS("OGC:CRS84").to_ogc_url()
    else:
        col["storageCrs"] = storageSRS.to_ogc_url()

    is_html = server.is_html_req(req)
    col["links"] = [
        {
            "rel": ("self" if not is_html else "alternate"),
            "type": FORMAT_TYPES[F_JSON],
            "title": "The JSON representation of this data collection",
            "href": server.create_href(req, f"/ogcapi/collections/{id}?f={F_JSON}"),
        },
        {
            "rel": ("alternate" if not is_html else "self"),
            "type": FORMAT_TYPES[F_HTML],
            "title": "The HTML representation of this data collection",
            "href": server.create_href(req, f"/ogcapi/collections/{id}?f={F_HTML}"),
        },
    ]
    if server.enable_maps:
        col["links"] += [
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                "type": FORMAT_TYPES[F_PNG],
                "title": "Default map (as PNG)",
                "href": server.create_href(req, f"/ogcapi/collections/{id}/map.png"),
            },
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
                "type": FORMAT_TYPES[F_JPEG],
                "title": "Default map (as JPEG)",
                "href": server.create_href(req, f"/ogcapi/collections/{id}/map.jpg"),
            },
        ]
    if server.enable_tiles:
        col["links"] += [
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/tilesets-map",
                "type": FORMAT_TYPES[F_JSON],
                "title": "Map tilesets available for this collection (as JSON)",
                "href": server.create_href(
                    req, f"/ogcapi/collections/{id}/map/tiles?f={F_JSON}"
                ),
            },
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/tilesets-map",
                "type": FORMAT_TYPES[F_HTML],
                "title": "Map tilesets available for this collection (as HTML)",
                "href": server.create_href(
                    req, f"/ogcapi/collections/{id}/map/tiles?f={F_HTML}"
                ),
            },
        ]

    if layer.res_range and layer.res_range.max_res:
        # Not a typo. If my understanding is correct, MapProxy max_res
        # corresponds to OGC minCellSize
        col["minCellSize"] = layer.res_range.max_res
        col["minScaleDenominator"] = res_to_ogc_scale(col["minCellSize"])
    if layer.res_range and layer.res_range.min_res:
        # Not a typo. If my understanding is correct, MapProxy min_res
        # corresponds to OGC maxCellSize
        col["maxCellSize"] = layer.res_range.min_res
        col["maxScaleDenominator"] = res_to_ogc_scale(col["maxCellSize"])

    return col


def collections(server: OGCAPIServer, req: Request):
    log = server.log
    log.debug("Collections page")

    for arg in req.args:
        if arg != "f":
            raise OGCAPIServer.unknown_query_parameter(arg)
    if req.args.get("f", None) not in (None, F_JSON, F_HTML):
        raise OGCAPIServer.invalid_parameter("Invalid value for f query parameter")

    is_html = server.is_html_req(req)
    collections = [
        get_collection(server, req, server.layers[id]) for id in server.layers
    ]
    json_resp = {"collections": collections}

    json_resp["links"] = [
        {
            "rel": ("self" if not is_html else "alternate"),
            "type": FORMAT_TYPES[F_JSON],
            "title": "The JSON representation of the list of all data collections served from this endpoint",
            "href": server.create_href(req, f"/ogcapi/collections?f={F_JSON}"),
        },
        {
            "rel": ("alternate" if not is_html else "self"),
            "type": FORMAT_TYPES[F_HTML],
            "title": "The HTML representation of the list of all data collections served from this endpoint",
            "href": server.create_href(req, f"/ogcapi/collections?f={F_HTML}"),
        },
    ]

    if is_html:
        json_resp["collections_path"] = server.create_href(req, "/ogcapi/collections")

    return server.create_json_or_html_response(req, json_resp, "collections/index.html")


def collection(server: OGCAPIServer, req: Request, coll_id: str):
    log = server.log
    log.debug(f"Collection page for {coll_id}")

    for arg in req.args:
        if arg != "f":
            raise OGCAPIServer.unknown_query_parameter(arg)
    if req.args.get("f", None) not in (None, F_JSON, F_HTML):
        raise OGCAPIServer.invalid_parameter("Invalid value for f query parameter")

    if coll_id not in server.layers:
        raise OGCAPIServer.collection_not_found()

    layer = server.layers[coll_id]
    json_resp = get_collection(server, req, layer)

    is_html = server.is_html_req(req)
    if is_html:
        json_resp["collections_path"] = server.create_href(req, "/ogcapi/collections")
        json_resp["srs"] = layer.extent.srs.srs_code
        json_resp["extent"] = list(layer.extent.bbox)
        json_resp["background_url"] = base_config().background.url

    return server.create_json_or_html_response(
        req, json_resp, "collections/collection.html"
    )
