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
import copy
import json
import mimetypes
import os

import mapproxy.service as service_package
from mapproxy.config.config import base_config
from mapproxy.request.base import Request
from mapproxy.response import Response
from mapproxy.service.base import Server
from mapproxy.service.ogcapi.constants import (
    FORMAT_TYPES,
    F_JSON,
    F_HTML,
    F_PNG,
    F_JPEG,
)
from mapproxy.util.jinja2_templates import render_j2_template

from mapproxy.util.escape import escape_html

import logging

log = logging.getLogger(__name__)


def static_filename(name):
    if base_config().template_dir:
        return os.path.join(base_config().template_dir, name)
    else:
        return (
            importlib_resources.files(service_package.__package__)
            .joinpath("templates")
            .joinpath(name)
        )


class OGCAPIException(Exception):
    def __init__(self, type, detail, status):
        super().__init__()
        self.type = type
        self.detail = detail
        self.status = status


class OGCAPIServer(Server):
    names = ("ogcapi",)

    def __init__(
        self,
        root_layer,
        enable_tiles=True,
        enable_maps=True,
        attribution=None,
        metadata={},
        image_formats=None,
        max_tile_age=None,
        on_error="raise",
        concurrent_layer_renderer=1,
        max_output_pixels=None,
        grid_configs=None,
        map_srs=None,
        default_dataset_layers=None,
    ):
        super().__init__()
        self.enable_tiles = enable_tiles
        self.enable_maps = enable_maps
        self.image_formats = image_formats
        self.layers = root_layer.child_layers()
        self.attribution = attribution
        self.metadata = metadata if metadata else {}
        if "identification" not in self.metadata:
            self.metadata["identification"] = {}
        self.max_tile_age = max_tile_age
        self.on_error = on_error
        self.concurrent_layer_renderer = concurrent_layer_renderer
        self.max_output_pixels = max_output_pixels
        self.max_width = None
        self.max_height = None
        if max_output_pixels:
            self.max_width = int(max_output_pixels**0.5) * 10
            self.max_height = self.max_width
        self.grid_configs = {}
        if grid_configs:
            for name in grid_configs:
                conf = grid_configs[name]
                if name == "GLOBAL_WEBMERCATOR":
                    name = "WebMercatorQuad"
                self.grid_configs[name] = conf
        self.map_srs = map_srs if map_srs else []
        self.default_dataset_layers = default_dataset_layers
        self.response_headers = {}
        self.log = log

    def handle(self, req: Request):
        assert req.path.startswith("/ogcapi")

        if req.path.startswith("/ogcapi/static/") or req.path.startswith(
            "/ogcapi/demo/static/"
        ):
            if ".." in req.path:
                return Response("file not found", content_type="text/plain", status=404)
            filename = req.path.lstrip("/")
            filename = static_filename(filename)
            if not os.path.isfile(filename):
                return Response("file not found", content_type="text/plain", status=404)
            type, encoding = mimetypes.guess_type(filename)
            return Response(open(filename, "rb"), content_type=type)

        path_components = req.path.strip("/").split("/")[1:]
        log.debug(f"Handle request: {path_components} {req.args}")

        map_filenames = ["map", "map.png", "map.jpg", "map.jpeg"]

        try:
            if len(path_components) == 0:
                from mapproxy.service.ogcapi.landing_page import landing_page

                return landing_page(self, req)

            if len(path_components) == 1 and path_components[0] == "conformance":
                from mapproxy.service.ogcapi.conformance import conformance

                return conformance(self, req)

            if len(path_components) == 1 and path_components[0] == "api":
                from mapproxy.service.ogcapi.api import api

                return api(self, req)

            if len(path_components) == 1 and path_components[0] == "collections":
                from mapproxy.service.ogcapi.collections import collections

                return collections(self, req)

            if len(path_components) == 2 and path_components[0] == "collections":
                from mapproxy.service.ogcapi.collections import collection

                return collection(self, req, path_components[1])

            if (
                self.enable_maps
                and len(path_components) == 3
                and path_components[0] == "collections"
                and path_components[2] in map_filenames
            ):
                from mapproxy.service.ogcapi.map import get_map

                return get_map(self, req, path_components[1], path_components[2])

            if (
                self.enable_maps
                and len(path_components) == 1
                and path_components[0] in map_filenames
            ):
                from mapproxy.service.ogcapi.map import get_map

                return get_map(self, req, None, path_components[0])

            if (
                self.enable_tiles
                and len(path_components) == 1
                and path_components[0] == "tileMatrixSets"
            ):
                from mapproxy.service.ogcapi.tilematrixsets import tilematrixsets

                return tilematrixsets(self, req)

            if (
                self.enable_tiles
                and len(path_components) == 2
                and path_components[0] == "tileMatrixSets"
            ):
                from mapproxy.service.ogcapi.tilematrixsets import tilematrixset

                return tilematrixset(self, req, path_components[1])

            if (
                self.enable_tiles
                and len(path_components) == 4
                and path_components[0] == "collections"
                and path_components[2] == "map"
                and path_components[3] == "tiles"
            ):
                from mapproxy.service.ogcapi.tilesets import tilesets

                return tilesets(self, req, path_components[1])

            if (
                self.enable_tiles
                and len(path_components) == 5
                and path_components[0] == "collections"
                and path_components[2] == "map"
                and path_components[3] == "tiles"
            ):
                from mapproxy.service.ogcapi.tilesets import tileset

                return tileset(self, req, path_components[1], path_components[4])

            if (
                self.enable_tiles
                and len(path_components) == 8
                and path_components[0] == "collections"
                and path_components[2] == "map"
                and path_components[3] == "tiles"
            ):
                from mapproxy.service.ogcapi.tile import tile

                return tile(
                    self,
                    req,
                    path_components[1],
                    path_components[4],
                    path_components[5],
                    path_components[6],
                    path_components[7],
                )

            if (
                self.enable_tiles
                and len(path_components) == 2
                and path_components[0] == "map"
                and path_components[1] == "tiles"
            ):
                from mapproxy.service.ogcapi.tilesets import tilesets

                return tilesets(self, req, None)

            if (
                self.enable_tiles
                and len(path_components) == 3
                and path_components[0] == "map"
                and path_components[1] == "tiles"
            ):
                from mapproxy.service.ogcapi.tilesets import tileset

                return tileset(self, req, None, path_components[2])

            if (
                self.enable_tiles
                and len(path_components) == 6
                and path_components[0] == "map"
                and path_components[1] == "tiles"
            ):
                from mapproxy.service.ogcapi.tile import tile

                return tile(
                    self,
                    req,
                    None,
                    path_components[2],
                    path_components[3],
                    path_components[4],
                    path_components[5],
                )

        except OGCAPIException as e:
            json_resp = {
                "title": "OGCAPI",
                "type": e.type,
                "status": e.status,
                "detail": e.detail,
            }
            return self.create_json_or_html_response(
                req, json_resp, "exception.html", status=e.status
            )

    def create_href(self, req: Request, resource):
        return escape_html(req.script_url) + resource

    def is_html_req(self, req):
        return (req.args.get("f", None) == F_HTML) or (
            FORMAT_TYPES[F_HTML] in req.accept_header
            and req.args.get("f", None) != F_JSON
        )

    def get_pygeoapi_config(self, req):
        config = {}
        config["server"] = {}
        config["server"]["url"] = req.host_url + "ogcapi"
        config["server"]["encoding"] = "utf-8"
        config["metadata"] = self.metadata
        return config

    def create_json_or_html_response(
        self, req: Request, json_resp: dict, html_page: str, status=200, headers={}
    ):
        headers = copy.copy(headers)
        headers.update(self.response_headers)

        if self.is_html_req(req):
            content = render_j2_template(
                self.get_pygeoapi_config(req),
                service_package.__package__,
                "ogcapi",
                html_page,
                json_resp,
            )
            return Response(
                content,
                content_type=FORMAT_TYPES[F_HTML],
                headers=headers,
                status=status,
            )
        else:
            return Response(
                json.dumps(json_resp, indent=2),
                content_type=FORMAT_TYPES[F_JSON],
                headers=headers,
                status=status,
            )

    @staticmethod
    def exception(type, detail, status=400):
        return OGCAPIException(type, detail, status)

    @staticmethod
    def collection_not_found():
        return OGCAPIException("Not Found", "Collection not found", status=404)

    @staticmethod
    def unknown_query_parameter(param_name: str):
        return OGCAPIException(
            "Bad Request", f"Unknown query parameter {param_name}", status=400
        )

    @staticmethod
    def invalid_parameter(msg):
        return OGCAPIException("Invalid Parameter", msg, status=400)


