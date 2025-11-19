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

from collections import OrderedDict
import copy
import re
from typing import Optional

from mapproxy.image import (
    bbox_position_in_image,
    sub_image_source,
    BlankImageSource,
    GeoReference,
)
from mapproxy.image.merge import LayerMerger
from mapproxy.image.message import attribution_image
from mapproxy.image.opts import ImageOptions
from mapproxy.extent import MapExtent
from mapproxy.query import MapQuery
from mapproxy.response import Response
from mapproxy.request.base import Request
from mapproxy.service.ogcapi.constants import FORMAT_TYPES, F_PNG, F_JPEG
from mapproxy.service.ogcapi.map_utils import (
    compute_width_height_bbox,
    get_aspect_ratio,
    get_width_height_from_default_size,
)
from mapproxy.service.ogcapi.server import OGCAPIServer, get_image_format
from mapproxy.service.wms import LayerRenderer, WMSGroupLayer, WMSLayerBase
from mapproxy.srs import SRS, ogc_crs_url_to_auth_code

# Cf https://www.w3.org/wiki/CSS/Properties/color/keywords
W3C_BGCOLORS = {
    "black": "#000000",
    "silver": "#C0C0C0",
    "gray": "#808080",
    "white": "#FFFFFF",
    "maroon": "#800000",
    "red": "#FF0000",
    "purple": "#800080",
    "fuchsia": "#FF00FF",
    "green": "#008000",
    "lime": "#00FF00",
    "olive": "#808000",
    "yellow": "#FFFF00",
    "navy": "#000080",
    "blue": "#0000FF",
    "teal": "#008080",
    "aqua": "#00FFFF",
}


def ogcapi_srs_to_srs(s: str):
    """Convert a OGC SRS, expressed either as a OGC CRS URL, "
    a safe CURIE ("[EPSG:4326]") or a unsafe CURIE ("EPSG:4326") to a
    MapProxy SRS object.
    """

    if s.startswith("http"):
        return SRS(ogc_crs_url_to_auth_code(s))
    elif s and s[0] == "[" and s[-1] == "]":
        # Safe CURIE
        return SRS(s[1:-1])
    else:
        # Unsafe CURIE
        return SRS(s)


def subset_to_bbox(subset):
    """Convert the "subset" parameter into a bounding box (list of 4 float)."""

    if not isinstance(subset, list):
        subset = [subset]

    if len(subset) == 1:
        subset = subset[0].split(",")

    if len(subset) != 2:
        raise OGCAPIServer.invalid_parameter("subset must include 2 axis")

    x_axis_set = set(["lon", "long", "longitude", "x", "e", "easting"])
    y_axis_set = set(["lat", "latitude", "y", "n", "northing"])
    bbox = [None, None, None, None]
    for subset_part in subset:
        subset_part = subset_part.lower()
        pattern = re.compile("^(\\w+)\\(([^)]+)\\)$")
        match = pattern.match(subset_part)
        if match is None:
            raise OGCAPIServer.invalid_parameter(f"Invalid subset part {subset_part}")
        axis_name, range_part = match.groups()
        range_part = range_part.split(":")
        if len(range_part) != 2:
            raise OGCAPIServer.invalid_parameter(
                f"Only intervals are supported in subset part {subset_part}"
            )

        if axis_name in x_axis_set:
            idx_min = 0
            idx_max = 2
        elif axis_name in y_axis_set:
            idx_min = 1
            idx_max = 3
        else:
            raise OGCAPIServer.invalid_parameter(
                f"Unsupported axis name {axis_name} in subset part {subset_part}"
            )

        if bbox[idx_min] is not None:
            raise OGCAPIServer.invalid_parameter(
                f"Axis name {axis_name} has been specified in multiple subset parts"
            )

        try:
            bbox[idx_min] = float(range_part[0])
            bbox[idx_max] = float(range_part[1])
        except ValueError:
            raise OGCAPIServer.invalid_parameter(
                f"Non numeric value found in range of subset part {subset_part}"
            )

    return bbox


