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

from mapproxy.grid.resolutions import ogc_scale_to_res, deg_to_m
from mapproxy.request.base import Request
from mapproxy.service.ogcapi.server import OGCAPIServer
from mapproxy.service.wms import WMSLayerBase
from mapproxy.srs import _SRS
from mapproxy.util.bbox import bbox_from_center

DEFAULT_SIZE = 1024


def res_display_res_m_per_px_to_crs_res(res_display_res_m_per_px, crs: _SRS):
    """Convert a resolution expressed in meter/pixel to the geospatial units
    of the CRS/pixel.
    """

    if crs.is_latlong:
        return res_display_res_m_per_px / deg_to_m(
            1, semi_major_meters=crs.semi_major_meters()
        )
    else:
        return res_display_res_m_per_px


def scale_denominator_to_crs_res(scale_denominator, display_res_m_per_px, crs: _SRS):
    """Convert a OGC scale denominator to the CRS resolution."""
    return res_display_res_m_per_px_to_crs_res(
        ogc_scale_to_res(scale_denominator, display_res_m_per_px), crs
    )


def get_crs_res(
    server: OGCAPIServer,
    req: Request,
    scale_denominator,
    display_res_m_per_px,
    layer,
    crs: _SRS,
):
    """Return the resolution in CRS unit/pixel of the request from the
    "scale-denominator" parameter of the request,
    or the nominal_scale attribute of the layer (from user configuration).
    """
    if scale_denominator:
        res = scale_denominator_to_crs_res(scale_denominator, display_res_m_per_px, crs)
    else:
        if layer.nominal_scale:
            res = res_display_res_m_per_px_to_crs_res(
                ogc_scale_to_res(layer.nominal_scale, display_res_m_per_px), crs
            )
        else:
            raise OGCAPIServer.exception(
                "InternalError",
                f"Layer {layer.name} lacks a mominal_res/nominal_scale setting",
                status=500,
            )
    return res


def get_center(a_bbox):
    """Return the center of a bounding box."""
    return [(a_bbox[0] + a_bbox[2]) / 2, (a_bbox[1] + a_bbox[3]) / 2]


def compute_bbox(center, width, height, res):
    """Compute a bounding box from its center, the (width, height) in pixels
    and the resolution (in CRS unit/pixel).
    """
    width_geo = compute_width_geo(width, res)
    height_geo = compute_height_geo(height, res)
    return bbox_from_center(center[0], center[1], width_geo, height_geo)


def compute_width_geo(width, res):
    """Compute the width in geospatial units from the width in pixel and the
    resolution (in CRS unit/pixel).
    """
    return width * res


def compute_width_from_geo(width_geo, res):
    """Compute the width in pixels from the width in geospatial units and the
    resolution (in CRS unit/pixel).
    """
    return max(1, round(width_geo / res))


def compute_height_geo(height, res):
    """Compute the height in geospatial units from the height in pixel and the
    resolution (in CRS unit/pixel).
    """
    return height * res


def compute_height_from_geo(height_geo, res):
    """Compute the height in pixels from the height in geospatial units and the
    resolution (in CRS unit/pixel).
    """

    return max(1, round(height_geo / res))


def width_from_height(height, aspect_ratio):
    """Compute the width in pixel from the height in pixel preserving the
    aspect ratio.
    """
    return max(1, round(height * aspect_ratio))


def height_from_width(width, aspect_ratio):
    """Compute the height in pixel from the width in pixel preserving the
    aspect ratio.
    """
    return max(1, round(width / aspect_ratio))


def get_width_height_from_default_size(aspect_ratio):
    """Return a tuple (width, height) following the aspect_ratio and such
    that max(width, height) <= DEFAULT_SIZE
    """
    if aspect_ratio >= 1:
        width = DEFAULT_SIZE
        height = height_from_width(width, aspect_ratio)
    else:
        height = DEFAULT_SIZE
        width = width_from_height(height, aspect_ratio)
    return width, height


def get_width_height_from_width_height_default_size(width, height, aspect_ratio):
    """Return a tuple (width, height) following the aspect_ratio.
    The input width or height can be None.
    """
    if not width and not height:
        width, height = get_width_height_from_default_size(aspect_ratio)
    elif width and not height:
        height = height_from_width(width, aspect_ratio)
    elif height and not width:
        width = width_from_height(height, aspect_ratio)
    return width, height


