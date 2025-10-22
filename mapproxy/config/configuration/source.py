from __future__ import division

import hashlib
import os
import warnings

from copy import copy, deepcopy
from urllib.parse import urlparse

from mapproxy.config.configuration.base import ConfigurationBase

from mapproxy.config.configuration.base import ConfigurationError, parse_color
from mapproxy.config.spec import add_source_to_mapproxy_yaml_spec
from mapproxy.util.fs import find_exec
from mapproxy.util.py import memoize

import logging

log = logging.getLogger('mapproxy.config')


class SourcesCollection(dict):
    """
    Collection of SourceConfigurations.
    Allows access to tagged WMS sources, e.g.
    ``sc['source_name:lyr,lyr2']`` will return the source with ``source_name``
    and set ``req.layers`` to ``lyr1,lyr2``.
    """

    def __getitem__(self, key):
        layers = None
        source_name = key
        if ':' in source_name:
            source_name, layers = source_name.split(':', 1)
        source = dict.__getitem__(self, source_name)
        if not layers:
            return source

        if source.conf.get('type') not in ('wms', 'mapserver', 'mapnik'):
            raise ConfigurationError("found ':' in: '%s'."
                                     " tagged sources only supported for WMS/Mapserver/Mapnik" % key)

        uses_req = source.conf.get('type') != 'mapnik'

        source = copy(source)
        source.conf = deepcopy(source.conf)

        if uses_req:
            supported_layers = source.conf['req'].get('layers', [])
        else:
            supported_layers = source.conf.get('layers', [])
        supported_layer_set = SourcesCollection.layer_set(supported_layers)
        layer_set = SourcesCollection.layer_set(layers)

        if supported_layer_set and not layer_set.issubset(supported_layer_set):
            raise ConfigurationError('layers (%s) not supported by source (%s)' % (
                layers, ','.join(supported_layer_set)))

        if uses_req:
            source.conf['req']['layers'] = layers
        else:
            source.conf['layers'] = layers

        return source

    def __contains__(self, key):
        source_name = key
        if ':' in source_name:
            source_name, _ = source_name.split(':', 1)
        return dict.__contains__(self, source_name)

    @staticmethod
    def layer_set(layers):
        if isinstance(layers, (list, tuple)):
            return set(layers)
        return set(layers.split(','))


class SourceConfiguration(ConfigurationBase):

    supports_meta_tiles = True

    @classmethod
    def load(cls, conf, context):
        source_type = conf['type']

        subclass = source_configuration_types.get(source_type)
        if not subclass:
            raise ConfigurationError("unknown source type '%s'" % source_type)

        return subclass(conf, context)

    @memoize
    def coverage(self):
        if 'coverage' not in self.conf:
            return None
        from mapproxy.config.coverage import load_coverage
        return load_coverage(self.conf['coverage'])

    def image_opts(self, format=None):
        if 'transparent' in self.conf:
            self.conf.setdefault('image', {})['transparent'] = self.conf['transparent']
        return self.context.globals.image_options.image_opts(self.conf.get('image', {}), format)

    def supported_srs(self):
        from mapproxy.srs import SRS, SupportedSRS

        supported_srs = [SRS(code) for code in self.conf.get('supported_srs', [])]
        if not supported_srs:
            return None
        return SupportedSRS(supported_srs, self.context.globals.preferred_srs)

    def http_client(self, url):
        from mapproxy.client.http import auth_data_from_url, HTTPClient

        http_client = None
        url, (username, password) = auth_data_from_url(url)
        insecure = ssl_ca_certs = None
        if 'https' in url:
            insecure = self.context.globals.get_value('http.ssl_no_cert_checks', self.conf)
            ssl_ca_certs = self.context.globals.get_path('http.ssl_ca_certs', self.conf)

        timeout = self.context.globals.get_value('http.client_timeout', self.conf)
        headers = self.context.globals.get_value('http.headers', self.conf)
        hide_error_details = self.context.globals.get_value('http.hide_error_details', self.conf)
        manage_cookies = self.context.globals.get_value('http.manage_cookies', self.conf)

        http_client = HTTPClient(url, username, password, insecure=insecure,
                                 ssl_ca_certs=ssl_ca_certs, timeout=timeout,
                                 headers=headers, hide_error_details=hide_error_details,
                                 manage_cookies=manage_cookies)
        return http_client, url

    @memoize
    def on_error_handler(self):
        if 'on_error' not in self.conf:
            return None
        from mapproxy.source.error import HTTPSourceErrorHandler

        error_handler = HTTPSourceErrorHandler()
        for status_code, response_conf in self.conf['on_error'].items():
            if not isinstance(status_code, int) and status_code != 'other':
                raise ConfigurationError("invalid error code %r in on_error", status_code)
            cacheable = response_conf.get('cache', False)
            color = response_conf.get('response', 'transparent')
            authorize_stale = response_conf.get('authorize_stale', False)
            if color == 'transparent':
                color = (255, 255, 255, 0)
            else:
                color = parse_color(color)
            error_handler.add_handler(status_code, color, cacheable, authorize_stale)

        return error_handler