def get_bbox_center_or_subset_crs(crs, layer, param_name):
    """Return the MapProxy SRS object corresponding to a
    "bbox-center"/"center-crs"/"subset-crs" parameter.
    """
    if crs:
        try:
            return ogcapi_srs_to_srs(crs)
        except ValueError:
            raise OGCAPIServer.invalid_parameter(f"{param_name} is not a valid CRS")
    else:
        if layer.extent.srs.srs_code.startswith("EPSG:"):
            # Default CRS for an earth projection
            return SRS("OGC:CRS84")
        else:
            return layer.extent.srs.get_geographic_srs()


def get_headers(server: OGCAPIServer, query: MapQuery):
    headers = copy.copy(server.response_headers)
    if query.srs.srs_code != "EPSG:4326":
        headers["Content-Crs"] = "<" + query.srs.to_ogc_url() + ">"
    if query.srs.is_axis_order_ne and query.srs.srs_code != "EPSG:4326":
        headers["Content-Bbox"] = "%.17g,%.17g,%.17g,%.17g" % (
            query.bbox[1],
            query.bbox[0],
            query.bbox[3],
            query.bbox[2],
        )
    else:
        headers["Content-Bbox"] = "%.17g,%.17g,%.17g,%.17g" % (
            query.bbox[0],
            query.bbox[1],
            query.bbox[2],
            query.bbox[3],
        )
    return headers


def get_width_height(server: OGCAPIServer, req: Request):
    width = req.args.get("width", None)
    height = req.args.get("height", None)

    if width:
        try:
            width = int(width)
        except ValueError:
            raise OGCAPIServer.invalid_parameter("width is not an integer")
        if width <= 0:
            raise OGCAPIServer.invalid_parameter("width must be strictly positive")

    if height:
        try:
            height = int(height)
        except ValueError:
            raise OGCAPIServer.invalid_parameter("height is not an integer")
        if height <= 0:
            raise OGCAPIServer.invalid_parameter("height must be strictly positive")

    return width, height


def check_width_height(server: OGCAPIServer, req: Request, width: int, height: int):
    if server.max_width and width > server.max_width:
        raise OGCAPIServer.invalid_parameter(
            f"width={width} exceeds max_width={server.max_width}"
        )
    if server.max_height and height > server.max_height:
        raise OGCAPIServer.invalid_parameter(
            f"height={height} exceeds max_height={server.max_height}"
        )
    if server.max_output_pixels and width * height > server.max_output_pixels:
        raise OGCAPIServer.invalid_parameter(
            f"number of pixels {width * height} exceed max_pixels={server.max_output_pixels}"
        )


