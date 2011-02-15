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

"""
Configuration loading and system initializing.
"""
from __future__ import with_statement, division

import os
import hashlib
import urlparse
import yaml #pylint: disable-msg=F0401
from copy import deepcopy

import logging
log = logging.getLogger(__name__)

from mapproxy.srs import SRS
from mapproxy.util.ext.odict import odict
from mapproxy.cache.file import FileCache, DummyCache
from mapproxy.util.lock import SemLock
from mapproxy.config.config import load_default_config
from mapproxy.client.http import auth_data_from_url, HTTPClient


def loader(loaders, name):
    """
    Return named class/function from loaders map.
    """
    entry_point = loaders[name]
    module_name, class_name = entry_point.split(':')
    module = __import__(module_name, {}, {}, class_name)
    return getattr(module, class_name)


tile_filter_loaders = {
    'watermark': 'mapproxy.tilefilter:WaterMarkTileFilter',
    'pngquant': 'mapproxy.tilefilter:PNGQuantTileFilter',
}

def load_tile_filters():
    filters = []
    for key in tile_filter_loaders:
        filters.append(loader(tile_filter_loaders, key))
    filters.sort(key=lambda x: x.priority, reverse=True)
    conf_keys = set()
    for f in filters:
        conf_keys.update(f.cache_conf_keys)
    return filters, conf_keys

tile_filters, tile_filter_conf_keys = load_tile_filters()
del load_tile_filters


import mapproxy.config
from mapproxy.grid import tile_grid, resolution_range as _resolution_range
from mapproxy.request.base import split_mime_type
from mapproxy.request.wms import create_request
from mapproxy.layer import (
    CacheMapLayer, SRSConditional,
    ResolutionConditional, map_extent_from_grid, merge_layer_extents
)
from mapproxy.client.tile import TileClient, TileURLTemplate
from mapproxy.client.wms import WMSClient, WMSInfoClient, WMSLegendClient, WMSLegendURLClient
from mapproxy.service.wms import WMSServer, WMSLayer, WMSGroupLayer
from mapproxy.service.tile import TileServer, TileLayer
from mapproxy.service.kml import KMLServer
from mapproxy.service.demo import DemoServer
from mapproxy.source import DebugSource, DummySource
from mapproxy.source.wms import WMSSource, WMSInfoSource, WMSLegendSource
from mapproxy.source.tile import TiledSource
from mapproxy.cache.tile import TileManager
from mapproxy.cache.legend import LegendCache
from mapproxy.util import local_base_config, memoize
from mapproxy.config.coverage import load_coverage
from mapproxy.featureinfo import XSLTransformer, has_xslt_support

class ConfigurationError(Exception):
    pass