def resolution_range(conf):
    from mapproxy.grid.resolutions import resolution_range as _resolution_range
    if 'min_res' in conf or 'max_res' in conf:
        return _resolution_range(min_res=conf.get('min_res'),
                                 max_res=conf.get('max_res'))
    if 'min_scale' in conf or 'max_scale' in conf:
        return _resolution_range(min_scale=conf.get('min_scale'),
                                 max_scale=conf.get('max_scale'))


class ArcGISSourceConfiguration(SourceConfiguration):
    source_type = ('arcgis',)

    def __init__(self, conf, context):
        SourceConfiguration.__init__(self, conf, context)

    def source(self, params=None):
        from mapproxy.client.arcgis import ArcGISClient
        from mapproxy.source.arcgis import ArcGISSource
        from mapproxy.request.arcgis import create_request

        if not self.conf.get('opts', {}).get('map', True):
            return None

        if not self.context.seed and self.conf.get('seed_only'):
            from mapproxy.source import DummySource
            return DummySource(coverage=self.coverage())

        supported_formats = [file_ext(f) for f in self.conf.get("supported_formats", [])]

        # Construct the parameters
        if params is None:
            params = {}

        request_format = self.conf['req'].get('format')
        if request_format:
            params['format'] = request_format

        request = create_request(self.conf["req"], params)
        http_client, request.url = self.http_client(request.url)
        coverage = self.coverage()
        res_range = resolution_range(self.conf)

        client = ArcGISClient(request, http_client)
        image_opts = self.image_opts(format=params.get('format'))
        return ArcGISSource(client, image_opts=image_opts, coverage=coverage,
                            res_range=res_range,
                            supported_srs=self.supported_srs(),
                            supported_formats=supported_formats or None,
                            error_handler=self.on_error_handler())

    @memoize
    def fi_source(self, params=None):
        from mapproxy.client.arcgis import ArcGISInfoClient
        from mapproxy.request.arcgis import create_identify_request
        from mapproxy.source.arcgis import ArcGISInfoSource

        if params is None:
            params = {}
        request_format = self.conf['req'].get('format')
        if request_format:
            params['format'] = request_format
        fi_source = None
        if self.conf.get('opts', {}).get('featureinfo', False):
            opts = self.conf['opts']
            tolerance = opts.get('featureinfo_tolerance', 5)
            return_geometries = opts.get('featureinfo_return_geometries', False)

            fi_request = create_identify_request(self.conf['req'], params)

            http_client, fi_request.url = self.http_client(fi_request.url)
            fi_client = ArcGISInfoClient(fi_request,
                                         supported_srs=self.supported_srs(),
                                         http_client=http_client,
                                         tolerance=tolerance,
                                         return_geometries=return_geometries,
                                         )
            fi_source = ArcGISInfoSource(fi_client)
        return fi_source


