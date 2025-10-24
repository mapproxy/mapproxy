from __future__ import division

import os
import sys
from functools import partial

from mapproxy.config.configuration.base import ConfigurationBase
from mapproxy.config.configuration.base import ConfigurationError, parse_color
from mapproxy.util.py import memoize

import logging

log = logging.getLogger('mapproxy.config')


class CacheConfiguration(ConfigurationBase):
    defaults = {'format': 'image/png'}

    @memoize
    def coverage(self):
        if 'cache' not in self.conf or 'coverage' not in self.conf['cache']:
            return None
        from mapproxy.config.coverage import load_coverage
        return load_coverage(self.conf['cache']['coverage'])

    @memoize
    def cache_dir(self):
        cache_dir = self.conf.get('cache', {}).get('directory')
        if cache_dir:
            if self.conf.get('cache_dir'):
                log.warning('found cache.directory and cache_dir option for %s, ignoring cache_dir',
                            self.conf['name'])
            return self.context.globals.abspath(cache_dir)

        return self.context.globals.get_path('cache_dir', self.conf,
                                             global_key='cache.base_dir')

    @memoize
    def directory_permissions(self):
        directory_permissions = self.conf.get('cache', {}).get('directory_permissions')
        if directory_permissions:
            log.info('Using cache specific directory permission configuration for %s: %s',
                     self.conf['name'], directory_permissions)
            return directory_permissions

        global_permissions = self.context.globals.get_value('directory_permissions', self.conf,
                global_key='cache.directory_permissions')
        if global_permissions:
            log.info('Using global directory permission configuration for %s: %s',
                 self.conf['name'], global_permissions)
        return global_permissions

    @memoize
    def file_permissions(self):
        file_permissions = self.conf.get('cache', {}).get('file_permissions')
        if file_permissions:
            log.info('Using cache specific file permission configuration for %s: %s',
                     self.conf['name'], file_permissions)
            return file_permissions

        global_permissions = self.context.globals.get_value('file_permissions', self.conf,
                global_key='cache.file_permissions')
        if global_permissions:
            log.info('Using global file permission configuration for %s: %s',
                 self.conf['name'], global_permissions)
        return global_permissions

    @memoize
    def has_multiple_grids(self):
        return len(self.grid_confs()) > 1

    def lock_dir(self):
        lock_dir = self.context.globals.get_path('cache.tile_lock_dir', self.conf)
        if not lock_dir:
            lock_dir = os.path.join(self.cache_dir(), 'tile_locks')
        return lock_dir

    def _file_cache(self, grid_conf, image_opts):
        from mapproxy.cache.file import FileCache

        cache_dir = self.cache_dir()
        directory_layout = self.conf.get('cache', {}).get('directory_layout', 'tc')
        coverage = self.coverage()

        if self.conf.get('cache', {}).get('directory'):
            if self.has_multiple_grids():
                raise ConfigurationError(
                    "using single directory for cache with multiple grids in %s" %
                    (self.conf['name']),
                )
            pass
        elif self.conf.get('cache', {}).get('use_grid_names'):
            cache_dir = os.path.join(cache_dir, self.conf['name'], grid_conf.tile_grid().name)
        else:
            suffix = grid_conf.conf['srs'].replace(':', '')
            cache_dir = os.path.join(cache_dir, self.conf['name'] + '_' + suffix)
        link_single_color_images = self.context.globals.get_value('link_single_color_images', self.conf,
                                                                  global_key='cache.link_single_color_images')

        if link_single_color_images and sys.platform == 'win32':
            log.warning('link_single_color_images not supported on windows')
            link_single_color_images = False

        return FileCache(
            cache_dir,
            file_ext=image_opts.format.ext,
            image_opts=image_opts,
            directory_layout=directory_layout,
            link_single_color_images=link_single_color_images,
            coverage=coverage,
            directory_permissions=self.directory_permissions(),
            file_permissions=self.file_permissions()
        )

    def _mbtiles_cache(self, grid_conf, image_opts):
        from mapproxy.cache.mbtiles import MBTilesCache

        filename = self.conf['cache'].get('filename')
        if not filename:
            filename = self.conf['name'] + '.mbtiles'

        if filename.startswith('.' + os.sep):
            mbfile_path = self.context.globals.abspath(filename)
        else:
            mbfile_path = os.path.join(self.cache_dir(), filename)

        sqlite_timeout = self.context.globals.get_value('cache.sqlite_timeout', self.conf)
        wal = self.context.globals.get_value('cache.sqlite_wal', self.conf)
        coverage = self.coverage()

        return MBTilesCache(
            mbfile_path,
            timeout=sqlite_timeout,
            wal=wal,
            coverage=coverage,
            directory_permissions=self.directory_permissions(),
            file_permissions=self.file_permissions()
        )

    def _geopackage_cache(self, grid_conf, image_opts):
        from mapproxy.cache.geopackage import GeopackageCache, GeopackageLevelCache

        filename = self.conf['cache'].get('filename')
        table_name = self.conf['cache'].get('table_name') or \
            "{}_{}".format(self.conf['name'], grid_conf.tile_grid().name)
        levels = self.conf['cache'].get('levels')
        coverage = self.coverage()

        if not filename:
            filename = self.conf['name'] + '.gpkg'
        if filename.startswith('.' + os.sep):
            gpkg_file_path = self.context.globals.abspath(filename)
        else:
            gpkg_file_path = os.path.join(self.cache_dir(), filename)

        cache_dir = self.conf['cache'].get('directory')
        if cache_dir:
            cache_dir = os.path.join(
                self.context.globals.abspath(cache_dir),
                grid_conf.tile_grid().name
            )
        else:
            cache_dir = self.cache_dir()
            cache_dir = os.path.join(
                cache_dir,
                self.conf['name'],
                grid_conf.tile_grid().name
            )

        if levels:
            return GeopackageLevelCache(
                cache_dir,
                grid_conf.tile_grid(),
                table_name,
                coverage=coverage,
                directory_permissions=self.directory_permissions(),
                file_permissions=self.file_permissions()
            )
        else:
            return GeopackageCache(
                gpkg_file_path,
                grid_conf.tile_grid(),
                table_name,
                coverage=coverage,
                directory_permissions=self.directory_permissions(),
                file_permissions=self.file_permissions()
            )

    def _azureblob_cache(self, grid_conf, image_opts):
        from mapproxy.cache.azureblob import AzureBlobCache

        container_name = self.context.globals.get_value('cache.container_name', self.conf,
                                                        global_key='cache.azureblob.container_name')
        coverage = self.coverage()

        if not container_name:
            raise ConfigurationError("no container_name configured for Azure Blob cache %s" % self.conf['name'])

        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", self.context.globals.get_value(
            'cache.connection_string', self.conf, global_key='cache.azureblob.connection_string'))

        if not connection_string:
            raise ConfigurationError("no connection_string configured for Azure Blob cache %s" % self.conf['name'])

        directory_layout = self.conf['cache'].get('directory_layout', 'tms')

        base_path = self.conf['cache'].get('directory', None)
        if base_path is None:
            base_path = os.path.join(self.conf['name'], grid_conf.tile_grid().name)

        return AzureBlobCache(
            base_path=base_path,
            file_ext=image_opts.format.ext,
            directory_layout=directory_layout,
            container_name=container_name,
            connection_string=connection_string,
            coverage=coverage
        )

    def _s3_cache(self, grid_conf, image_opts):
        from mapproxy.cache.s3 import S3Cache

        bucket_name = self.context.globals.get_value('cache.bucket_name', self.conf,
                                                     global_key='cache.s3.bucket_name')
        coverage = self.coverage()

        if not bucket_name:
            raise ConfigurationError("no bucket_name configured for s3 cache %s" % self.conf['name'])

        profile_name = self.context.globals.get_value('cache.profile_name', self.conf,
                                                      global_key='cache.s3.profile_name')

        region_name = self.context.globals.get_value('cache.region_name', self.conf,
                                                     global_key='cache.s3.region_name')

        endpoint_url = self.context.globals.get_value('cache.endpoint_url', self.conf,
                                                      global_key='cache.s3.endpoint_url')

        access_control_list = self.context.globals.get_value('cache.access_control_list', self.conf,
                                                             global_key='cache.s3.access_control_list')

        use_http_get = self.context.globals.get_value('cache.use_http_get', self.conf,
                                                      global_key='cache.s3.use_http_get'
                                                      )

        include_grid_name = self.context.globals.get_value('cache.include_grid_name', self.conf,
                                                      global_key='cache.s3.include_grid_name')

        directory_layout = self.conf['cache'].get('directory_layout', 'tms')

        base_path = self.conf['cache'].get('directory', None)

        if include_grid_name and base_path:
            base_path = os.path.join(base_path, grid_conf.tile_grid().name)

        if base_path is None:
            base_path = os.path.join(self.conf['name'], grid_conf.tile_grid().name)

        return S3Cache(
            base_path=base_path,
            file_ext=image_opts.format.ext,
            directory_layout=directory_layout,
            bucket_name=bucket_name,
            profile_name=profile_name,
            region_name=region_name,
            endpoint_url=endpoint_url,
            access_control_list=access_control_list,
            coverage=coverage,
            use_http_get=use_http_get
        )

    def _sqlite_cache(self, grid_conf, image_opts):
        from mapproxy.cache.mbtiles import MBTilesLevelCache

        cache_dir = self.conf.get('cache', {}).get('directory')
        if cache_dir:
            cache_dir = os.path.join(
                self.context.globals.abspath(cache_dir),
                grid_conf.tile_grid().name
            )
        else:
            cache_dir = self.cache_dir()
            cache_dir = os.path.join(
                cache_dir,
                self.conf['name'],
                grid_conf.tile_grid().name
            )

        sqlite_timeout = self.context.globals.get_value('cache.sqlite_timeout', self.conf)
        wal = self.context.globals.get_value('cache.sqlite_wal', self.conf)
        coverage = self.coverage()

        return MBTilesLevelCache(
            cache_dir,
            timeout=sqlite_timeout,
            wal=wal,
            ttl=self.conf.get('cache', {}).get('ttl', 0),
            coverage=coverage,
            directory_permissions=self.directory_permissions(),
            file_permissions=self.file_permissions()
        )

    def _couchdb_cache(self, grid_conf, image_opts):
        from mapproxy.cache.couchdb import CouchDBCache, CouchDBMDTemplate

        db_name = self.conf['cache'].get('db_name')
        if not db_name:
            suffix = grid_conf.conf['srs'].replace(':', '')
            db_name = self.conf['name'] + '_' + suffix

        url = self.conf['cache'].get('url')
        if not url:
            url = 'http://127.0.0.1:5984'

        md_template = CouchDBMDTemplate(self.conf['cache'].get('tile_metadata', {}))
        tile_id = self.conf['cache'].get('tile_id')
        coverage = self.coverage()

        return CouchDBCache(
            url=url,
            db_name=db_name,
            file_ext=image_opts.format.ext,
            tile_grid=grid_conf.tile_grid(),
            md_template=md_template,
            tile_id_template=tile_id,
            coverage=coverage
        )

    def _redis_cache(self, grid_conf, image_opts):
        from mapproxy.cache.redis import RedisCache

        host = self.conf['cache'].get('host', '127.0.0.1')
        port = self.conf['cache'].get('port', 6379)
        db = self.conf['cache'].get('db', 0)
        ttl = self.conf['cache'].get('default_ttl', 3600)
        username = self.conf['cache'].get('username', None)
        password = self.conf['cache'].get('password', None)
        coverage = self.coverage()
        ssl_certfile = self.conf['cache'].get('ssl_certfile', None)
        ssl_keyfile = self.conf['cache'].get('ssl_keyfile', None)
        ssl_ca_certs = self.conf['cache'].get('ssl_ca_certs', None)
        prefix = self.conf['cache'].get('prefix')
        if not prefix:
            prefix = self.conf['name'] + '_' + grid_conf.tile_grid().name

        return RedisCache(
            host=host,
            port=port,
            db=db,
            username=username,
            password=password,
            prefix=prefix,
            ttl=ttl,
            coverage=coverage,
            ssl_certfile=ssl_certfile,
            ssl_keyfile=ssl_keyfile,
            ssl_ca_certs=ssl_ca_certs
        )

    def _compact_cache(self, grid_conf, image_opts):
        from mapproxy.cache.compact import CompactCacheV1, CompactCacheV2

        coverage = self.coverage()
        cache_dir = self.cache_dir()
        if self.conf.get('cache', {}).get('directory'):
            if self.has_multiple_grids():
                raise ConfigurationError(
                    "using single directory for cache with multiple grids in %s" %
                    (self.conf['name']),
                )
            pass
        else:
            cache_dir = os.path.join(cache_dir, self.conf['name'], grid_conf.tile_grid().name)

        version = self.conf['cache']['version']
        if version == 1:
            return CompactCacheV1(
                cache_dir=cache_dir,
                coverage=coverage,
                directory_permissions=self.directory_permissions(),
                file_permissions=self.file_permissions()
            )
        elif version == 2:
            return CompactCacheV2(
                cache_dir=cache_dir,
                coverage=coverage,
                directory_permissions=self.directory_permissions(),
                file_permissions=self.file_permissions()
            )

        raise ConfigurationError("compact cache only supports version 1 or 2")

    def _tile_cache(self, grid_conf, image_opts):
        if self.conf.get('disable_storage', False):
            from mapproxy.cache.dummy import DummyCache
            return DummyCache()

        grid_conf.tile_grid()  # create to resolve `base` in grid_conf.conf
        cache_type = self.conf.get('cache', {}).get('type', 'file')
        return getattr(self, '_%s_cache' % cache_type)(grid_conf, image_opts)

    def _tile_filter(self):
        filters = []
        if 'watermark' in self.conf:
            from mapproxy.tilefilter import create_watermark_filter
            if self.conf['watermark'].get('color'):
                self.conf['watermark']['color'] = parse_color(self.conf['watermark']['color'])
            f = create_watermark_filter(self.conf, self.context)
            if f:
                filters.append(f)
        return filters

    @memoize
    def image_opts(self):
        from mapproxy.image.opts import ImageFormat

        format = None
        if 'format' not in self.conf.get('image', {}):
            format = self.conf.get('format') or self.conf.get('request_format')
        image_opts = self.context.globals.image_options.image_opts(self.conf.get('image', {}), format)
        if image_opts.format is None:
            if format is not None and format.startswith('image/'):
                image_opts.format = ImageFormat(format)
            else:
                image_opts.format = ImageFormat('image/png')
        return image_opts

    def supports_tiled_only_access(self, params=None, tile_grid=None):
        caches = self.caches()
        if len(caches) > 1:
            return False

        cache_grid, extent, tile_manager = caches[0]
        image_opts = self.image_opts()

        if (tile_grid.is_subset_of(cache_grid)
                and params.get('format') == image_opts.format):
            return True

        return False

    def source(self, params=None, tile_grid=None, tiled_only=False):
        from mapproxy.source.tile import CacheSource
        from mapproxy.extent import map_extent_from_grid

        caches = self.caches()
        if len(caches) > 1:
            # cache with multiple grids/sources
            source = self.map_layer()
            source.supports_meta_tiles = True
            return source

        cache_grid, extent, tile_manager = caches[0]
        image_opts = self.image_opts()

        cache_extent = map_extent_from_grid(tile_grid)
        cache_extent = extent.intersection(cache_extent)

        source = CacheSource(tile_manager, extent=cache_extent,
                             image_opts=image_opts, tiled_only=tiled_only)
        return source

    def _sources_for_grid(self, source_names, grid_conf, request_format):
        sources = []
        source_image_opts = []

        # a cache can directly access source tiles when _all_ sources are caches too
        # and when they have compatible grids by using tiled_only on the CacheSource
        # check if all sources support tiled_only
        tiled_only = True
        for source_name in source_names:
            if source_name in self.context.sources:
                tiled_only = False
                break
            elif source_name in self.context.caches:
                cache_conf = self.context.caches[source_name]
                tiled_only = cache_conf.supports_tiled_only_access(
                    params={'format': request_format},
                    tile_grid=grid_conf.tile_grid(),
                )
                if not tiled_only:
                    break

        for source_name in source_names:
            if source_name in self.context.sources:
                source_conf = self.context.sources[source_name]
                source = source_conf.source({'format': request_format})
            elif source_name in self.context.caches:
                cache_conf = self.context.caches[source_name]
                source = cache_conf.source(
                    params={'format': request_format},
                    tile_grid=grid_conf.tile_grid(),
                    tiled_only=tiled_only,
                )
            else:
                raise ConfigurationError('unknown source %s' % source_name)
            if source:
                sources.append(source)
                source_image_opts.append(source.image_opts)

        return sources, source_image_opts

    def _sources_for_band_merge(self, sources_conf, grid_conf, request_format):
        from mapproxy.image.merge import BandMerger

        source_names = []

        for band, band_sources in sources_conf.items():
            for source in band_sources:
                name = source['source']
                if name in source_names:
                    idx = source_names.index(name)
                else:
                    source_names.append(name)
                    idx = len(source_names) - 1

                source["src_idx"] = idx

        sources, source_image_opts = self._sources_for_grid(
            source_names=source_names,
            grid_conf=grid_conf,
            request_format=request_format,
        )

        if 'l' in sources_conf:
            mode = 'L'
        elif 'a' in sources_conf:
            mode = 'RGBA'
        else:
            mode = 'RGB'

        band_merger = BandMerger(mode=mode)
        available_bands = {'r': 0, 'g': 1, 'b': 2, 'a': 3, 'l': 0}
        for band, band_sources in sources_conf.items():
            band_idx = available_bands.get(band)
            if band_idx is None:
                raise ConfigurationError("unsupported band '%s' for cache %s"
                                         % (band, self.conf['name']))
            for source in band_sources:
                band_merger.add_ops(
                    dst_band=band_idx,
                    src_img=source['src_idx'],
                    src_band=source['band'],
                    factor=source.get('factor', 1.0),
                )

        return band_merger, sources, source_image_opts

    @memoize
    def caches(self):
        from mapproxy.cache.dummy import DummyCache, DummyLocker
        from mapproxy.cache.tile import TileManager
        from mapproxy.cache.base import TileLocker
        from mapproxy.image.opts import compatible_image_options
        from mapproxy.extent import merge_layer_extents, map_extent_from_grid

        base_image_opts = self.image_opts()
        if (self.conf.get('format') == 'mixed' and
                self.conf.get('request_format') not in ['image/png', 'image/vnd.jpeg-png']):
            raise ConfigurationError(
                'request_format must be set to image/png or image/vnd.jpeg-png if mixed mode is enabled')
        request_format = self.conf.get('request_format') or self.conf.get('format')
        if '/' in request_format:
            request_format_ext = request_format.split('/', 1)[1]
        else:
            request_format_ext = request_format

        caches = []

        meta_buffer = self.context.globals.get_value('meta_buffer', self.conf,
                                                     global_key='cache.meta_buffer')
        meta_size = self.context.globals.get_value('meta_size', self.conf,
                                                   global_key='cache.meta_size')
        bulk_meta_tiles = self.context.globals.get_value('bulk_meta_tiles', self.conf,
                                                         global_key='cache.bulk_meta_tiles')
        minimize_meta_requests = self.context.globals.get_value('minimize_meta_requests', self.conf,
                                                                global_key='cache.minimize_meta_requests')
        concurrent_tile_creators = self.context.globals.get_value('concurrent_tile_creators', self.conf,
                                                                  global_key='cache.concurrent_tile_creators')

        cache_rescaled_tiles = self.conf.get('cache_rescaled_tiles')
        upscale_tiles = self.conf.get('upscale_tiles', 0)
        if upscale_tiles < 0:
            raise ConfigurationError("upscale_tiles must be positive")
        downscale_tiles = self.conf.get('downscale_tiles', 0)
        if downscale_tiles < 0:
            raise ConfigurationError("downscale_tiles must be positive")
        if upscale_tiles and downscale_tiles:
            raise ConfigurationError("cannot use both upscale_tiles and downscale_tiles")

        rescale_tiles = 0
        if upscale_tiles:
            rescale_tiles = -upscale_tiles
        if downscale_tiles:
            rescale_tiles = downscale_tiles

        renderd_address = self.context.globals.get_value('renderd.address', self.conf)

        band_merger = None
        for grid_name, grid_conf in self.grid_confs():
            if isinstance(self.conf['sources'], dict):
                band_merger, sources, source_image_opts = self._sources_for_band_merge(
                    self.conf['sources'],
                    grid_conf=grid_conf,
                    request_format=request_format,
                )
            else:
                sources, source_image_opts = self._sources_for_grid(
                    self.conf['sources'],
                    grid_conf=grid_conf,
                    request_format=request_format,
                )

            if not sources:
                from mapproxy.source import DummySource
                sources = [DummySource()]
                source_image_opts.append(sources[0].image_opts)
            tile_grid = grid_conf.tile_grid()
            tile_filter = self._tile_filter()
            image_opts = compatible_image_options(source_image_opts, base_opts=base_image_opts)
            cache = self._tile_cache(grid_conf, image_opts)
            identifier = self.conf['name'] + '_' + tile_grid.name

            tile_creator_class = None

            use_renderd = bool(renderd_address)
            if self.context.renderd:
                # we _are_ renderd
                use_renderd = False
            if self.conf.get('disable_storage', False):
                # can't ask renderd to create tiles that shouldn't be cached
                use_renderd = False

            if use_renderd:
                from mapproxy.cache.renderd import RenderdTileCreator, has_renderd_support
                if not has_renderd_support():
                    raise ConfigurationError("renderd requires requests library")
                if self.context.seed:
                    priority = 10
                else:
                    priority = 100

                cache_dir = self.cache_dir()

                lock_dir = self.context.globals.get_value('cache.tile_lock_dir')
                if not lock_dir:
                    lock_dir = os.path.join(cache_dir, 'tile_locks')

                global_directory_permissions = self.context.globals.get_value('directory_permissions', self.conf,
                                                                         global_key='cache.directory_permissions')
                if global_directory_permissions:
                    log.info(f'Using global directory permission configuration for tile locks:'
                             f' {global_directory_permissions}')

                global_file_permissions = self.context.globals.get_value('file_permissions', self.conf,
                                                                         global_key='cache.file_permissions')
                if global_file_permissions:
                    log.info(f'Using global file permission configuration for tile locks:'
                             f' {global_file_permissions}')

                lock_timeout = self.context.globals.get_value('http.client_timeout', {})
                locker = TileLocker(lock_dir, lock_timeout, identifier + '_renderd',
                                    directory_permissions=global_directory_permissions,
                                    file_permissions=global_file_permissions)
                # TODO band_merger
                tile_creator_class = partial(RenderdTileCreator, renderd_address,
                                             priority=priority, tile_locker=locker)

            else:
                from mapproxy.cache.tile import TileCreator
                tile_creator_class = partial(TileCreator, image_merger=band_merger)

            if isinstance(cache, DummyCache):
                locker = DummyLocker()
            else:
                global_directory_permissions = self.context.globals.get_value('directory_permissions', self.conf,
                                                                              global_key='cache.directory_permissions')
                if global_directory_permissions:
                    log.info(f'Using global directory permission configuration for tile locks:'
                             f' {global_directory_permissions}')

                global_file_permissions = self.context.globals.get_value('file_permissions', self.conf,
                                                                         global_key='cache.file_permissions')
                if global_file_permissions:
                    log.info(f'Using global file permission configuration for tile locks:'
                             f' {global_file_permissions}')

                locker = TileLocker(
                    lock_dir=self.lock_dir(),
                    lock_timeout=self.context.globals.get_value('http.client_timeout', {}),
                    lock_cache_id=cache.lock_cache_id,
                    directory_permissions=global_directory_permissions,
                    file_permissions=global_file_permissions
                )

            mgr = TileManager(tile_grid, cache, sources, image_opts.format.ext,
                              locker=locker,
                              image_opts=image_opts, identifier=identifier,
                              request_format=request_format_ext,
                              meta_size=meta_size, meta_buffer=meta_buffer,
                              minimize_meta_requests=minimize_meta_requests,
                              concurrent_tile_creators=concurrent_tile_creators,
                              pre_store_filter=tile_filter,
                              tile_creator_class=tile_creator_class,
                              bulk_meta_tiles=bulk_meta_tiles,
                              cache_rescaled_tiles=cache_rescaled_tiles,
                              rescale_tiles=rescale_tiles,
                              )
            if self.conf['name'] in self.context.caches:
                mgr._refresh_before = self.context.caches[self.conf['name']].conf.get('refresh_before', {})
            extent = merge_layer_extents(sources)
            # If the cache has a defined coverage prefer it's extent over source extent
            if cache.coverage:
                extent = cache.coverage.extent
            elif extent.is_default:
                extent = map_extent_from_grid(tile_grid)
            caches.append((tile_grid, extent, mgr))
        return caches

    @memoize
    def grid_confs(self):
        grid_names = self.conf.get('grids')
        if grid_names is None:
            log.warning(
                'cache %s does not have any grids. default will change from [GLOBAL_MERCATOR] to [GLOBAL_WEBMERCATOR]'
                ' with MapProxy 2.0', self.conf['name'])
            grid_names = ['GLOBAL_MERCATOR']
        return [(g, self.context.grids[g]) for g in grid_names]

    @memoize
    def map_layer(self):
        from mapproxy.layer import CacheMapLayer, SRSConditional, ResolutionConditional

        image_opts = self.image_opts()
        max_tile_limit = self.context.globals.get_value('max_tile_limit', self.conf,
                                                        global_key='cache.max_tile_limit')
        caches = []
        main_grid = None
        for grid, extent, tile_manager in self.caches():
            if main_grid is None:
                main_grid = grid
            caches.append((CacheMapLayer(tile_manager, extent=extent, image_opts=image_opts,
                                         max_tile_limit=max_tile_limit),
                          grid.srs))

        if len(caches) == 1:
            layer = caches[0][0]
        else:
            layer = SRSConditional(caches, caches[0][0].extent, opacity=image_opts.opacity,
                                   preferred_srs=self.context.globals.preferred_srs)

        if 'use_direct_from_level' in self.conf:
            self.conf['use_direct_from_res'] = main_grid.resolution(self.conf['use_direct_from_level'])
        if 'use_direct_from_res' in self.conf:
            if len(self.conf['sources']) != 1:
                raise ValueError('use_direct_from_level/res only supports single sources')
            source_conf = self.context.sources[self.conf['sources'][0]]
            layer = ResolutionConditional(layer, source_conf.source(), self.conf['use_direct_from_res'],
                                          main_grid.srs, layer.extent, opacity=image_opts.opacity)
        return layer


def cache_source_names(context, cache):
    """
    Return all sources for a cache, even if a caches uses another cache.
    """
    source_names = []
    for src in context.caches[cache].conf['sources']:
        if src in context.caches and src not in context.sources:
            source_names.extend(cache_source_names(context, src))
        else:
            source_names.append(src)

    return source_names
