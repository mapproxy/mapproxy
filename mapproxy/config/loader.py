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
import yaml #pylint: disable-msg=F0401

import logging
log = logging.getLogger(__name__)

from mapproxy.srs import SRS
from mapproxy.util.ext.odict import odict
from mapproxy.cache.file import FileCache
from mapproxy.util.lock import SemLock
from mapproxy.config import base_config, abspath
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
from mapproxy.grid import tile_grid
from mapproxy.request.base import split_mime_type
from mapproxy.request.wms import create_request
from mapproxy.layer import (
    CacheMapLayer, SRSConditional,
    ResolutionConditional, map_extent_from_grid
)
from mapproxy.client.tile import TileClient, TileURLTemplate
from mapproxy.client.wms import WMSClient, WMSInfoClient
from mapproxy.service.wms import WMSServer, WMSLayer
from mapproxy.service.tile import TileServer, TileLayer
from mapproxy.service.kml import KMLServer
from mapproxy.service.demo import DemoServer
from mapproxy.source import DebugSource
from mapproxy.source.wms import WMSSource, WMSInfoSource
from mapproxy.source.tile import TiledSource

from mapproxy.cache.tile import TileManager


class ConfigurationError(Exception):
    pass

class ProxyConfiguration(object):
    def __init__(self, conf):
        self.configuration = conf

        self.load_globals()
        self.load_grids()
        self.load_caches()
        self.load_sources()
        self.load_layers()
        self.load_services()
    
    def load_globals(self):
        self.globals = GlobalConfiguration(**self.configuration.get('globals', {}))
    
    def load_grids(self):
        self.grids = {}
        
        self.grids['GLOBAL_GEODETIC'] = GridConfiguration(srs='EPSG:4326')
        self.grids['GLOBAL_MERCATOR'] = GridConfiguration(srs='EPSG:900913')
        
        for grid_name, grid_conf in self.configuration.get('grids', {}).iteritems():
            self.grids[grid_name] = GridConfiguration(**grid_conf)
    
    def load_caches(self):
        self.caches = odict()
        caches_conf = self.configuration.get('caches')
        if not caches_conf: return None # TODO config error
        if isinstance(caches_conf, list):
            caches_conf = list_of_dicts_to_ordered_dict(caches_conf)
        for cache_name, cache_conf in caches_conf.iteritems():
            self.caches[cache_name] = CacheConfiguration(name=cache_name, **cache_conf)
    
    def load_sources(self):
        self.sources = {}
        for source_name, source_conf in self.configuration.get('sources', {}).iteritems():
            self.sources[source_name] = SourceConfiguration.load(**source_conf)

    def load_layers(self):
        self.layers = odict()
        layers_conf = self.configuration.get('layers')
        if not layers_conf: return None # TODO config error
        if isinstance(layers_conf, list):
            layers_conf = list_of_dicts_to_ordered_dict(layers_conf)
        for layer_name, layer_conf in layers_conf.iteritems():
            self.layers[layer_name] = LayerConfiguration(name=layer_name, **layer_conf)

    def load_services(self):
        self.services = ServiceConfiguration(**self.configuration.get('services', {}))

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
    optional_keys = set()
    required_keys = set()
    defaults = {}
    
    def __init__(self, **kw):
        self.conf = {}
        expected_keys = set(self.optional_keys)
        expected_keys.update(self.required_keys)
        expected_keys.update(self.defaults.keys())
        for k, v in kw.iteritems():
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
        res_factor
        '''.split())
    
    def tile_grid(self, context):
        if 'base' in self.conf:
            base_grid_name = self.conf['base']
            conf = context.grids[base_grid_name].conf.copy()
            conf.update(self.conf)
            conf.pop('base')
            self.conf = conf
        else:
            conf = self.conf
        align_with = None
        if 'align_resolutions_with' in self.conf:
            align_with_grid_name = self.conf['align_resolutions_with']
            align_with = context.grids[align_with_grid_name].tile_grid(context)

        tile_size = context.globals.get_value('tile_size', conf,
            global_key='grid.tile_size')
        conf['tile_size'] = tuple(tile_size)
        tile_size = tuple(tile_size)
        
        stretch_factor = context.globals.get_value('stretch_factor', conf,
            global_key='image.stretch_factor')
        max_shrink_factor = context.globals.get_value('max_shrink_factor', conf,
            global_key='image.max_shrink_factor')
        
        
        grid = tile_grid(
            srs=conf.get('srs'),
            tile_size=tile_size,
            min_res=conf.get('min_res'),
            max_res=conf.get('max_res'),
            res=conf.get('res'),
            res_factor=conf.get('res_factor', 2.0),
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
    
    def __init__(self, **kw):
        ConfigurationBase.__init__(self, **kw)
        self._set_base_config()
        mapproxy.config.finish_base_config()
    
    def _set_base_config(self):
        self._copy_conf_values(self.conf, base_config())
    
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
            result = dotted_dict_get(default_key or global_key or key, base_config())
            
        return result
    
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
    def load(cls, **kw):
        source_type = kw['type']
        for subclass in cls.__subclasses__():
            if source_type in subclass.source_type:
                return subclass(**kw)
        
        raise ValueError("unknown source type '%s'" % source_type)

class WMSSourceConfiguration(SourceConfiguration):
    source_type = ('wms',)
    optional_keys = set('''type supported_srs supported_formats image
        wms_opts http concurrent_requests'''.split())
    required_keys = set('req'.split())
    
    def http_client(self, context, request):
        http_client = None
        url, (username, password) = auth_data_from_url(request.url)
        if username and password:
            insecure = context.globals.get_value('http.ssl_no_cert_checks', self.conf)
            request.url = url
            http_client = HTTPClient(url, username, password, insecure=insecure)
        return http_client
    
    def source(self, context, params=None):
        if params is None: params = {}
        
        request_format = self.conf['req'].get('format')
        if request_format:
            params['format'] = request_format
        
        transparent = self.conf['req'].get('transparent', 'false')
        transparent = bool(str(transparent).lower() == 'true')
        
        resampling = context.globals.get_value('image.resampling_method', self.conf)
        
        supported_srs = [SRS(code) for code in self.conf.get('supported_srs', [])]
        supported_formats = [file_ext(f) for f in self.conf.get('supported_formats', [])]
        version = self.conf.get('wms_opts', {}).get('version', '1.1.1')
        
        lock = None
        if 'concurrent_requests' in self.conf:
            lock_dir = abspath(context.globals.get_value('cache.lock_dir', self.conf))
            md5 = hashlib.md5(self.conf['req']['url'])
            lock_file = os.path.join(lock_dir, md5.hexdigest() + '.lck')
            lock = lambda: SemLock(lock_file, self.conf['concurrent_requests'])
        
        request = create_request(self.conf['req'], params, version=version)
        http_client = self.http_client(context, request)
        client = WMSClient(request, supported_srs, http_client=http_client, 
                           resampling=resampling, lock=lock,
                           supported_formats=supported_formats or None)
        return WMSSource(client, transparent=transparent)
    
    def fi_source(self, context, params=None):
        if params is None: params = {}
        request_format = self.conf['req'].get('format')
        if request_format:
            params['format'] = request_format
        supported_srs = [SRS(code) for code in self.conf.get('supported_srs', [])]
        fi_source = None
        if self.conf.get('wms_opts', {}).get('featureinfo', False):
            version = self.conf.get('wms_opts', {}).get('version', '1.1.1')
            fi_request = create_request(self.conf['req'], params,
                req_type='featureinfo', version=version)
            fi_client = WMSInfoClient(fi_request, supported_srs=supported_srs)
            fi_source = WMSInfoSource(fi_client)
        return fi_source


class TileSourceConfiguration(SourceConfiguration):
    source_type = ('tile',)
    optional_keys = set('''type grid request_format origin'''.split())
    required_keys = set('url'.split())
    defaults = {'origin': 'sw', 'grid': 'GLOBAL_MERCATOR'}
    
    def source(self, context, params=None):
        if params is None: params = {}
        
        url = self.conf['url']
        origin = self.conf['origin']
        if origin not in ('sw', 'nw'):
            log.error("ignoring origin '%s', only supports sw and nw")
            origin = 'sw'
            # TODO raise some configuration exception
        
        grid = context.grids[self.conf['grid']].tile_grid(context)
        
        inverse = True if origin == 'nw' else False
        format = file_ext(params['format'])
        client = TileClient(TileURLTemplate(url, format=format))
        return TiledSource(grid, client, inverse=inverse)

def file_ext(mimetype):
    _mime_class, format, _options = split_mime_type(mimetype)
    return format

class DebugSourceConfiguration(SourceConfiguration):
    source_type = ('debug',)
    required_keys = set('type'.split())
    
    def source(self, context, params=None):
        return DebugSource()

class CacheConfiguration(ConfigurationBase):
    optional_keys = set('''format cache_dir grids link_single_color_images image
        use_direct_from_res use_direct_from_level meta_buffer meta_size
        minimize_meta_requests'''.split())
    optional_keys.update(tile_filter_conf_keys)
    required_keys = set('name sources'.split())
    defaults = {'format': 'image/png', 'grids': ['GLOBAL_MERCATOR']}
    
    def cache_dir(self, context):
        cache_dir = context.globals.get_value('cache_dir', self.conf,
            global_key='cache.base_dir')
        return abspath(cache_dir)
        
    def _file_cache(self, grid_conf, context):
        cache_dir = self.cache_dir(context)
        grid_conf.tile_grid(context) #create to resolve `base` in grid_conf.conf
        suffix = grid_conf.conf['srs'].replace(':', '')
        cache_dir = os.path.join(cache_dir, self.conf['name'] + '_' + suffix)
        link_single_color_images = self.conf.get('link_single_color_images', False)
        
        tile_filter = self._tile_filter(context)
        return FileCache(cache_dir, file_ext=file_ext(self.conf['format']),
            pre_store_filter=tile_filter,
            link_single_color_images=link_single_color_images)
    
    def _tile_filter(self, context):
        filters = []
        for tile_filter in tile_filters:
            f = tile_filter().create_filter(self.conf, context)
            if f is not None:
                filters.append(f)
        return filters
    
    def caches(self, context):
        request_format = self.conf.get('request_format') or self.conf['format']
        caches = []

        meta_buffer = context.globals.get_value('meta_buffer', self.conf,
            global_key='cache.meta_buffer')
        meta_size = context.globals.get_value('meta_size', self.conf,
            global_key='cache.meta_size')
        minimize_meta_requests = self.conf.get('minimize_meta_requests', False)
        
        for grid_conf in [context.grids[g] for g in self.conf['grids']]:
            sources = []
            for source_conf in [context.sources[s] for s in self.conf['sources']]:
                source = source_conf.source(context, {'format': request_format})
                sources.append(source)
            cache = self._file_cache(grid_conf, context)
            tile_grid = grid_conf.tile_grid(context)
            mgr = TileManager(tile_grid, cache, sources, file_ext(request_format),
                              meta_size=meta_size, meta_buffer=meta_buffer,
                              minimize_meta_requests=minimize_meta_requests)
            caches.append((tile_grid, mgr))
        return caches
    
    def map_layer(self, context):
        resampling = context.globals.get_value('image.resampling_method', self.conf)
        
        caches = []
        main_grid = None
        for grid, tile_manager in self.caches(context):
            if main_grid is None:
                main_grid = grid
            caches.append((CacheMapLayer(tile_manager, resampling=resampling), (grid.srs,)))
        
        if len(caches) == 1:
            layer = caches[0][0]
        else:
            map_extent = map_extent_from_grid(main_grid)
            layer = SRSConditional(caches, map_extent, caches[0][0].transparent)
        
        if 'use_direct_from_level' in self.conf:
            self.conf['use_direct_from_res'] = main_grid.resolution(self.conf['use_direct_from_level'])
        if 'use_direct_from_res' in self.conf:
            if len(self.conf['sources']) != 1:
                raise ValueError('use_direct_from_level/res only supports single sources')
            source_conf = context.sources[self.conf['sources'][0]]
            layer = ResolutionConditional(layer, source_conf.source(context), self.conf['use_direct_from_res'], main_grid.srs, layer.extent)
        return layer
    
class LayerConfiguration(ConfigurationBase):
    optional_keys = set(''.split())
    required_keys = set('name title sources'.split())
    
    def wms_layer(self, context):
        sources = []
        fi_sources = []
        for source_name in self.conf['sources']:
            fi_source_names = []
            if source_name in context.caches:
                map_layer = context.caches[source_name].map_layer(context)
                fi_source_names = context.caches[source_name].conf['sources']
            elif source_name in context.sources:
                map_layer = context.sources[source_name].source(context)
                fi_source_names = [source_name]
            else:
                raise ConfigurationError('source/cache "%s" not found' % source_name)
            sources.append(map_layer)
            
            for fi_source_name in fi_source_names:
                # TODO multiple sources
                if not hasattr(context.sources[fi_source_name], 'fi_source'): continue
                fi_source = context.sources[fi_source_name].fi_source(context)
                if fi_source:
                    fi_sources.append(fi_source)
            
        
        layer = WMSLayer({'title': self.conf['title'], 'name': self.conf['name']}, sources, fi_sources)
        return layer
    
    def tile_layers(self, context):
        if len(self.conf['sources']) > 1: return [] #TODO
        
        tile_layers = []
        for cache_name in self.conf['sources']:
            if not cache_name in context.caches: continue
            for grid, cache_source in context.caches[cache_name].caches(context):
                md = {}
                md['title'] = self.conf['title']
                md['name'] = self.conf['name']
                md['name_path'] = (self.conf['name'], grid.srs.srs_code.replace(':', '').upper())
                md['name_internal'] = md['name_path'][0] + '_' + md['name_path'][1]
                md['format'] = context.caches[cache_name].conf['format']
            
                tile_layers.append(TileLayer(md, cache_source))
        
        return tile_layers
        


class ServiceConfiguration(ConfigurationBase):
    optional_keys = set('wms tms kml demo'.split())
    
    def services(self, context):
        services = {}
        for service_name, service_conf in self.conf.iteritems():
            creator = getattr(self, service_name + '_service', None)
            if not creator:
                raise ValueError('unknown service: %s' % service_name)
            services[service_name] = creator(service_conf or {}, context)
        return services
    
    def tile_layers(self, conf, context):
        layers = odict()
        for layer_name, layer_conf in context.layers.iteritems():
            for tile_layer in layer_conf.tile_layers(context):
                if not tile_layer: continue
                layers[tile_layer.md['name_internal']] = tile_layer
        return layers
    
    def kml_service(self, conf, context):
        md = context.services.conf.get('wms', {}).get('md', {}).copy()
        md.update(conf.get('md', {}))
        layers = self.tile_layers(conf, context)
        return KMLServer(layers, md)
    
    def tms_service(self, conf, context):
        md = context.services.conf.get('wms', {}).get('md', {}).copy()
        md.update(conf.get('md', {}))
        layers = self.tile_layers(conf, context)
        return TileServer(layers, md)
    
    def wms_service(self, conf, context):
        md = conf.get('md', {})
        tile_layers = self.tile_layers(conf, context)
        attribution = conf.get('attribution')
        strict = context.globals.get_value('strict', conf, global_key='wms.strict')
        layers = odict()
        for layer_name, layer_conf in context.layers.iteritems():
            layers[layer_name] = layer_conf.wms_layer(context)
        image_formats = context.globals.get_value('image_formats', conf, global_key='wms.image_formats')
        srs = context.globals.get_value('srs', conf, global_key='wms.srs')
        return WMSServer(layers, md, attribution=attribution, image_formats=image_formats,
            srs=srs, tile_layers=tile_layers, strict=strict)

    def demo_service(self, conf, context):
        md = context.services.conf.get('wms', {}).get('md', {}).copy()
        md.update(conf.get('md', {}))
        layers = odict()
        for layer_name, layer_conf in context.layers.iteritems():
            layers[layer_name] = layer_conf.wms_layer(context)
        tile_layers = self.tile_layers(conf, context)
        image_formats = context.globals.get_value('image_formats', conf, global_key='wms.image_formats')
        return DemoServer(layers, md, tile_layers=tile_layers, image_formats=image_formats)
    
def load_services(conf_file):
    if hasattr(conf_file, 'read'):
        conf_data = conf_file.read()
    else:
        log.info('Reading services configuration: %s' % conf_file)
        conf_data = open(conf_file).read()
    conf_dict = yaml.load(conf_data)
    conf = ProxyConfiguration(conf_dict)
    
    return conf.services.services(conf)
    
        