class WMSSourceConfiguration(SourceConfiguration):
    source_type = ('wms',)

    @staticmethod
    def static_legend_source(url, context):
        from mapproxy.cache.legend import LegendCache
        from mapproxy.client.wms import WMSLegendURLClient
        from mapproxy.source.wms import WMSLegendSource

        cache_dir = os.path.join(context.globals.get_path('cache.base_dir', {}),
                                 'legends')
        if url.startswith('file://') and not url.startswith('file:///'):
            prefix = 'file://'
            url = prefix + context.globals.abspath(url[7:])
        lg_client = WMSLegendURLClient(url)

        global_directory_permissions = context.globals.get_value('directory_permissions', None,
                                                     global_key='cache.directory_permissions')
        if global_directory_permissions:
            log.info(f'Using global directory permission configuration for static legend cache:'
                     f' {global_directory_permissions}')

        global_file_permissions = context.globals.get_value(
            'file_permissions', None, global_key='cache.file_permissions')
        if global_file_permissions:
            log.info(f'Using global file permission configuration for static legend cache: {global_file_permissions}')

        legend_cache = LegendCache(cache_dir=cache_dir, directory_permissions=global_directory_permissions,
                                   file_permissions=global_file_permissions)
        return WMSLegendSource([lg_client], legend_cache, static=True)

    def fi_xslt_transformer(self, conf, context):
        from mapproxy.featureinfo import XSLTransformer
        fi_transformer = None
        fi_xslt = conf.get('featureinfo_xslt')
        if fi_xslt:
            fi_xslt = context.globals.abspath(fi_xslt)
            fi_format = conf.get('featureinfo_out_format')
            if not fi_format:
                fi_format = conf.get('featureinfo_format')
            fi_transformer = XSLTransformer(fi_xslt, fi_format)
        return fi_transformer

    def image_opts(self, format=None):
        if 'transparent' not in (self.conf.get('image') or {}):
            transparent = self.conf['req'].get('transparent')
            if transparent is not None:
                transparent = bool(str(transparent).lower() == 'true')
                self.conf.setdefault('image', {})['transparent'] = transparent
        return SourceConfiguration.image_opts(self, format=format)

    def source(self, params=None):
        from mapproxy.client.wms import WMSClient
        from mapproxy.request.wms import create_request
        from mapproxy.source.wms import WMSSource

        if not self.conf.get('wms_opts', {}).get('map', True):
            return None

        if not self.context.seed and self.conf.get('seed_only'):
            from mapproxy.source import DummySource
            return DummySource(coverage=self.coverage())

        if params is None:
            params = {}

        request_format = self.conf['req'].get('format')
        if request_format:
            params['format'] = request_format

        image_opts = self.image_opts(format=params.get('format'))

        supported_formats = [file_ext(f) for f in self.conf.get('supported_formats', [])]
        version = self.conf.get('wms_opts', {}).get('version', '1.1.1')

        lock = None
        concurrent_requests = self.context.globals.get_value('concurrent_requests', self.conf,
                                                             global_key='http.concurrent_requests')
        if concurrent_requests:
            from mapproxy.util.lock import SemLock
            lock_dir = self.context.globals.get_path('cache.lock_dir', self.conf)
            lock_timeout = self.context.globals.get_value('http.client_timeout', self.conf)
            url = urlparse(self.conf['req']['url'])

            global_directory_permissions = self.context.globals.get_value('directory_permissions', self.conf,
                                                                          global_key='cache.directory_permissions')
            if global_directory_permissions:
                log.info(f'Using global directory permission configuration for concurrent file locks:'
                         f' {global_directory_permissions}')

            global_file_permissions = self.context.globals.get_value('file_permissions', self.conf,
                                                                     global_key='cache.file_permissions')
            if global_file_permissions:
                log.info(f'Using global file permission configuration for concurrent file locks:'
                         f' {global_file_permissions}')

            md5 = hashlib.new('md5', url.netloc.encode('ascii'), usedforsecurity=False)
            lock_file = os.path.join(lock_dir, md5.hexdigest() + '.lck')
            lock = lambda: SemLock(lock_file, concurrent_requests, timeout=lock_timeout,  # noqa
                                   directory_permissions=global_directory_permissions,
                                   file_permissions=global_file_permissions)

        coverage = self.coverage()
        res_range = resolution_range(self.conf)

        transparent_color = (self.conf.get('image') or {}).get('transparent_color')
        transparent_color_tolerance = self.context.globals.get_value(
            'image.transparent_color_tolerance', self.conf)
        if transparent_color:
            transparent_color = parse_color(transparent_color)

        http_method = self.context.globals.get_value('http.method', self.conf)

        fwd_req_params = set(self.conf.get('forward_req_params', []))

        request = create_request(self.conf['req'], params, version=version,
                                 abspath=self.context.globals.abspath)
        http_client, request.url = self.http_client(request.url)
        client = WMSClient(request, http_client=http_client,
                           http_method=http_method, lock=lock,
                           fwd_req_params=fwd_req_params)
        return WMSSource(client, image_opts=image_opts, coverage=coverage,
                         res_range=res_range, transparent_color=transparent_color,
                         transparent_color_tolerance=transparent_color_tolerance,
                         supported_srs=self.supported_srs(),
                         supported_formats=supported_formats or None,
                         fwd_req_params=fwd_req_params,
                         error_handler=self.on_error_handler())

    def fi_source(self, params=None):
        from mapproxy.client.wms import WMSInfoClient
        from mapproxy.request.wms import create_request
        from mapproxy.source.wms import WMSInfoSource

        if params is None:
            params = {}
        request_format = self.conf['req'].get('format')
        if request_format:
            params['format'] = request_format
        fi_source = None
        if self.conf.get('wms_opts', {}).get('featureinfo', False):
            wms_opts = self.conf['wms_opts']
            version = wms_opts.get('version', '1.1.1')
            if 'featureinfo_format' in wms_opts:
                params['info_format'] = wms_opts['featureinfo_format']
            if 'query_layers' in wms_opts:
                params['query_layers'] = wms_opts['query_layers']
            fi_request = create_request(self.conf['req'], params,
                                        req_type='featureinfo', version=version,
                                        abspath=self.context.globals.abspath)

            fi_transformer = self.fi_xslt_transformer(self.conf.get('wms_opts', {}),
                                                      self.context)

            http_client, fi_request.url = self.http_client(fi_request.url)
            fi_client = WMSInfoClient(fi_request, supported_srs=self.supported_srs(),
                                      http_client=http_client)
            coverage = self.coverage()
            fi_source = WMSInfoSource(fi_client, fi_transformer=fi_transformer,
                                      coverage=coverage)
        return fi_source

    def lg_source(self, params=None):
        from mapproxy.cache.legend import LegendCache
        from mapproxy.client.wms import WMSLegendClient
        from mapproxy.request.wms import create_request
        from mapproxy.source.wms import WMSLegendSource

        if params is None:
            params = {}
        request_format = self.conf['req'].get('format')
        if request_format:
            params['format'] = request_format
        lg_source = None
        cache_dir = os.path.join(self.context.globals.get_path('cache.base_dir', {}),
                                 'legends')

        if self.conf.get('wms_opts', {}).get('legendurl', False):
            lg_url = self.conf.get('wms_opts', {}).get('legendurl')
            lg_source = WMSSourceConfiguration.static_legend_source(lg_url, self.context)
        elif self.conf.get('wms_opts', {}).get('legendgraphic', False):
            version = self.conf.get('wms_opts', {}).get('version', '1.1.1')
            lg_req = self.conf['req'].copy()
            lg_clients = []
            lg_layers = str(lg_req['layers']).split(',')
            del lg_req['layers']
            for lg_layer in lg_layers:
                lg_req['layer'] = lg_layer
                lg_request = create_request(lg_req, params,
                                            req_type='legendgraphic', version=version,
                                            abspath=self.context.globals.abspath)
                http_client, lg_request.url = self.http_client(lg_request.url)
                lg_client = WMSLegendClient(lg_request, http_client=http_client)
                lg_clients.append(lg_client)

            global_directory_permissions = self.context.globals.get_value('directory_permissions', self.conf,
                                                                   global_key='cache.directory_permissions')
            if global_directory_permissions:
                log.info(f'Using global directory permission configuration for legend cache:'
                         f' {global_directory_permissions}')

            global_file_permissions = self.context.globals.get_value('file_permissions', self.conf,
                                                              global_key='cache.file_permissions')
            if global_file_permissions:
                log.info(f'Using global file permission configuration for legend cache:'
                         f' {global_file_permissions}')

            legend_cache = LegendCache(cache_dir=cache_dir, directory_permissions=global_directory_permissions,
                                       file_permissions=global_file_permissions)
            lg_source = WMSLegendSource(lg_clients, legend_cache)
        return lg_source