class ProxyConfiguration(object):
    def __init__(self, conf, conf_base_dir=None, seed=False):
        self.configuration = conf
        self.seed = seed
        
        if conf_base_dir is None:
            conf_base_dir = os.getcwd()
        
        self.load_globals(conf_base_dir=conf_base_dir)
        self.load_grids()
        self.load_caches()
        self.load_sources()
        self.load_wms_root_layer()
        self.load_tile_layers()
        self.load_services()
    
    def load_globals(self, conf_base_dir):
        self.globals = GlobalConfiguration(conf_base_dir=conf_base_dir,
                                           conf=self.configuration.get('globals', {}),
                                           context=self)
    
    def load_grids(self):
        self.grids = {}
        
        self.grids['GLOBAL_GEODETIC'] = GridConfiguration(dict(srs='EPSG:4326'), context=self)
        self.grids['GLOBAL_MERCATOR'] = GridConfiguration(dict(srs='EPSG:900913'), context=self)
        
        for grid_name, grid_conf in self.configuration.get('grids', {}).iteritems():
            self.grids[grid_name] = GridConfiguration(grid_conf, context=self)
    
    def load_caches(self):
        self.caches = odict()
        caches_conf = self.configuration.get('caches')
        if not caches_conf: return None # TODO config error
        if isinstance(caches_conf, list):
            caches_conf = list_of_dicts_to_ordered_dict(caches_conf)
        for cache_name, cache_conf in caches_conf.iteritems():
            cache_conf['name'] = cache_name
            self.caches[cache_name] = CacheConfiguration(conf=cache_conf, context=self)
    
    def load_sources(self):
        self.sources = {}
        for source_name, source_conf in self.configuration.get('sources', {}).iteritems():
            self.sources[source_name] = SourceConfiguration.load(conf=source_conf, context=self)
    
    def load_tile_layers(self):
        self.layers = odict()
        layers_conf = deepcopy(self._layers_conf_dict())
        if layers_conf is None: return
        layers = self._flatten_layers_conf_dict(layers_conf)
        for layer_name, layer_conf in layers.iteritems():
            layer_conf['name'] = layer_name
            self.layers[layer_name] = LayerConfiguration(conf=layer_conf, context=self)
        
    def _legacy_layers_conf_dict(self):
        """
        Read old style layer configuration with a dictionary where
        the key is the layer name. Optionally: a list an each layer
        is wrapped in such dictionary.
        
        ::
          layers:
            foo:
              title: xxx
              sources: []
            bar:
              title: xxx
              sources: []
        
        or
        
        ::
        
          layers:
            - foo:
               title: xxx
               sources: []
            - bar:
               title: xxx
               sources: []
        
        """
        layers = []
        layers_conf = self.configuration.get('layers')
        if not layers_conf: return None # TODO config error
        if isinstance(layers_conf, list):
            layers_conf = list_of_dicts_to_ordered_dict(layers_conf)
        for layer_name, layer_conf in layers_conf.iteritems():
            layer_conf['name'] = layer_name
            layers.append(layer_conf)
        return dict(title=None, layers=layers)
        
        
    def _layers_conf_dict(self):
        """
        Returns (recursive) layer configuration as a dictionary
        in unified structure:
        
        ::
            {
             title: 'xxx', # required, might be None
             name: 'xxx', # optional
             # sources or layers or both are required
             sources: [],
             layers: [
                {..., ...} # more layers like this
             ]
            }
        
        Multiple layers will be wrapped in an unnamed root layer, if the
        first level starts with multiple layers.
        """
        layers_conf = self.configuration.get('layers')
        if layers_conf is None: return
        
        if isinstance(layers_conf, list):
            if isinstance(layers_conf[0], dict) and len(layers_conf[0].keys()) == 1:
                # looks like ordered legacy config
                layers_conf = self._legacy_layers_conf_dict()
            elif len(layers_conf) == 1 and 'layers' in layers_conf[0]:
                # single root layer in list -> remove list
                layers_conf = layers_conf[0]
            else:
                # layer list without root -> wrap in root layer
                layers_conf = dict(title=None, layers=layers_conf)
        
        if len(set(layers_conf.keys()) &
               set('layers name title sources'.split())) < 2:
            # looks like unordered legacy config
            layers_conf = self._legacy_layers_conf_dict()
        
        return layers_conf
    
    def _flatten_layers_conf_dict(self, layers_conf, _layers=None):
        """
        Returns a dictionary with all layers that have a name and sources.
        Flattens the layer tree.
        """
        layers = _layers if _layers is not None else odict()
        
        if 'layers' in layers_conf:
            for layer in layers_conf.pop('layers'):
                self._flatten_layers_conf_dict(layer, layers)
        
        if 'sources' in layers_conf and 'name' in layers_conf:
            layers[layers_conf['name']] = layers_conf
        
        return layers
        
    
    def load_wms_root_layer(self):
        self.wms_root_layer = None
        
        layers_conf = self._layers_conf_dict()
        if layers_conf is None: return
        self.wms_root_layer = WMSLayerConfiguration(layers_conf, context=self)
    
    def load_services(self):
        self.services = ServiceConfiguration(self.configuration.get('services', {}), context=self)
    
    def configured_services(self):
        with local_base_config(self.base_config):
            return self.services.services()
    
    @property
    def base_config(self):
        return self.globals.base_config

def list_of_dicts_to_ordered_dict(dictlist):
    """
    >>> d = list_of_dicts_to_ordered_dict([{'a': 1}, {'b': 2}, {'c': 3}])
    >>> d.items()
    [('a', 1), ('b', 2), ('c', 3)]
    """
    
    result = odict()
    for d in dictlist:
        for k, v in d.iteritems():
            result[k] = v
    return result

