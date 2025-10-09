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
import optparse
import sys
import yaml

from mapproxy.client.http import HTTPClient
from mapproxy.grid.tile_grid import (
    tile_grid_from_ogc_tile_matrix_set,
    UnsupportedException,
)
from mapproxy.script.conf.utils import MapProxyYAMLDumper
from mapproxy.util.ogcapi import (
    find_href_in_links,
    build_absolute_url,
    normalize_srs_code,
)


def gridconf_from_ogcapitilematrixset_command(args=None):
    parser = optparse.OptionParser(
        "%prog gridconf-from-ogcapitilematrixset url_to_landing_page"
    )
    parser.add_option("--url", dest="url", help="URL to OGC API landing page.")

    from mapproxy.script.util import setup_logging
    import logging

    setup_logging(logging.WARN)

    if args:
        args = args[1:]  # remove script name

    (options, args) = parser.parse_args(args)
    if not options.url:
        if len(args) != 1:
            parser.print_help()
            sys.exit(1)
        else:
            options.url = args[0]

    conf = get_gridconf(options.url)
    if conf:
        print("Configuration to add to mapproxy.yml:")
        print("")
        print(yaml.dump(conf, default_flow_style=False, Dumper=MapProxyYAMLDumper))
    else:
        sys.exit(0)


def get_gridconf(landing_page_url):
    http_client = HTTPClient(landing_page_url)
    headers = {"Accept": "application/json"}
    resp = http_client.open(landing_page_url, headers=headers)
    j = json.loads(resp.read().decode("utf-8"))

    tilematrixsets_href = find_href_in_links(
        j["links"],
        "http://www.opengis.net/def/rel/ogc/1.0/tiling-schemes",
        "application/json",
    )
    if not tilematrixsets_href:
        print("Cannot find a link to tile matrix set definitions")
        return None
    tilematrixsets_url = build_absolute_url(landing_page_url, tilematrixsets_href)

    resp = http_client.open(tilematrixsets_url, headers=headers)
    j = json.loads(resp.read().decode("utf-8"))

    ret = {"grids": {}}

    for tileMatrixSet in j["tileMatrixSets"]:
        tilematrixset_href = find_href_in_links(
            tileMatrixSet["links"],
            "self",
            "application/json",
        )
        if tilematrixset_href:
            tilematrixset_url = build_absolute_url(landing_page_url, tilematrixset_href)
            resp = http_client.open(tilematrixset_url, headers=headers)
            j = json.loads(resp.read().decode("utf-8"))
            try:
                grid = tile_grid_from_ogc_tile_matrix_set(j)
            except UnsupportedException as e:
                print(f"Cannot handle {tilematrixset_url}: {e}", file=sys.stderr)
                continue
            grid_dict = {}
            grid_dict["srs"] = normalize_srs_code(grid.srs.srs_code)
            grid_dict["bbox"] = grid.bbox
            grid_dict["origin"] = grid.origin
            grid_dict["tile_size"] = [x for x in grid.tile_size]
            grid_dict["res"] = [grid.resolutions[level] for level in range(grid.levels)]
            ret["grids"][grid.name] = grid_dict
        else:
            print(f"Cannot find definition for {tilematrixset_href}", file=sys.stderr)

    return ret