class MapServerSourceConfiguration(WMSSourceConfiguration):
    source_type = ('mapserver',)

    def __init__(self, conf, context):
        WMSSourceConfiguration.__init__(self, conf, context)
        self.script = self.context.globals.get_path('mapserver.binary',
                                                    self.conf)
        if not self.script:
            self.script = find_exec('mapserv')

        if not self.script or not os.path.isfile(self.script):
            raise ConfigurationError('could not find mapserver binary (%r)' %
                                     (self.script, ))

        # set url to dummy script name, required as identifier
        # for concurrent_request
        self.conf['req']['url'] = 'mapserver://' + self.script

        mapfile = self.context.globals.abspath(self.conf['req']['map'])
        self.conf['req']['map'] = mapfile

    def http_client(self, url):
        working_dir = self.context.globals.get_path('mapserver.working_dir', self.conf)
        if working_dir and not os.path.isdir(working_dir):
            raise ConfigurationError('could not find mapserver working_dir (%r)' % (working_dir, ))

        from mapproxy.client.cgi import CGIClient
        client = CGIClient(script=self.script, working_directory=working_dir)
        return client, url


class MapnikSourceConfiguration(SourceConfiguration):
    source_type = ('mapnik',)

    def source(self, params=None):
        if not self.context.seed and self.conf.get('seed_only'):
            from mapproxy.source import DummySource
            return DummySource(coverage=self.coverage())

        image_opts = self.image_opts()

        lock = None
        concurrent_requests = self.context.globals.get_value('concurrent_requests', self.conf,
                                                             global_key='http.concurrent_requests')
        if concurrent_requests:
            from mapproxy.util.lock import SemLock
            lock_dir = self.context.globals.get_path('cache.lock_dir', self.conf)
            mapfile = self.conf['mapfile']

            global_directory_permissions = self.context.globals.get_value('directory_permissions', self.conf,
                                                                          global_key='cache.directory_permissions')
            if global_directory_permissions:
                log.info(f'Using global directory permission configuration for concurrent file locks:'
                         f' {global_directory_permissions}')

            global_file_permissions = self.context.globals.get_value('file_permissions', self.conf,
                                                                     global_key='cache.file_permissions')
            if global_file_permissions:
                log.info(f'Using global file permission configuration for concurrent file locks:'
                         f' {global_file_permissions}')

            md5 = hashlib.new('md5', mapfile.encode('utf-8'), usedforsecurity=False)
            lock_file = os.path.join(lock_dir, md5.hexdigest() + '.lck')
            lock = lambda: SemLock(lock_file, concurrent_requests, # noqa
                                   directory_permissions=global_directory_permissions,
                                   file_permissions=global_file_permissions)

        coverage = self.coverage()
        res_range = resolution_range(self.conf)

        scale_factor = self.conf.get('scale_factor', None)
        multithreaded = self.conf.get('multithreaded', False)

        layers = self.conf.get('layers', None)
        if isinstance(layers, str):
            layers = layers.split(',')

        mapfile = self.context.globals.abspath(self.conf['mapfile'])

        if self.conf.get('use_mapnik2', False):
            warnings.warn('use_mapnik2 option is no longer needed for Mapnik 2 support',
                          DeprecationWarning)

        from mapproxy.source.mapnik import MapnikSource, mapnik as mapnik_api
        if mapnik_api is None:
            raise ConfigurationError('Could not import Mapnik, please verify it is installed!')

        if self.context.renderd:
            # only renderd guarantees that we have a single proc/thread
            # that accesses the same mapnik map object
            reuse_map_objects = True
        else:
            reuse_map_objects = False

        return MapnikSource(mapfile, layers=layers, image_opts=image_opts,
                            coverage=coverage, res_range=res_range, lock=lock,
                            reuse_map_objects=reuse_map_objects, scale_factor=scale_factor,
                            multithreaded=multithreaded)