def get_aspect_ratio(a_bbox):
    """Return the ratio width/height of a (georeferenced) bounding box."""
    return (a_bbox[2] - a_bbox[0]) / (a_bbox[3] - a_bbox[1])


def compute_width_height_bbox(
    server: OGCAPIServer,
    req: Request,
    width: Optional[int],
    height: Optional[int],
    bbox,
    crs,
    center,
    scale_denominator,
    display_res_m_per_px,
    layer: WMSLayerBase,
):
    """Returns a tuple (width, height, bbox) from query parameters of a map
    request.

    Implements Table 9
    "Parameter combinations for implementations supporting both Subsetting and Scaling"
    """

    if (width or height) and not (center or bbox or scale_denominator):
        whole_bbox = layer.extent.transform(crs).bbox
        aspect_ratio = get_aspect_ratio(whole_bbox)
        center = get_center(whole_bbox)
        res = get_crs_res(
            server, req, scale_denominator, display_res_m_per_px, layer, crs
        )
        if width and not height:
            height = height_from_width(width, aspect_ratio)
        elif height and not width:
            width = width_from_height(height, aspect_ratio)
        bbox = compute_bbox(center, width, height, res)

    elif bbox and not (scale_denominator or width or height):
        aspect_ratio = get_aspect_ratio(bbox)
        width, height = get_width_height_from_default_size(aspect_ratio)

    elif center and not (scale_denominator or width or height):
        whole_bbox = layer.extent.transform(crs).bbox
        aspect_ratio = get_aspect_ratio(whole_bbox)
        res = get_crs_res(
            server, req, scale_denominator, display_res_m_per_px, layer, crs
        )
        width, height = get_width_height_from_default_size(aspect_ratio)
        bbox = compute_bbox(center, width, height, res)

    elif center and (width or height) and not scale_denominator:
        whole_bbox = layer.extent.transform(crs).bbox
        aspect_ratio = get_aspect_ratio(whole_bbox)
        res = get_crs_res(
            server, req, scale_denominator, display_res_m_per_px, layer, crs
        )
        width, height = get_width_height_from_width_height_default_size(
            width, height, aspect_ratio
        )
        bbox = compute_bbox(center, width, height, res)

    elif scale_denominator and not bbox:
        whole_bbox = layer.extent.transform(crs).bbox
        aspect_ratio = get_aspect_ratio(whole_bbox)
        if not center:
            center = get_center(whole_bbox)
        width, height = get_width_height_from_width_height_default_size(
            width, height, aspect_ratio
        )
        res = get_crs_res(
            server, req, scale_denominator, display_res_m_per_px, layer, crs
        )
        bbox = compute_bbox(center, width, height, res)

    elif bbox:
        if width and height:
            # Completely specified (WMS case)
            pass
        elif width or height:
            aspect_ratio = get_aspect_ratio(bbox)
            width, height = get_width_height_from_width_height_default_size(
                width, height, aspect_ratio
            )
        else:
            assert scale_denominator
            width_geo = bbox[2] - bbox[0]
            height_geo = bbox[3] - bbox[1]
            res = get_crs_res(
                server, req, scale_denominator, display_res_m_per_px, layer, crs
            )
            width = compute_width_from_geo(width_geo, res)
            height = compute_height_from_geo(height_geo, res)

    elif center:
        assert scale_denominator
        assert width or height
        if not (width and height):
            whole_bbox = layer.extent.transform(crs).bbox
            aspect_ratio = get_aspect_ratio(whole_bbox)
            width, height = get_width_height_from_width_height_default_size(
                width, height, aspect_ratio
            )
        res = get_crs_res(
            server, req, scale_denominator, display_res_m_per_px, layer, crs
        )
        bbox = compute_bbox(center, width, height, res)

    else:
        # I don't think this should happen since hopefully all above cases
        # encompass all the possible cases, but that's not so obvious !
        raise OGCAPIServer.exception(
            "InternalError",
            "unexpected combination of query parameters",
            status=500,
        )

    return width, height, bbox