def get_map_query(
    server: OGCAPIServer, req: Request, layer: WMSLayerBase, format: str
) -> tuple[MapQuery, ImageOptions]:
    """Return a tuple (MapQuery, ImageOptions) from the incoming request"""
    log = server.log

    bbox_crs = req.args.get("bbox-crs", None)
    bbox = req.args.get("bbox", None)
    subset_crs = req.args.get("subset-crs", None)
    subset = (
        req.args.get_all("subset")
        if not isinstance(req.args, dict)
        else req.args.get("subset", None)
    )  # potentially multi valued
    center_crs = req.args.get("center-crs", None)
    center = req.args.get("center", None)
    width, height = get_width_height(server, req)
    scale_denominator = req.args.get("scale-denominator", None)

    try:
        mm_per_pixel = float(req.args.get("mm-per-pixel", "0.28"))
        if mm_per_pixel <= 0:
            raise ValueError
    except ValueError:
        raise OGCAPIServer.invalid_parameter(
            "mm-per-pixel must be a strictly positive numeric value"
        )
    display_res_m_per_px = mm_per_pixel / 1000.0

    if (bbox or center) and subset:
        raise OGCAPIServer.invalid_parameter(
            "(bbox or center) and subset are mutually exclusive"
        )

    crs = req.args.get("crs", None)
    if crs:
        try:
            crs = ogcapi_srs_to_srs(crs)
        except ValueError:
            raise OGCAPIServer.invalid_parameter("crs is not a valid CRS")

        if crs not in server.map_srs:
            raise OGCAPIServer.invalid_parameter("crs is incompatible with this layer")
    elif len(server.map_srs) > 0:
        crs = server.map_srs[0]
    else:
        crs = SRS(4326)

    if subset:
        subset_crs = get_bbox_center_or_subset_crs(subset_crs, layer, "subset-crs")

        bbox = subset_to_bbox(subset)
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            raise OGCAPIServer.invalid_parameter(
                "Invalid range in subset: first value must be less than second one"
            )

        try:
            bbox = MapExtent(bbox, subset_crs).transform(crs).bbox
        except Exception as e:
            raise OGCAPIServer.invalid_parameter(
                f"subset cannot be reprojected from {subset_crs} to {crs}: {e}"
            )

    elif bbox:
        bbox_crs = get_bbox_center_or_subset_crs(bbox_crs, layer, "bbox-crs")
        try:
            bbox = [float(x) for x in bbox.split(",")]
            if len(bbox) != 4 and len(bbox) != 6:
                raise ValueError
        except ValueError:  # catch ValueError from float or local raise
            raise OGCAPIServer.invalid_parameter(
                "bbox must be a list of 4 or 6 numeric values"
            )
        if len(bbox) == 6:
            # Ignore minz / maxz
            bbox = [bbox[0], bbox[1], bbox[3], bbox[4]]
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            raise OGCAPIServer.invalid_parameter(
                "bbox[2] must be greater than bbox[0] and bbox[3] must be greater than bbox[1]"
            )

        if bbox_crs.is_axis_order_ne:
            bbox = [bbox[1], bbox[0], bbox[3], bbox[2]]

        try:
            bbox = MapExtent(bbox, bbox_crs).transform(crs).bbox
        except Exception as e:
            raise OGCAPIServer.invalid_parameter(
                f"bbox cannot be reprojected from {bbox_crs} to {crs}: {e}"
            )

    elif center:
        center_crs = get_bbox_center_or_subset_crs(center_crs, layer, "center-crs")

        try:
            center = [float(x) for x in center.split(",")]
            if len(center) != 2:
                raise ValueError
        except ValueError:  # catch ValueError from float or local raise
            raise OGCAPIServer.invalid_parameter(
                "center must be a list of 2 numeric values"
            )

        if center_crs.is_axis_order_ne:
            new_center = [center[1], center[0]]
            center = new_center

        try:
            center = list(center_crs.transform_to(crs, (center[0], center[1])))
        except Exception as e:
            raise OGCAPIServer.invalid_parameter(
                f"center cannot be reprojected from {center_crs} to {crs}: {e}"
            )

    if scale_denominator:
        try:
            scale_denominator = float(scale_denominator)
        except ValueError:
            raise OGCAPIServer.invalid_parameter(
                "scale-denominator must be a strictly positive numeric value"
            )
        if scale_denominator <= 0:
            raise OGCAPIServer.invalid_parameter(
                "scale-denominator must be a strictly positive numeric value"
            )

    # Cf https://docs.ogc.org/is/20-058/20-058.html#overview-subsetting-and-scaling

    # Cf Table 5 "Always valid requests (no scaling or subsetting parameter)"
    if not (bbox or center or width or height or scale_denominator):
        bbox = layer.extent.transform(crs).bbox
        aspect_ratio = get_aspect_ratio(bbox)
        width, height = get_width_height_from_default_size(aspect_ratio)

    # Cf Table 6 "Always invalid parameter combinations"
    elif bbox and center:
        raise OGCAPIServer.invalid_parameter("bbox and center are mutually exclusive")
    elif bbox and scale_denominator and (width or height):
        raise OGCAPIServer.invalid_parameter(
            "bbox and scale-denominator and (width/height) are mutually exclusive"
        )

    # For all cases below, cf Table 9
    # "Parameter combinations for implementations supporting both Subsetting and Scaling"
    else:
        width, height, bbox = compute_width_height_bbox(
            server,
            req,
            width,
            height,
            bbox,
            crs,
            center,
            scale_denominator,
            display_res_m_per_px,
            layer,
        )

    log.debug(f"width={width}, height={height}, bbox={bbox}, crs={crs}")
    assert width
    assert height
    assert bbox

    check_width_height(server, req, width, height)

    query = MapQuery(bbox, (width, height), crs, format=format)

    image_opts = server.image_formats[FORMAT_TYPES[format]].copy()
    bgcolor = get_bgcolor(server, req)
    if bgcolor:
        image_opts.bgcolor = bgcolor
    image_opts.transparent = get_transparent(req, bgcolor)

    return query, image_opts


