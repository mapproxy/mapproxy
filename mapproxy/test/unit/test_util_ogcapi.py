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

from mapproxy.util.ogcapi import (
    find_href_in_links,
    build_absolute_url,
    normalize_srs_code,
)


def test_find_href_in_links():
    links = [
        {
            "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
            "title": "Default map (as PNG)",
            "href": "/ogcapi/collections/my_collection/map.png",
        },
        {
            "rel": "[ogc-rel:map]",
            "type": "image/jpeg",
            "title": "Default map (as JPG)",
            "href": "/ogcapi/collections/my_collection/map.jpg",
        },
        {
            "rel": "http://www.opengis.net/def/rel/ogc/1.0/map",
            "type": "image/tiff",
            "title": "Default map (as TIFF)",
            "href": "/ogcapi/collections/my_collection/map.tif",
        },
    ]

    assert (
        find_href_in_links(
            links, "http://www.opengis.net/def/rel/ogc/1.0/map", "image/jpeg"
        )
        == "/ogcapi/collections/my_collection/map.jpg"
    )


def test_build_absolute_url():
    assert build_absolute_url("http://example.com", "/foo") == "http://example.com/foo"
    assert (
        build_absolute_url("http://example.com/foo", "/bar") == "http://example.com/bar"
    )
    assert (
        build_absolute_url("http://example.com", "http://example.com/bar")
        == "http://example.com/bar"
    )


def test_normalize_srs_code():
    assert normalize_srs_code("OGC:CRS84") == "EPSG:4326"
    assert normalize_srs_code("EPSG:900913") == "EPSG:3857"
    assert normalize_srs_code("EPSG:32631") == "EPSG:32631"
