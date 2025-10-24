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

import json
import sys
from threading import Lock

from mapproxy.client.http import HTTPClientError
from mapproxy.request.base import BaseRequest
from mapproxy.source import SourceError
from mapproxy.source.wms import WMSLikeSource
from mapproxy.srs import ogc_crs_url_to_auth_code, SRS, SupportedSRS
from mapproxy.util.ogcapi import (
    find_href_in_links,
    normalize_srs_code,
    build_absolute_url,
)
from mapproxy.util.py import reraise_exception

import logging

log = logging.getLogger("mapproxy.source.ogcapimaps")

# For testing
reset_config_cache = False


class OGCAPIMapsSource(WMSLikeSource):
    def __init__(
        self,
        landingpage_url,
        collection,
        http_client,
        coverage=None,
        image_opts=None,
        error_handler=None,
        res_range=None,
        supported_srs=None,
        transparent=None,
        transparent_color=None,
        transparent_color_tolerance=None,
        bgcolor=None,
    ):
        WMSLikeSource.__init__(
            self,
            image_opts=image_opts,
            coverage=coverage,
            res_range=res_range,
            transparent_color=transparent_color,
            transparent_color_tolerance=transparent_color_tolerance,
            error_handler=error_handler,
        )

        self.landingpage_url = landingpage_url.rstrip("/")
        self.collection = collection
        self.http_client = http_client
        if transparent is not None:
            self.image_opts.transparent = transparent
        self.bgcolor = bgcolor
        self.supported_srs = supported_srs
        self.supported_srs_from_config = (
            self.supported_srs is not None and len(self.supported_srs.supported_srs) > 0
        )

        self.lock = Lock()
        # Below variables are protected under the lock
        self._reset_config_caches()

    def _reset_config_caches(self):
        self.has_got_maps_list = False
        self.map_format_to_href = {}
        if not self.supported_srs_from_config:
            self.supported_srs = set()
        self.map_crs_code_to_url = {}

    def _build_url(self, href):
        return build_absolute_url(self.landingpage_url, href)

    def _get_maps_list(self):
        with self.lock:
            # Used by tests to avoid caching of "metadata"
            global reset_config_cache
            if reset_config_cache:
                reset_config_cache = False
                self._reset_config_caches()

            if self.has_got_maps_list:
                return
            self.has_got_maps_list = True

            headers = {"Accept": "application/json"}

            url = self.landingpage_url
            if self.collection:
                url += "/collections/" + self.collection
            try:
                resp = self.http_client.open(url, headers=headers)
            except HTTPClientError as e:
                log.warning(f"Cannot retrieve {url}: %s", e)
                raise reraise_exception(SourceError(e.args[0]), sys.exc_info())
            try:
                j = json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                log.warning(f"Cannot parse response to {url} as JSON: %s", e)
                raise reraise_exception(SourceError(e.args[0]), sys.exc_info())

            if "links" not in j:
                ex = SourceError(f"Could not retrieve 'links' in {url} response")
                log.error(ex)
                raise ex

            for mimetype in ("image/png", "image/jpeg"):
                href = find_href_in_links(
                    j["links"],
                    "http://www.opengis.net/def/rel/ogc/1.0/map",
                    mimetype,
                )
                if href:
                    len_image_prefix = len("image/")
                    self.map_format_to_href[
                        mimetype[len_image_prefix:]
                    ] = self._build_url(href)

            if len(self.map_format_to_href) == 0:
                ex = SourceError(f"Could not retrieve a map link in {url} response")
                log.error(ex)
                raise ex

            supported_srs = set()
            if "crs" in j:
                for crs_url in j["crs"]:
                    crs_code = normalize_srs_code(ogc_crs_url_to_auth_code(crs_url))
                    self.map_crs_code_to_url[crs_code] = crs_url
                    supported_srs.add(crs_code)
            if "storageCrs" in j:
                crs_url = j["storageCrs"]
                crs_code = normalize_srs_code(ogc_crs_url_to_auth_code(crs_url))
                self.map_crs_code_to_url[crs_code] = crs_url
                supported_srs.add(crs_code)

            if len(supported_srs) == 0:
                self.map_crs_code_to_url[
                    "EPSG:4326"
                ] = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
                supported_srs.add("EPSG:4326")

            if self.supported_srs_from_config:
                for srs in self.supported_srs.supported_srs:
                    self.map_crs_code_to_url[srs.srs_code] = srs.to_ogc_url()
            else:
                self.supported_srs = SupportedSRS([SRS(crs) for crs in supported_srs])

    def get_map(self, query):
        self._get_maps_list()
        return WMSLikeSource.get_map(self, query)

    def _retrieve(self, query, format):
        url = self.map_format_to_href[format]
        req = BaseRequest(url=url)
        if query.srs.srs_code != "EPSG:4326" and query.srs.is_axis_order_ne:
            req.params["bbox"] = "%.17g,%.17g,%.17g,%.17g" % (
                query.bbox[1],
                query.bbox[0],
                query.bbox[3],
                query.bbox[2],
            )
        else:
            req.params["bbox"] = "%.17g,%.17g,%.17g,%.17g" % (
                query.bbox[0],
                query.bbox[1],
                query.bbox[2],
                query.bbox[3],
            )
        if query.srs.srs_code != "EPSG:4326":
            req.params["bbox-crs"] = self.map_crs_code_to_url[query.srs.srs_code]
        if (
            query.srs.srs_code != "EPSG:4326"
            or len(self.supported_srs.supported_srs) != 1
        ):
            req.params["crs"] = self.map_crs_code_to_url[query.srs.srs_code]
        req.params["width"] = query.size[0]
        req.params["height"] = query.size[1]
        if self.image_opts.transparent:
            req.params["transparent"] = "true"
        if self.bgcolor:
            if len(self.bgcolor) == 4:
                r, g, b, a = self.bgcolor
                req.params["bgcolor"] = "0x%02X%02X%02X%02X" % (a, r, g, b)
            else:
                r, g, b = self.bgcolor
                req.params["bgcolor"] = "0x%02X%02X%02X" % (r, g, b)
        resp = self.http_client.open(req.complete_url)
        return resp
