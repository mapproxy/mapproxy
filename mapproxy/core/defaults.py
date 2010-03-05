client_user_agent = 'Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11'
# client_user_agent = 'Mozilla/5.0 (compatible; proxylib 0.1)'

server = ['wms', 'tms', 'kml']

wms = dict(
    image_formats = ['image/jpeg', 'image/png', 'image/gif', 'image/GeoTIFF', 'image/tiff'],
    srs = set(['EPSG:4326', 'EPSG:4258', 'CRS:84', 'EPSG:900913', 'EPSG:31466', 'EPSG:31467', 'EPSG:31468', 'EPSG:25831', 'EPSG:25832', 'EPSG:25833']),
    request_parser = 'default',
    client_request = 'default',
)
debug_mode = False

image = dict(
    # nearest, bilinear, bicubic
    resampling_method = 'bicubic',
    jpeg_quality = 90,
    stretch_factor = 1.15,
)
# number of concurrent requests to a tile source
tile_creator_pool_size = 2

services_conf = 'services.yaml'
log_conf = 'log.ini'

cache = dict(
    base_dir = '../var/cache_data',
    lock_dir = '../tmp/tile_locks',
    meta_size = (4, 4),
    meta_buffer = 80,
    max_tile_limit = 500,
)
tiles = dict(
    expires_hours = 72,
)

http_client_timeout = 60