class TileSourceConfiguration(SourceConfiguration):
    supports_meta_tiles = False
    source_type = ('tile',)
    defaults = {}

    def source(self, params=None):
        from mapproxy.client.tile import TileClient, TileURLTemplate
        from mapproxy.source.tile import TiledSource

        if not self.context.seed and self.conf.get('seed_only'):
            from mapproxy.source import DummySource
            return DummySource(coverage=self.coverage())

        if params is None:
            params = {}

        url = self.conf['url']

        if self.conf.get('origin'):
            warnings.warn('origin for tile sources is deprecated since 1.3.0 '
                          'and will be ignored. use grid with correct origin.', RuntimeWarning)

        http_client, url = self.http_client(url)

        grid_name = self.conf.get('grid')
        if grid_name is None:
            log.warning(
                "tile source for %s does not have a grid configured and defaults to GLOBAL_MERCATOR. default will"
                " change with MapProxy 2.0", url)
            grid_name = "GLOBAL_MERCATOR"

        grid = self.context.grids[grid_name].tile_grid()
        coverage = self.coverage()
        res_range = resolution_range(self.conf)

        image_opts = self.image_opts()
        error_handler = self.on_error_handler()

        format = file_ext(params['format'])
        client = TileClient(TileURLTemplate(url, format=format), http_client=http_client, grid=grid)
        return TiledSource(grid, client, coverage=coverage, image_opts=image_opts,
                           error_handler=error_handler, res_range=res_range)