def get_image_format(req: Request, map_filename: str):
    """Return the image format (F_PNG/F_JPEG) from the request query parameter
    "f", the Accept header or the extension of the request path.
    """
    f = req.args.get("f", None)
    if map_filename.endswith(".png"):
        format = F_PNG
    elif map_filename.endswith(".jpg") or map_filename.endswith(".jpeg"):
        format = F_JPEG
    elif "." in map_filename:
        pos = map_filename.find(".") + 1
        format = map_filename[pos:]
        raise OGCAPIServer.exception(
            "Not Acceptable", f"Unsupported image format {format}", status=406
        )
    elif f == F_PNG:
        format = F_PNG
    elif f == F_JPEG:
        format = F_JPEG
    elif f:
        raise OGCAPIServer.exception(
            "Not Acceptable", f"Unsupported image format {f}", status=406
        )
    elif FORMAT_TYPES[F_PNG] in req.accept_header:
        format = F_PNG
    elif FORMAT_TYPES[F_JPEG] in req.accept_header:
        format = F_JPEG
    elif req.accept_header and "*/*" not in req.accept_header:
        raise OGCAPIServer.exception(
            "Not Acceptable",
            f"Unsupported image format {req.accept_header}",
            status=406,
        )
    else:
        format = F_PNG

    return format
