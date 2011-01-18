# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

server = ['wms', 'tms', 'kml']

wms = dict(
    image_formats = ['image/jpeg', 'image/png', 'image/gif', 'image/GeoTIFF', 'image/tiff'],
    srs = set(['EPSG:4326', 'EPSG:4258', 'CRS:84', 'EPSG:900913', 'EPSG:31466', 'EPSG:31467', 'EPSG:31468', 'EPSG:25831', 'EPSG:25832', 'EPSG:25833']),
    strict = False,
    request_parser = 'default',
    client_request = 'default',
    concurrent_layer_renderer = 1,
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
)
# number of concurrent requests to a tile source


services_conf = 'services.yaml'
log_conf = 'log.ini'

cache = dict(
    base_dir = '../var/cache_data',
    lock_dir = '../tmp/tile_locks',
    max_tile_limit = 500,
    concurrent_tile_creators = 2,
    meta_size = (4, 4),
    meta_buffer = 80,
    minimize_meta_requests = False,
)

grid = dict(
    tile_size = (256, 256),
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
)