class OGCAPITilesSourceConfiguration(SourceConfiguration):
    supports_meta_tiles = False
    source_type = ('ogcapitiles',)
    defaults = {}

    def source(self, params=None):
        from mapproxy.source.ogcapitiles import OGCAPITilesSource

        landingpage_url = self.conf['landingpage_url']

        http_client, landingpage_url = self.http_client(landingpage_url)

        collection = self.conf.get('collection', None)

        tile_matrix_set_id = self.conf.get('tile_matrix_set_id', None)

        coverage = self.coverage()
        image_opts = self.image_opts()
        error_handler = self.on_error_handler()
        res_range = resolution_range(self.conf)

        return OGCAPITilesSource(landingpage_url,
                                 collection, http_client,
                                 tile_matrix_set_id=tile_matrix_set_id,
                                 coverage=coverage,
                                 image_opts=image_opts,
                                 error_handler=error_handler,
                                 res_range=res_range)


class OGCAPIMapsSourceConfiguration(SourceConfiguration):
    supports_meta_tiles = True
    source_type = ('ogcapimaps',)
    defaults = {}

    def source(self, params=None):
        from mapproxy.source.ogcapimaps import OGCAPIMapsSource

        landingpage_url = self.conf['landingpage_url']

        http_client, landingpage_url = self.http_client(landingpage_url)

        collection = self.conf.get('collection', None)

        transparent = self.conf.get('transparent', None)
        transparent_color = (self.conf.get('image') or {}).get('transparent_color')
        transparent_color_tolerance = self.context.globals.get_value(
            'image.transparent_color_tolerance', self.conf)
        if transparent_color:
            transparent_color = parse_color(transparent_color)
        bgcolor = self.conf.get('bgcolor', None)
        if bgcolor:
            bgcolor = parse_color(bgcolor)

        coverage = self.coverage()
        image_opts = self.image_opts()
        error_handler = self.on_error_handler()
        res_range = resolution_range(self.conf)

        return OGCAPIMapsSource(landingpage_url,
                                collection, http_client, coverage=coverage,
                                image_opts=image_opts,
                                error_handler=error_handler,
                                res_range=res_range,
                                supported_srs=self.supported_srs(),
                                transparent=transparent,
                                transparent_color=transparent_color,
                                transparent_color_tolerance=transparent_color_tolerance,
                                bgcolor=bgcolor)


def file_ext(mimetype):
    from mapproxy.request.base import split_mime_type
    _mime_class, format, _options = split_mime_type(mimetype)
    return format


class DebugSourceConfiguration(SourceConfiguration):
    source_type = ('debug',)
    required_keys = set('type'.split())

    def source(self, params=None):
        from mapproxy.source import DebugSource
        return DebugSource()


source_configuration_types = {
    'wms': WMSSourceConfiguration,
    'arcgis': ArcGISSourceConfiguration,
    'tile': TileSourceConfiguration,
    'debug': DebugSourceConfiguration,
    'mapserver': MapServerSourceConfiguration,
    'mapnik': MapnikSourceConfiguration,
    'ogcapitiles': OGCAPITilesSourceConfiguration,
    'ogcapimaps': OGCAPIMapsSourceConfiguration,
}


def register_source_configuration(config_name, config_class,
                                  yaml_spec_source_name=None, yaml_spec_source_def=None):
    """ Method used by plugins to register a new source configuration.

        :param config_name: Name of the source configuration
        :type config_name: str
        :param config_class: Class of the source configuration
        :type config_name: SourceConfiguration
        :param yaml_spec_source_name: Name of the source in the YAML configuration file
        :type yaml_spec_source_name: str
        :param yaml_spec_source_def: Definition of the source in the YAML configuration file
        :type yaml_spec_source_def: dict

        Example:
            register_source_configuration('hips', HIPSSourceConfiguration,
                                          'hips', { required('url'): str(),
                                                    'resampling_method': str(),
                                                    'image': image_opts,
                                                  })
    """
    log.info('Registering configuration for plugin source %s' % config_name)
    source_configuration_types[config_name] = config_class
    if yaml_spec_source_name is not None and yaml_spec_source_def is not None:
        add_source_to_mapproxy_yaml_spec(yaml_spec_source_name, yaml_spec_source_def)
