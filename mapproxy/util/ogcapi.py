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


def find_href_in_links(links, rel, preferred_media_type):
    href = None
    for link in links:
        if link["rel"] == rel:
            if "type" in link and link["type"] == preferred_media_type:
                href = link["href"]
                break
            elif "type" not in link:
                if href is None:
                    href = link["href"]
    return href


def build_absolute_url(root_url, href):
    if href.startswith("/"):
        schema, root_server = root_url.split("://", 1)
        if "/" in root_server:
            host = root_server.split("/", 1)[0]
        else:
            host = root_server
        return schema + "://" + host + href

    return href


def normalize_srs_code(srs_code):
    if srs_code == "OGC:CRS84":
        return "EPSG:4326"
    elif srs_code == "EPSG:900913":
        return "EPSG:3857"
    else:
        return srs_code