class ConfigurationBase(object):
    """
    Base class for all configurations.
    """
    optional_keys = set()
    required_keys = set()
    defaults = {}
    
    def __init__(self, conf, context):
        """
        :param conf: the configuration part for this configurator
        :param context: the complete proxy configuration
        :type context: ProxyConfiguration
        """
        self.conf = {}
        self.context = context
        expected_keys = set(self.optional_keys)
        expected_keys.update(self.required_keys)
        expected_keys.update(self.defaults.keys())
        for k, v in conf.iteritems():
            if k not in expected_keys:
                log.warn('unexpected key %s', k)
            self.conf[k] = v
        
        for k in self.required_keys:
            if k not in self.conf:
                raise ConfigurationError('missing key %s' % k)
        
        for k, v in self.defaults.iteritems():
            if k not in self.conf:
                self.conf[k] = v

class GridConfiguration(ConfigurationBase):
    optional_keys = set('''res srs bbox bbox_srs num_levels tile_size base
        stretch_factor max_shrink_factor align_resolutions_with min_res max_res
        res_factor threshold_res
        '''.split())
    
    @memoize
    def tile_grid(self):
        if 'base' in self.conf:
            base_grid_name = self.conf['base']
            conf = self.context.grids[base_grid_name].conf.copy()
            conf.update(self.conf)
            conf.pop('base')
            self.conf = conf
        else:
            conf = self.conf
        align_with = None
        if 'align_resolutions_with' in self.conf:
            align_with_grid_name = self.conf['align_resolutions_with']
            align_with = self.context.grids[align_with_grid_name].tile_grid()

        tile_size = self.context.globals.get_value('tile_size', conf,
            global_key='grid.tile_size')
        conf['tile_size'] = tuple(tile_size)
        tile_size = tuple(tile_size)
        
        stretch_factor = self.context.globals.get_value('stretch_factor', conf,
            global_key='image.stretch_factor')
        max_shrink_factor = self.context.globals.get_value('max_shrink_factor', conf,
            global_key='image.max_shrink_factor')
        
        
        grid = tile_grid(
            srs=conf.get('srs'),
            tile_size=tile_size,
            min_res=conf.get('min_res'),
            max_res=conf.get('max_res'),
            res=conf.get('res'),
            res_factor=conf.get('res_factor', 2.0),
            threshold_res=conf.get('threshold_res'),
            bbox=conf.get('bbox'),
            bbox_srs=conf.get('bbox_srs'),
            num_levels=conf.get('num_levels'),
            stretch_factor=stretch_factor,
            max_shrink_factor=max_shrink_factor,
            align_with = align_with,
        )
        
        return grid


class GlobalConfiguration(ConfigurationBase):
    optional_keys = set('image grid srs http cache'.split())
    
    def __init__(self, conf_base_dir, conf, context):
        ConfigurationBase.__init__(self, conf, context)
        self.base_config = load_default_config()
        self._copy_conf_values(self.conf, self.base_config)
        self.base_config.conf_base_dir = conf_base_dir
        mapproxy.config.finish_base_config(self.base_config)
    
    def _copy_conf_values(self, d, target):
        for k, v in d.iteritems():
            if v is None: continue
            if hasattr(v, 'iteritems'):
                self._copy_conf_values(v, target[k])
            else:
                target[k] = v
    
    def get_value(self, key, local, global_key=None, default_key=None):
        result = dotted_dict_get(key, local)
        if result is None:
            result = dotted_dict_get(global_key or key, self.conf)
        
        if result is None:
            result = dotted_dict_get(default_key or global_key or key, self.base_config)
            
        return result
    
    def get_path(self, key, local, global_key=None, default_key=None):
        value = self.get_value(key, local, global_key, default_key)
        if value is not None:
            value = self.abspath(value)
        return value
    
    def abspath(self, path):
        return os.path.join(self.base_config.conf_base_dir, path)
        
    

def dotted_dict_get(key, d):
    """
    >>> dotted_dict_get('foo', {'foo': {'bar': 1}})
    {'bar': 1}
    >>> dotted_dict_get('foo.bar', {'foo': {'bar': 1}})
    1
    >>> dotted_dict_get('bar', {'foo': {'bar': 1}})
    """
    parts = key.split('.')
    try:
        while parts and d:
            d = d[parts.pop(0)]
    except KeyError:
        return None
    if parts: # not completely resolved
        return None
    return d

