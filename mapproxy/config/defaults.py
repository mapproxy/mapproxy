# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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

server = ['wms', 'tms', 'kml']

wms = dict(
    image_formats = ['image/png', 'image/jpeg', 'image/gif', 'image/GeoTIFF', 'image/tiff'],
    srs = set(['EPSG:4326', 'EPSG:4258', 'CRS:84', 'EPSG:900913', 'EPSG:3857']),
    strict = False,
    request_parser = 'default',
    client_request = 'default',
    concurrent_layer_renderer = 1,
    max_output_pixels = 4000*4000,
)
debug_mode = False

srs = dict(
    # user sets
    axis_order_ne = set(),
    axis_order_en = set(),
    # default sets, both will be combined in config:load_base_config
    axis_order_ne_ = set(['EPSG:4326', 'EPSG:4258', 'EPSG:31466', 'EPSG:31467', 'EPSG:31468']),
    axis_order_en_ = set(['CRS:84', 'EPSG:900913', 'EPSG:25831', 'EPSG:25832', 'EPSG:25833']),
)

image = dict(
    # nearest, bilinear, bicubic
    resampling_method = 'bicubic',
    jpeg_quality = 90,
    stretch_factor = 1.15,
    max_shrink_factor = 4.0,
    paletted = True,
    transparent_color_tolerance = 5,
    font_dir = None,
)
# number of concurrent requests to a tile source


services_conf = 'services.yaml'
log_conf = 'log.ini'

# directory with mapproxy/service/templates/* files
template_dir = None

cache = dict(
    base_dir = './cache_data',
    lock_dir = './cache_data/tile_locks',
    max_tile_limit = 500,
    concurrent_tile_creators = 2,
    meta_size = (4, 4),
    meta_buffer = 80,
    minimize_meta_requests = False,
    link_single_color_images = False,
    sqlite_timeout = 30,
)

grid = dict(
    tile_size = (256, 256),
)

grids = dict(
    GLOBAL_GEODETIC=dict(
        srs='EPSG:4326', origin='sw', name='GLOBAL_GEODETIC'
    ),
    GLOBAL_MERCATOR=dict(
        srs='EPSG:900913', origin='sw', name='GLOBAL_MERCATOR'
    ),
    GLOBAL_WEBMERCATOR=dict(
        srs='EPSG:3857', origin='nw', name='GLOBAL_WEBMERCATOR'
    )
)

tiles = dict(
    expires_hours = 72,
)

http = dict(
    ssl_ca_certs = None,
    ssl_no_cert_checks = False,
    client_timeout = 60,
    concurrent_requests = 0,
    method = 'AUTO',
    access_control_allow_origin = '*',
)
