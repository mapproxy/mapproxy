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
from typing import Optional

from mapproxy.query import MapQuery
from mapproxy.request.base import Request
from mapproxy.service.ogcapi.server import OGCAPIException, OGCAPIServer
from mapproxy.service.ogcapi.constants import FORMAT_TYPES, F_PNG, F_JPEG
from mapproxy.service.ogcapi.map import (
    render_map,
    get_bgcolor,
    get_transparent,
    get_width_height,
    check_width_height,
)
from mapproxy.service.ogcapi.map_utils import scale_denominator_to_crs_res
from mapproxy.service.ogcapi.server import get_image_format
from mapproxy.service.wms import WMSGroupLayer


def tile(
    server: OGCAPIServer,
    req: Request,
    coll_id: Optional[str],
    tms_name: str,
    z_str: str,
    row_str: str,
    col_ext: str,
):
    log = server.log
    log.debug("Tile")

    allowed_args = set(
        [
            "f",
            "bgcolor",
            "transparent",
        ]
    )
    if coll_id is None:
        allowed_args.add("collections")

    if server.enable_maps:
        allowed_args.add("width")
        allowed_args.add("height")
        allowed_args.add("scale-denominator")
        allowed_args.add("mm-per-pixel")

    for arg in req.args:
        if arg not in allowed_args:
            raise OGCAPIServer.unknown_query_parameter(arg)
    if req.args.get("f", None) not in (None, F_PNG, F_JPEG):
        raise OGCAPIServer.invalid_parameter("Invalid value for f query parameter")

    if coll_id is None:
        collections = req.args.get("collections", None)
        if collections is None and server.default_dataset_layers is None:
            raise OGCAPIServer.exception(
                "InternalError",
                "Dataset tile request but no default_dataset_layers defined in server configuration",
                status=500,
            )
    else:
        if coll_id not in server.layers:
            raise OGCAPIServer.collection_not_found()

    if tms_name not in server.grid_configs:
        raise OGCAPIException("Not Found", "TileMatrixSet not found", status=404)

    format = get_image_format(req, col_ext)

    tile_grid = server.grid_configs[tms_name].tile_grid()
    width, height = get_width_height(server, req)

    try:
        z = int(z_str)
        if z < 0 or z >= tile_grid.levels:
            raise ValueError
    except ValueError:
        raise OGCAPIServer.invalid_parameter(
            f"Invalid zoom level. Valid range is [0,{tile_grid.levels - 1}]"
        )

    try:
        mm_per_pixel = float(req.args.get("mm-per-pixel", "0.28"))
        if mm_per_pixel <= 0:
            raise ValueError
    except ValueError:
        raise OGCAPIServer.invalid_parameter(
            "mm-per-pixel must be a strictly positive numeric value"
        )
    display_res_m_per_px = mm_per_pixel / 1000.0

    zoom_factor = 0.00028 / display_res_m_per_px
    cellSize = tile_grid.resolutions[z]
    scale_denominator = req.args.get("scale-denominator", None)
    tileWidth = tile_grid.tile_size[0]
    tileHeight = tile_grid.tile_size[1]
    renderWidth = int(round(tileWidth * zoom_factor))
    renderHeight = int(round(tileHeight * zoom_factor))

    if scale_denominator and (width or height):
        raise OGCAPIServer.invalid_parameter(
            "scale-denominator is mutually exclusive with width or height"
        )

    if width and height:
        renderWidth = width
        renderHeight = height
    elif scale_denominator:
        try:
            scale_denominator = float(scale_denominator)
            if scale_denominator <= 0:
                raise ValueError
        except ValueError:
            raise OGCAPIServer.invalid_parameter(
                "scale-denominator must be a strictly positive numeric value"
            )

        res = scale_denominator_to_crs_res(
            scale_denominator, display_res_m_per_px, tile_grid.srs
        )
        zoom_factor = cellSize / res
        renderWidth = int(round(tileWidth * zoom_factor))
        renderHeight = int(round(tileHeight * zoom_factor))
    elif width:
        renderWidth = width
        renderHeight = int(round(renderWidth * tileWidth / tileHeight))
    elif height:
        renderHeight = height
        renderWidth = int(round(renderHeight * tileHeight / tileWidth))

    check_width_height(server, req, renderWidth, renderHeight)

    matrixWidth = tile_grid.grid_sizes[z][0]
    matrixHeight = tile_grid.grid_sizes[z][1]

    try:
        row = int(row_str)
        if row < 0 or row >= matrixHeight:
            raise ValueError
    except ValueError:
        raise OGCAPIServer.invalid_parameter(
            f"Invalid row number. Valid range is [0,{matrixHeight - 1}]"
        )

    dot_pos = col_ext.find(".")
    if dot_pos > 0:
        col_str = col_ext[0:dot_pos]
    else:
        col_str = col_ext

    try:
        col = int(col_str)
        if col < 0 or col >= matrixWidth:
            raise ValueError
    except ValueError:
        raise OGCAPIServer.invalid_parameter(
            f"Invalid col number. Valid range is [0,{matrixWidth - 1}]"
        )

    if tile_grid.origin == "ul":
        bbox = (
            tile_grid.bbox[0] + col * tileWidth * cellSize,
            tile_grid.bbox[3] - (row + 1) * tileHeight * cellSize,
            tile_grid.bbox[0] + (col + 1) * tileWidth * cellSize,
            tile_grid.bbox[3] - row * tileHeight * cellSize,
        )
    else:
        bbox = (
            tile_grid.bbox[0] + col * tileWidth * cellSize,
            tile_grid.bbox[1] + row * tileHeight * cellSize,
            tile_grid.bbox[0] + (col + 1) * tileWidth * cellSize,
            tile_grid.bbox[1] + (row + 1) * tileHeight * cellSize,
        )
    query = MapQuery(bbox, (renderWidth, renderHeight), tile_grid.srs, format=format)

    image_opts = server.image_formats[FORMAT_TYPES[format]].copy()
    bgcolor = get_bgcolor(server, req)
    if bgcolor:
        image_opts.bgcolor = bgcolor
    image_opts.transparent = get_transparent(req, bgcolor)

    if coll_id:
        layer = server.layers[coll_id]
    else:
        if collections:
            layers = []
            for col in collections.split(","):
                if col not in server.layers:
                    raise OGCAPIServer.invalid_parameter(f"unknown collection {col}")
                layers.append(server.layers[col])
        else:
            layers = server.default_dataset_layers
        layer = WMSGroupLayer(
            "group_layer", "group_layer", None, server.default_dataset_layers
        )

    return render_map(server, req, query, image_opts, layer)