class SourceConfiguration(ConfigurationBase):
    @classmethod
    def load(cls, conf, context):
        source_type = conf['type']
        for subclass in cls.__subclasses__():
            if source_type in subclass.source_type:
                return subclass(conf, context)
        
        raise ValueError("unknown source type '%s'" % source_type)
    
    @memoize
    def coverage(self):
        if not 'coverage' in self.conf: return None
        return load_coverage(self.conf['coverage'])
    
    def http_client(self, url):
        http_client = None
        url, (username, password) = auth_data_from_url(url)
        insecure = ssl_ca_certs = None
        if 'https' in url:
            insecure = self.context.globals.get_value('http.ssl_no_cert_checks', self.conf)
            ssl_ca_certs = self.context.globals.get_path('http.ssl_ca_certs', self.conf)
        
        timeout = self.context.globals.get_value('http.client_timeout', self.conf)
        headers = self.context.globals.get_value('http.headers', self.conf)
        
        http_client = HTTPClient(url, username, password, insecure=insecure,
                                 ssl_ca_certs=ssl_ca_certs, timeout=timeout,
                                 headers=headers)
        return http_client, url

def resolution_range(conf):
    if 'min_res' in conf or 'max_res' in conf:
        return _resolution_range(min_res=conf.get('min_res'),
                                max_res=conf.get('max_res'))
    if 'min_scale' in conf or 'max_scale' in conf:
        return _resolution_range(min_scale=conf.get('min_scale'),
                                max_scale=conf.get('max_scale'))


class WMSSourceConfiguration(SourceConfiguration):
    source_type = ('wms',)
    optional_keys = set('''type supported_srs supported_formats image
        wms_opts http concurrent_requests coverage seed_only
        min_res max_res min_scale max_scale'''.split())
    required_keys = set('req'.split())
    
    @staticmethod
    def static_legend_source(url, context):
        cache_dir = os.path.join(context.globals.get_path('cache.base_dir', {}),
                                 'legends')
        if url.startswith('file://') and not url.startswith('file:///'):
            prefix = 'file://'
            url = prefix + context.globals.abspath(url[7:])
        lg_client = WMSLegendURLClient(url)
        legend_cache = LegendCache(cache_dir=cache_dir)
        return WMSLegendSource([lg_client], legend_cache)
    
    def fi_xslt_transformer(self, conf, context):
        fi_transformer = None
        fi_xslt = conf.get('featureinfo_xslt')
        if fi_xslt:
            if not has_xslt_support:
                raise ValueError('featureinfo_xslt requires lxml. Please install.')
            fi_xslt = context.globals.abspath(fi_xslt)
            fi_transformer = XSLTransformer(fi_xslt)
        return fi_transformer
    
    def source(self, params=None):
        if not self.conf.get('wms_opts', {}).get('map', True):
            return None
        
        if not self.context.seed and self.conf.get('seed_only'):
            return DummySource()
        
        if params is None: params = {}
        
        request_format = self.conf['req'].get('format')
        if request_format:
            params['format'] = request_format
        
        transparent = self.conf['req'].get('transparent', 'false')
        transparent = bool(str(transparent).lower() == 'true')
        
        opacity = self.conf.get('image', {}).get('opacity')
        
        resampling = self.context.globals.get_value('image.resampling_method', self.conf)
        
        supported_srs = [SRS(code) for code in self.conf.get('supported_srs', [])]
        supported_formats = [file_ext(f) for f in self.conf.get('supported_formats', [])]
        version = self.conf.get('wms_opts', {}).get('version', '1.1.1')
        
        lock = None
        concurrent_requests = self.context.globals.get_value('concurrent_requests', self.conf,
                                                        global_key='http.concurrent_requests')
        if concurrent_requests:
            lock_dir = self.context.globals.get_path('cache.lock_dir', self.conf)
            url = urlparse.urlparse(self.conf['req']['url'])
            md5 = hashlib.md5(url.netloc)
            lock_file = os.path.join(lock_dir, md5.hexdigest() + '.lck')
            lock = lambda: SemLock(lock_file, concurrent_requests)
        
        coverage = self.coverage()
        res_range = resolution_range(self.conf)
        
        transparent_color = self.conf.get('image', {}).get('transparent_color')
        transparent_color_tolerance = self.context.globals.get_value(
            'image.transparent_color_tolerance', self.conf)
        if transparent_color:
            transparent_color = parse_color(transparent_color)
        
        http_method = self.context.globals.get_value('http.method', self.conf)
        
        request = create_request(self.conf['req'], params, version=version)
        http_client, request.url = self.http_client(request.url)
        client = WMSClient(request, supported_srs, http_client=http_client, 
                           http_method=http_method, resampling=resampling, lock=lock,
                           supported_formats=supported_formats or None)
        return WMSSource(client, transparent=transparent, coverage=coverage,
                         res_range=res_range, opacity=opacity,
                         transparent_color=transparent_color,
                         transparent_color_tolerance=transparent_color_tolerance)
    
    def fi_source(self, params=None):
        if params is None: params = {}
        request_format = self.conf['req'].get('format')
        if request_format:
            params['format'] = request_format
        supported_srs = [SRS(code) for code in self.conf.get('supported_srs', [])]
        fi_source = None
        if self.conf.get('wms_opts', {}).get('featureinfo', False):
            wms_opts = self.conf['wms_opts']
            version = wms_opts.get('version', '1.1.1')
            if 'featureinfo_format' in wms_opts:
                params['info_format'] = wms_opts['featureinfo_format']
            fi_request = create_request(self.conf['req'], params,
                req_type='featureinfo', version=version)
            
            fi_transformer = self.fi_xslt_transformer(self.conf.get('wms_opts', {}),
                                                     self.context)
            
            http_client, fi_request.url = self.http_client(fi_request.url)
            fi_client = WMSInfoClient(fi_request, supported_srs=supported_srs,
                                      http_client=http_client)
            fi_source = WMSInfoSource(fi_client, fi_transformer=fi_transformer)
        return fi_source
    
    def lg_source(self, params=None):
        if params is None: params = {}
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
            lg_layers = lg_req['layers'].split(',')
            del lg_req['layers']
            for lg_layer in lg_layers:
                lg_req['layer'] = lg_layer
                lg_request = create_request(lg_req, params,
                    req_type='legendgraphic', version=version)
                http_client, lg_request.url = self.http_client(lg_request.url)
                lg_client = WMSLegendClient(lg_request, http_client=http_client)
                lg_clients.append(lg_client)
            legend_cache = LegendCache(cache_dir=cache_dir)
            lg_source = WMSLegendSource(lg_clients, legend_cache)
        return lg_source
    

