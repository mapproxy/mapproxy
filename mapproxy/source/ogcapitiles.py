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
from mapproxy.grid.tile_grid import tile_grid_from_ogc_tile_matrix_set
from mapproxy.image.opts import ImageOptions
from mapproxy.layer import BlankImage, MapLayer
from mapproxy.extent import MapExtent, DefaultMapExtent
from mapproxy.source import SourceError, InvalidSourceQuery
from mapproxy.srs import ogc_crs_url_to_auth_code
from mapproxy.util.py import reraise_exception
from mapproxy.util.ogcapi import (
    find_href_in_links,
    normalize_srs_code,
    build_absolute_url,
)

import logging

log = logging.getLogger("mapproxy.source.ogcapitiles")
log_config = logging.getLogger("mapproxy.config")

# For testing
reset_config_cache = False


class OGCAPITilesSource(MapLayer):
    def __init__(
        self,
        landingpage_url,
        collection,
        http_client,
        tile_matrix_set_id=None,
        coverage=None,
        image_opts=None,
        error_handler=None,
        res_range=None,
    ):
        MapLayer.__init__(self, image_opts=image_opts)
        self.landingpage_url = landingpage_url.rstrip("/")
        self.collection = collection
        self.http_client = http_client
        self.image_opts = image_opts or ImageOptions()
        self.tile_matrix_set_id = tile_matrix_set_id
        self.coverage = coverage
        if self.coverage:
            self.extent = MapExtent(self.coverage.bbox, self.coverage.srs)
        else:
            self.extent = DefaultMapExtent()
        self.res_range = res_range
        self.error_handler = error_handler

        self.lock = Lock()
        # Below variables are protected under the lock
        self._reset_config_caches()

    def _reset_config_caches(self):
        self.has_got_tileset_list = False
        self.map_crs_to_tilesets_list = {}
        self.map_srs_to_grid_and_template_url = {}
        self.map_grid_name_to_cachemaplayer = {}

    def _build_url(self, href):
        return build_absolute_url(self.landingpage_url, href)

    def _get_tileset_list(self):
        with self.lock:
            # Used by tests to avoid caching of "metadata"
            global reset_config_cache
            if reset_config_cache:
                reset_config_cache = False
                self._reset_config_caches()

            if self.has_got_tileset_list:
                return

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

            tilesets_map_href = find_href_in_links(
                j["links"],
                "http://www.opengis.net/def/rel/ogc/1.0/tilesets-map",
                "application/json",
            )
            if not tilesets_map_href:
                ex = SourceError(
                    f"Could not retrieve a tilesets-map link in {url} response"
                )
                log.error(ex)
                raise ex

            tilesets_map_url = self._build_url(tilesets_map_href)
            try:
                resp = self.http_client.open(tilesets_map_url, headers=headers)
            except HTTPClientError as e:
                log.warning(f"Cannot retrieve {tilesets_map_url}: %s", e)
                raise reraise_exception(SourceError(e.args[0]), sys.exc_info())
            try:
                j = json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                log.warning(
                    f"Cannot parse response to {tilesets_map_url} as JSON: %s", e
                )
                raise reraise_exception(SourceError(e.args[0]), sys.exc_info())

            if "tilesets" not in j:
                ex = SourceError(
                    f"Could not retrieve 'tilesets' in {tilesets_map_url} response"
                )
                log.error(ex)
                raise ex

            map_tilesets_candidates = filter(
                lambda t: t["dataType"] == "map", j["tilesets"]
            )

            if self.tile_matrix_set_id:
                user_matrix_sets = []
                for tileset in map_tilesets_candidates:
                    tileset_links = tileset["links"]
                    for link in tileset_links:
                        if "href" in link and link["href"].split("?")[0].endswith(
                            "/" + self.tile_matrix_set_id
                        ):
                            user_matrix_sets.append(tileset)
                            break
                map_tilesets_candidates = user_matrix_sets

            for tileset in map_tilesets_candidates:
                crs = normalize_srs_code(ogc_crs_url_to_auth_code(tileset["crs"]))
                if crs not in self.map_crs_to_tilesets_list:
                    self.map_crs_to_tilesets_list[crs] = []
                self.map_crs_to_tilesets_list[crs].append(tileset)

            self.has_got_tileset_list = True

    def _get_grid_and_template_url_from_tileset(self, tileset, image_mime_type):
        links = tileset["links"]
        tiling_scheme_href = find_href_in_links(
            links,
            "http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme",
            "application/json",
        )
        if not tiling_scheme_href:
            ex = SourceError(
                f"Could not retrieve a 'tiling-scheme' link for tileset {tileset}"
            )
            log.error(ex)
            raise ex

        tiling_scheme_url = self._build_url(tiling_scheme_href)

        tileset_href = find_href_in_links(links, "self", "application/json")
        if not tiling_scheme_href:
            ex = SourceError(f"Could not retrieve a 'self' link for tileset {tileset}")
            log.error(ex)
            raise ex

        tileset_url = self._build_url(tileset_href)

        headers = {"Accept": "application/json"}
        try:
            resp = self.http_client.open(tiling_scheme_url, headers=headers)
        except HTTPClientError as e:
            log.warning(f"Cannot retrieve {tiling_scheme_url}: %s", e)
            raise reraise_exception(SourceError(e.args[0]), sys.exc_info())
        try:
            tile_matrix_set = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            log.warning(f"Cannot parse response to {tiling_scheme_url} as JSON: %s", e)
            raise reraise_exception(SourceError(e.args[0]), sys.exc_info())
        grid = tile_grid_from_ogc_tile_matrix_set(tile_matrix_set)

        try:
            resp = self.http_client.open(tileset_url, headers=headers)
        except HTTPClientError as e:
            log.warning(f"Cannot retrieve {tileset_url}: %s", e)
            raise reraise_exception(SourceError(e.args[0]), sys.exc_info())
        try:
            tileset_full = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            log.warning(f"Cannot parse response to {tileset_url} as JSON: %s", e)
            raise reraise_exception(SourceError(e.args[0]), sys.exc_info())

        template_href = find_href_in_links(
            tileset_full["links"], "item", image_mime_type
        )
        if not template_href:
            ex = SourceError(
                f"Could not retrieve a tile template URL for tileset {tileset}"
            )
            log.error(ex)
            raise ex

        return grid, self._build_url(template_href)

    def _get_grid_and_template_url_from_srs(self, query_srs, image_mime_type):
        srs_code = normalize_srs_code(query_srs.srs_code)
        key = srs_code + "/" + image_mime_type

        with self.lock:
            grid_and_template_url = self.map_srs_to_grid_and_template_url.get(key, None)
            if grid_and_template_url:
                return grid_and_template_url

            if srs_code in self.map_crs_to_tilesets_list:
                for tileset in self.map_crs_to_tilesets_list[srs_code]:
                    try:
                        grid_and_template_url = (
                            self._get_grid_and_template_url_from_tileset(
                                tileset, image_mime_type
                            )
                        )
                        break
                    except Exception as e:
                        log.info(f"Exception while evaluating tileset {tileset}: {e}")
                        pass

            if grid_and_template_url is None:
                ex = SourceError(f"Cannot find a valid tile matrix set for {query_srs}")
                log.error(ex)
                raise ex

            self.map_srs_to_grid_and_template_url[key] = grid_and_template_url
            return grid_and_template_url

    def get_map(self, query):
        self._get_tileset_list()
        image_mime_type = "image/" + query.format
        grid, template_url = self._get_grid_and_template_url_from_srs(
            query.srs, image_mime_type
        )

        if grid.tile_size != query.size:
            ex = InvalidSourceQuery(
                "tile size of cache and tile source do not match: %s != %s"
                % (grid.tile_size, query.size)
            )
            log_config.error(ex)
            raise ex

        if grid.srs != query.srs:
            ex = InvalidSourceQuery(
                "SRS of cache and tile source do not match: %r != %r"
                % (grid.srs, query.srs)
            )
            log_config.error(ex)
            raise ex

        if self.res_range and not self.res_range.contains(
            query.bbox, query.size, query.srs
        ):
            raise BlankImage()
        if self.coverage and not self.coverage.intersects(query.bbox, query.srs):
            raise BlankImage()

        _bbox, grid, tiles = grid.get_affected_tiles(query.bbox, query.size)

        if grid != (1, 1):
            raise InvalidSourceQuery("BBOX does not align to tile")

        x, y, z = next(tiles)
        tile_url = (
            template_url.replace("{tileMatrix}", str(z))
            .replace("{tileRow}", str(y))
            .replace("{tileCol}", str(x))
        )
        try:
            return self.http_client.open_image(tile_url)
        except HTTPClientError as e:
            if self.error_handler:
                resp = self.error_handler.handle(e.response_code, query)
                if resp:
                    return resp
            log.warning("could not retrieve tile: %s", e)
            raise reraise_exception(SourceError(e.args[0]), sys.exc_info())