def get_bgcolor(server: OGCAPIServer, req: Request):
    bgcolor = req.args.get("bgcolor", None)
    if bgcolor:
        bgcolor = bgcolor.lower()
        if bgcolor.startswith("0x") and len(bgcolor) == 8:
            try:
                R = int(bgcolor[2:4], base=16)
                G = int(bgcolor[4:6], base=16)
                B = int(bgcolor[6:8], base=16)
                bgcolor = (R, G, B)
            except ValueError:
                raise OGCAPIServer.invalid_parameter("invalid value for bgcolor")
        elif bgcolor.startswith("0x") and len(bgcolor) == 10:
            try:
                A = int(bgcolor[2:4], base=16)
                R = int(bgcolor[4:6], base=16)
                G = int(bgcolor[6:8], base=16)
                B = int(bgcolor[8:10], base=16)
                bgcolor = (R, G, B, A)
            except ValueError:
                raise OGCAPIServer.invalid_parameter("invalid value for bgcolor")
        else:
            if bgcolor in W3C_BGCOLORS:
                bgcolor = W3C_BGCOLORS[bgcolor]
                assert len(bgcolor) == 7 and bgcolor[0] == "#"
                bgcolor = (
                    int(bgcolor[1:3], base=16),
                    int(bgcolor[3:5], base=16),
                    int(bgcolor[5:7], base=16),
                )
            else:
                raise OGCAPIServer.invalid_parameter("invalid value for bgcolor")

    return bgcolor


def get_transparent(req: Request, bgcolor):
    transparent = req.args.get("transparent", None)
    if transparent is not None:
        if transparent == "true":
            transparent = True
        elif transparent == "false":
            transparent = False
        else:
            raise OGCAPIServer.invalid_parameter("invalid value for transparent")
    elif bgcolor:
        transparent = True

    return transparent