class TileSourceConfiguration(SourceConfiguration):
    source_type = ('tile',)
    optional_keys = set('''type grid request_format origin coverage seed_only
                           transparent http'''.split())
    required_keys = set('url'.split())
    defaults = {'origin': 'sw', 'grid': 'GLOBAL_MERCATOR'}
    
    def source(self, params=None):
        if not self.context.seed and self.conf.get('seed_only'):
            return DummySource()
        
        if params is None: params = {}
        
        url = self.conf['url']
        origin = self.conf['origin']
        if origin not in ('sw', 'nw'):
            log.error("ignoring origin '%s', only supports sw and nw")
            origin = 'sw'
            # TODO raise some configuration exception
        
        http_client, url = self.http_client(url)
        grid = self.context.grids[self.conf['grid']].tile_grid()
        coverage = self.coverage()
        opacity = self.conf.get('image', {}).get('opacity')
        transparent = self.conf.get('transparent')
        
        inverse = True if origin == 'nw' else False
        format = file_ext(params['format'])
        client = TileClient(TileURLTemplate(url, format=format), http_client=http_client)
        return TiledSource(grid, client, inverse=inverse, coverage=coverage, opacity=opacity,
                           transparent=transparent)

def file_ext(mimetype):
    _mime_class, format, _options = split_mime_type(mimetype)
    return format

class DebugSourceConfiguration(SourceConfiguration):
    source_type = ('debug',)
    required_keys = set('type'.split())
    
    def source(self, params=None):
        return DebugSource()