def render_map(
    server: OGCAPIServer,
    req: Request,
    query: MapQuery,
    image_opts: ImageOptions,
    layer: WMSLayerBase,
) -> Response:
    """Return the image in a Response object from the query."""

    # limit query to srs_extent if query is larger
    orig_query = query
    query_extent = MapExtent(query.bbox, query.srs)
    if not layer.extent.transform(query.srs).contains(query_extent):
        limited_extent = layer.extent.transform(query.srs).intersection(query_extent)
        if not limited_extent:
            img = BlankImageSource(
                size=query.size, image_opts=image_opts, cacheable=True
            )
            return Response(
                img.as_buffer(),
                content_type=FORMAT_TYPES[query.format],
                headers=get_headers(server, query),
                status=200,
            )

        sub_size, offset, sub_bbox = bbox_position_in_image(
            query.bbox, query.size, limited_extent.bbox
        )
        query = MapQuery(sub_bbox, sub_size, query.srs, query.format)

    actual_layers: OrderedDict = OrderedDict()
    # only add if layer renders the query
    if layer.renders_query(query):
        # if layer is not transparent and will be rendered,
        # remove already added (then hidden) layers
        if layer.is_opaque(query):
            actual_layers = OrderedDict()
        for layer_name, map_layers in layer.map_layers_for_query(query):
            actual_layers[layer_name] = map_layers

    render_layers = []
    for layers in actual_layers.values():
        render_layers.extend(layers)

    raise_source_errors = True if server.on_error == "raise" else False
    renderer = LayerRenderer(
        render_layers,
        query,
        req,
        raise_source_errors=raise_source_errors,
        concurrent_rendering=server.concurrent_layer_renderer,
    )

    merger = LayerMerger()
    renderer.render(merger)

    if server.attribution and server.attribution.get("text"):
        merger.add(attribution_image(server.attribution["text"], query.size))

    try:
        result = merger.merge(
            size=query.size, image_opts=image_opts, bbox=query.bbox, bbox_srs=query.srs
        )
    except Exception as ex:
        raise OGCAPIServer.exception(
            "InternalError",
            "error while merging layers: %s" % str(ex),
            status=500,
        )

    if query != orig_query:
        result = sub_image_source(
            result, size=orig_query.size, offset=offset, image_opts=image_opts
        )

    # Provide the wrapping WSGI app or filter the opportunity to process the
    # image before it's wrapped up in a response
    result = server.decorate_img(
        result,
        "ogcapi.map",
        list(actual_layers.keys()),
        req.environ,
        (query.srs.srs_code, query.bbox),
    )

    query = orig_query

    try:
        result.georef = GeoReference(bbox=query.bbox, srs=query.srs)
        result_buf = result.as_buffer(image_opts)
    except IOError as ex:
        raise OGCAPIServer.exception(
            "InternalError",
            "error while processing image file: %s" % ex,
            status=500,
        )

    return Response(
        result_buf,
        content_type=FORMAT_TYPES[query.format],
        headers=get_headers(server, query),
        status=200,
    )


def get_map(
    server: OGCAPIServer, req: Request, coll_id: Optional[str], map_filename: str
):
    log = server.log
    log.debug(f"Map for {coll_id}")

    allowed_args = set(
        [
            "f",
            "crs",
            "bbox-crs",
            "bbox",
            "center-crs",
            "center",
            "subset",
            "subset-crs",
            "width",
            "height",
            "scale-denominator",
            "mm-per-pixel",
            "bgcolor",
            "transparent",
        ]
    )
    collections = req.args.get("collections", None)

    if coll_id is None and (server.default_dataset_layers or collections):
        allowed_args.add("collections")

    if req.args.get("service", None) == "WMS":
        # Hack for the OpenLayers map in our collection.html that issues WMS requests...
        assert "width" in req.args
        assert "height" in req.args
        assert "bbox" in req.args
        assert req.args["version"] == "1.1.1"
        srs = SRS(req.args["srs"])
        if srs.is_axis_order_ne:
            bbox = req.args["bbox"].split(",")
            bbox = "%s,%s,%s,%s" % (bbox[1], bbox[0], bbox[3], bbox[2])
            req.args["bbox"] = bbox
        req.args["bbox-crs"] = req.args["srs"]
        req.args["crs"] = req.args["srs"]
    else:
        for arg in req.args:
            if arg not in allowed_args:
                raise OGCAPIServer.unknown_query_parameter(arg)
        if req.args.get("f", None) not in (None, F_PNG, F_JPEG):
            raise OGCAPIServer.invalid_parameter("Invalid value for f query parameter")

    if coll_id is None:
        # Dataset map
        if collections is None and server.default_dataset_layers is None:
            raise OGCAPIServer.exception(
                "InternalError",
                "Dataset map request but no default_dataset_layers defined in server configuration",
                status=500,
            )

        if collections:
            layers = []
            for col in collections.split(","):
                if col not in server.layers:
                    raise OGCAPIServer.invalid_parameter(f"unknown collection {col}")
                layers.append(server.layers[col])
        else:
            layers = server.default_dataset_layers
        layer = WMSGroupLayer("group_layer", "group_layer", None, layers)
    else:
        if coll_id not in server.layers:
            raise OGCAPIServer.collection_not_found()
        layer = server.layers[coll_id]

    format = get_image_format(req, map_filename)

    query, image_opts = get_map_query(server, req, layer, format)
    return render_map(server, req, query, image_opts, layer)