class CacheConfiguration(ConfigurationBase):
    optional_keys = set('''format cache_dir grids link_single_color_images image
        use_direct_from_res use_direct_from_level meta_buffer meta_size
        minimize_meta_requests disable_storage'''.split())
    optional_keys.update(tile_filter_conf_keys)
    required_keys = set('name sources'.split())
    defaults = {'format': 'image/png', 'grids': ['GLOBAL_MERCATOR']}
    
    def cache_dir(self):
        return self.context.globals.get_path('cache_dir', self.conf,
            global_key='cache.base_dir')
        
    def _file_cache(self, grid_conf):
        if self.conf.get('disable_storage', False):
            return DummyCache()
        
        cache_dir = self.cache_dir()
        grid_conf.tile_grid() #create to resolve `base` in grid_conf.conf
        suffix = grid_conf.conf['srs'].replace(':', '')
        cache_dir = os.path.join(cache_dir, self.conf['name'] + '_' + suffix)
        link_single_color_images = self.conf.get('link_single_color_images', False)
        
        tile_filter = self._tile_filter()
        return FileCache(cache_dir, file_ext=file_ext(self.conf['format']),
            pre_store_filter=tile_filter,
            link_single_color_images=link_single_color_images)
    
    def _tile_filter(self):
        filters = []
        for tile_filter in tile_filters:
            f = tile_filter().create_filter(self.conf, self.context)
            if f is not None:
                filters.append(f)
        return filters
    
    @memoize
    def caches(self):
        request_format = self.conf.get('request_format') or self.conf['format']
        caches = []

        meta_buffer = self.context.globals.get_value('meta_buffer', self.conf,
            global_key='cache.meta_buffer')
        meta_size = self.context.globals.get_value('meta_size', self.conf,
            global_key='cache.meta_size')
        minimize_meta_requests = self.context.globals.get_value('minimize_meta_requests', self.conf,
            global_key='cache.minimize_meta_requests')
        
        for grid_conf in [self.context.grids[g] for g in self.conf['grids']]:
            sources = []
            for source_conf in [self.context.sources[s] for s in self.conf['sources']]:
                source = source_conf.source({'format': request_format})
                if source:
                    sources.append(source)
            assert sources, 'no sources configured for %s' % self.conf['name']
            cache = self._file_cache(grid_conf)
            tile_grid = grid_conf.tile_grid()
            mgr = TileManager(tile_grid, cache, sources, file_ext(request_format),
                              meta_size=meta_size, meta_buffer=meta_buffer,
                              minimize_meta_requests=minimize_meta_requests)
            extent = merge_layer_extents(sources)
            if extent.is_default:
                extent = map_extent_from_grid(tile_grid)
            caches.append((tile_grid, extent, mgr))
        return caches
    
    @memoize
    def map_layer(self):
        resampling = self.context.globals.get_value('image.resampling_method', self.conf)
        opacity = self.conf.get('image', {}).get('opacity')
        caches = []
        main_grid = None
        for grid, extent, tile_manager in self.caches():
            if main_grid is None:
                main_grid = grid
            caches.append((CacheMapLayer(tile_manager, extent=extent, resampling=resampling,
                                         opacity=opacity),
                          (grid.srs,)))
        
        if len(caches) == 1:
            layer = caches[0][0]
        else:
            layer = SRSConditional(caches, caches[0][0].extent, caches[0][0].transparent, opacity=opacity)
        
        if 'use_direct_from_level' in self.conf:
            self.conf['use_direct_from_res'] = main_grid.resolution(self.conf['use_direct_from_level'])
        if 'use_direct_from_res' in self.conf:
            if len(self.conf['sources']) != 1:
                raise ValueError('use_direct_from_level/res only supports single sources')
            source_conf = self.context.sources[self.conf['sources'][0]]
            layer = ResolutionConditional(layer, source_conf.source(), self.conf['use_direct_from_res'],
                                          main_grid.srs, layer.extent, opacity=opacity)
        return layer


class WMSLayerConfiguration(ConfigurationBase):
    optional_keys = set('name layers min_res max_res min_scale '
                        'max_scale legendurl sources'.split())
    required_keys = set('title'.split())
    
    @memoize
    def wms_layer(self):
        layers = []
        this_layer = None
        
        if 'layers' in self.conf:
            layers_conf = self.conf['layers']
            for layer_conf in layers_conf:
                layers.append(WMSLayerConfiguration(layer_conf, self.context).wms_layer())
        
        if 'sources' in self.conf or 'legendurl' in self.conf:
            this_layer = LayerConfiguration(self.conf, self.context).wms_layer()
        
        if not layers and not this_layer:
            raise ValueError('wms layer requires sources and/or layers')
        
        if not layers:
            layer = this_layer
        else:
            layer = WMSGroupLayer(name=self.conf.get('name'), title=self.conf.get('title'),
                                  this=this_layer, layers=layers)
        return layer

class LayerConfiguration(ConfigurationBase):
    optional_keys = set('min_res max_res min_scale max_scale legendurl sources layers'.split())
    required_keys = set('name title'.split())

    @memoize
    def wms_layer(self):
        sources = []
        fi_sources = []
        lg_sources = []
        
        lg_sources_configured = False
        if self.conf.get('legendurl'):
            legend_url = self.conf['legendurl']
            lg_sources.append(WMSSourceConfiguration.static_legend_source(legend_url, self.context))
            lg_sources_configured = True
        
        for source_name in self.conf.get('sources', []):
            fi_source_names = []
            lg_source_names = []
            if source_name in self.context.caches:
                map_layer = self.context.caches[source_name].map_layer()
                fi_source_names = self.context.caches[source_name].conf['sources']
                lg_source_names = self.context.caches[source_name].conf['sources']
            elif source_name in self.context.sources:
                map_layer = self.context.sources[source_name].source()
                fi_source_names = [source_name]
                lg_source_names = [source_name]
            else:
                raise ConfigurationError('source/cache "%s" not found' % source_name)
            
            if map_layer:
                sources.append(map_layer)
            
            for fi_source_name in fi_source_names:
                if not hasattr(self.context.sources[fi_source_name], 'fi_source'): continue
                fi_source = self.context.sources[fi_source_name].fi_source()
                if fi_source:
                    fi_sources.append(fi_source)
            if not lg_sources_configured:
                for lg_source_name in lg_source_names:
                    if not hasattr(self.context.sources[lg_source_name], 'lg_source'): continue
                    lg_source = self.context.sources[lg_source_name].lg_source()
                    if lg_source:
                        lg_sources.append(lg_source)
                
        res_range = resolution_range(self.conf)
        
        layer = WMSLayer(self.conf.get('name'), self.conf.get('title'),
                         sources, fi_sources, lg_sources, res_range=res_range)
        return layer
    
    @memoize
    def tile_layers(self):
        if len(self.conf.get('sources', [])) > 1: return [] #TODO
        
        tile_layers = []
        for cache_name in self.conf.get('sources', []):
            if not cache_name in self.context.caches: continue
            for grid, extent, cache_source in self.context.caches[cache_name].caches():
                md = {}
                md['title'] = self.conf['title']
                md['name'] = self.conf['name']
                md['name_path'] = (self.conf['name'], grid.srs.srs_code.replace(':', '').upper())
                md['name_internal'] = md['name_path'][0] + '_' + md['name_path'][1]
                md['format'] = self.context.caches[cache_name].conf['format']
            
                tile_layers.append(TileLayer(self.conf['name'], self.conf['title'],
                                             md, cache_source))
        
        return tile_layers
        

def fi_xslt_transformers(conf, context):
    fi_transformers = {}
    fi_xslt = conf.get('featureinfo_xslt')
    if fi_xslt:
        if not has_xslt_support:
            raise ValueError('featureinfo_xslt requires lxml. Please install.')
        for info_type, fi_xslt in fi_xslt.items():
            fi_xslt = context.globals.abspath(fi_xslt)
            fi_transformers[info_type] = XSLTransformer(fi_xslt)
    return fi_transformers

class ServiceConfiguration(ConfigurationBase):
    optional_keys = set('wms tms kml demo'.split())
    
    def services(self):
        services = {}
        for service_name, service_conf in self.conf.iteritems():
            creator = getattr(self, service_name + '_service', None)
            if not creator:
                raise ValueError('unknown service: %s' % service_name)
            services[service_name] = creator(service_conf or {})
        return services
    
    def tile_layers(self, conf):
        layers = odict()
        for layer_name, layer_conf in self.context.layers.iteritems():
            for tile_layer in layer_conf.tile_layers():
                if not tile_layer: continue
                layers[tile_layer.md['name_internal']] = tile_layer
        return layers
    
    def kml_service(self, conf):
        md = self.context.services.conf.get('wms', {}).get('md', {}).copy()
        md.update(conf.get('md', {}))
        layers = self.tile_layers(conf)
        return KMLServer(layers, md)
    
    def tms_service(self, conf):
        md = self.context.services.conf.get('wms', {}).get('md', {}).copy()
        md.update(conf.get('md', {}))
        layers = self.tile_layers(conf)
        return TileServer(layers, md)
    
    def wms_service(self, conf):
        md = conf.get('md', {})
        tile_layers = self.tile_layers(conf)
        attribution = conf.get('attribution')
        strict = self.context.globals.get_value('strict', conf, global_key='wms.strict')
        on_source_errors = self.context.globals.get_value('on_source_errors',
            conf, global_key='wms.on_source_errors')
        root_layer = self.context.wms_root_layer.wms_layer()
        if not root_layer.title:
            # set title of root layer to WMS title
            root_layer.title = md.get('title')
        concurrent_layer_renderer = self.context.globals.get_value(
            'concurrent_layer_renderer', conf,
            global_key='wms.concurrent_layer_renderer')
        image_formats = self.context.globals.get_value('image_formats', conf,
                                                       global_key='wms.image_formats')
        info_types = conf.get('featureinfo_types')
        srs = self.context.globals.get_value('srs', conf, global_key='wms.srs')
        self.context.globals.base_config.wms.srs = srs
        server = WMSServer(root_layer, md, attribution=attribution,
            image_formats=image_formats, info_types=info_types,
            srs=srs, tile_layers=tile_layers, strict=strict, on_error=on_source_errors,
            concurrent_layer_renderer=concurrent_layer_renderer)
        
        server.fi_transformers = fi_xslt_transformers(conf, self.context)
        
        return server

    def demo_service(self, conf):
        md = self.context.services.conf.get('wms', {}).get('md', {}).copy()
        md.update(conf.get('md', {}))
        layers = odict()
        for layer_name, layer_conf in self.context.layers.iteritems():
            layers[layer_name] = layer_conf.wms_layer()
        tile_layers = self.tile_layers(conf)
        image_formats = self.context.globals.get_value('image_formats', conf, global_key='wms.image_formats')
        return DemoServer(layers, md, tile_layers=tile_layers, image_formats=image_formats)
    
def load_services(conf_file):
    conf = load_configuration(conf_file)
    return conf.configured_services()

def load_yaml_file(file):
    if yaml.__with_libyaml__:
        return yaml.load(file, Loader=yaml.CLoader)
    else:
        return yaml.load(file)

def load_configuration(mapproxy_conf, seed=False):
    if hasattr(mapproxy_conf, 'read'):
        conf_data = mapproxy_conf.read()
        conf_base_dir = os.getcwd()
    else:
        log.info('Reading services configuration: %s' % mapproxy_conf)
        conf_data = open(mapproxy_conf).read()
        conf_base_dir = os.path.abspath(os.path.dirname(mapproxy_conf))
    conf_dict = load_yaml_file(conf_data)
    if 'base' in conf_dict:
        with open(os.path.join(conf_base_dir, conf_dict['base'])) as f:
            base_dict = load_yaml_file(f)
        if 'base' in base_dict:
            log.warn('found `base` option in base config but recursive inheritance is not supported.')
        conf_dict = merge_dict(conf_dict, base_dict)
    
    return ProxyConfiguration(conf_dict, conf_base_dir=conf_base_dir, seed=seed)

def merge_dict(conf, base):
    """
    Return `base` dict with values from `conf` merged in.
    """
    for k, v in conf.iteritems():
        if k not in base:
            base[k] = v
        else:
            if isinstance(base[k], dict):
                merge_dict(v, base[k])
            else:
                base[k] = v
    return base

def parse_color(color):
    """
    >>> parse_color((100, 12, 55))
    (100, 12, 55)
    >>> parse_color('0xff0530')
    (255, 5, 48)
    >>> parse_color('#FF0530')
    (255, 5, 48)
    """
    if isinstance(color, (list, tuple)):
        return color
    if not isinstance(color, basestring):
        raise ValueError('color needs to be a tuple/list or 0xrrggbb/#rrggbb string')
    
    if color.startswith('0x'):
        color = color[2:]
    if color.startswith('#'):
        color = color[1:]
    
    r, g, b = map(lambda x: int(x, 16), [color[:2], color[2:4], color[4:6]])
    
    return r, g, b
    
    