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
from __future__ import with_statement

import os
import yaml #pylint: disable-msg=F0401
import types
import pkg_resources

import logging
log = logging.getLogger(__name__)

from mapproxy.core.srs import SRS
from mapproxy.core.cache import (FileCache, CacheManager, Cache,
                                  threaded_tile_creator)
from mapproxy.core.config import base_config, abspath
from mapproxy.core.odict import odict

def load_source_loaders():
    source_loaders = {}
    for entry_point in pkg_resources.iter_entry_points('mapproxy.source_loader'):
        source_loaders[entry_point.name] = entry_point
    return source_loaders

source_loaders = load_source_loaders()
del load_source_loaders


def loader(loaders, name):
    """
    Return named class/function from loaders map.
    """
    entry_point = loaders[name]
    module_name, class_name = entry_point.split(':')
    module = __import__(module_name, {}, {}, class_name)
    return getattr(module, class_name)


tile_filter_loaders = {
    'watermark': 'mapproxy.core.tilefilter:WaterMarkTileFilter',
    'pngquant': 'mapproxy.core.tilefilter:PNGQuantTileFilter',
}

def load_tile_filters():
    filters = []
    for key in tile_filter_loaders:
        filters.append(loader(tile_filter_loaders, key))
    filters.sort(key=lambda x: x.priority, reverse=True)
    return filters

tile_filters = load_tile_filters()
del load_tile_filters

server_loaders = {
    'wms': 'mapproxy.wms.conf_loader:create_wms_server',
    'tms': 'mapproxy.tms.conf_loader:create_tms_server',
    'kml': 'mapproxy.kml.conf_loader:create_kml_server',
}
def server_loader(name):
    return loader(server_loaders, name)

def load_services(services_conf=None):
    if services_conf is None:
        services_conf = base_config().services_conf
    if not os.path.isabs(services_conf):
        services_conf = os.path.join(base_config().conf_base_dir, services_conf)
    base_config().services_conf = services_conf
    log.info('Reading services configuration: %s' % services_conf)
    proxy_conf = ProxyConf(services_conf)
    server = {}
    for server_name in base_config().server:
        if server_name in server_loaders:
            server[server_name] = server_loader(server_name)(proxy_conf)
        else:
            log.warn('server \'%s\' configured but not found', server_name)
    return server
    
class ProxyConf(object):
    def __init__(self, conf_file):
        self.conf = yaml.load(open(conf_file))
        self.service_md = self.conf['service']['md']
        self.cache_dirs = set()
        self.layer_confs = self._init_layer_confs()
        
    def _init_layer_confs(self):
        layer_confs = odict()
        
        def _init_layer(name, layer):
            layer_conf = LayerConf(name, layer, self.conf['service'],
                                   self.cache_dirs)
            layer_confs[name] = layer_conf
        
        # layers is a dictionary
        if hasattr(self.conf['layers'], 'iteritems'):
            for name, layer in self.conf['layers'].iteritems():
                _init_layer(name, layer)
        else:
            # layers is a list of dictionaries
            for layer_dict in self.conf['layers']:
                for name, layer in layer_dict.iteritems():
                    _init_layer(name, layer)
        
        return layer_confs
    


class LayerConf(object):
    default_params = [('srs', 'EPSG:900913'),
                      ('format', 'image/png'),
                      ('bbox', None),
                      ('res', None),
                     ]
    def __init__(self, name, layer, service, cache_dirs):
        self.name = name
        self.layer = layer
        self.service = service
        self.cache_dirs = cache_dirs
        self.multi_layer = False
        self.param = self._init_param()
        self.sources = self._init_sources()
    
    def _init_param(self):
        layer_param = self.layer.get('param', {})
        for key, default in self.default_params:
            if key not in layer_param:
                layer_param[key] = default
        
        if not isinstance(layer_param['srs'], types.ListType):
            return layer_param
        else:
            params = []
            self.multi_layer = True
            for srs in layer_param['srs']:
                param = layer_param.copy()
                param['srs'] = srs
                params.append(param)
            return params
    
    def _init_sources(self):
        if self.multi_layer:
            params = self.param
        else:
            params = [self.param]
        
        multi_layer_sources = []
        for param in params:
            conf_sources = []
            for source in self.layer['sources']:
                conf_source = source_loaders[source['type']].load()(self, source, param)
                conf_sources.append(conf_source)
            multi_layer_sources.append(self._merge_sources(conf_sources))
        
        if self.multi_layer:
            return multi_layer_sources
        else:
            return multi_layer_sources[0]
    
    def _merge_sources(self, sources):
        if len(sources) <= 1:
            return sources
        
        merged_sources = []
        prev_source = None
        while sources:
            cur_source = sources.pop(0)
            if prev_source is not None and hasattr(prev_source, 'merge'):
                result = prev_source.merge(cur_source)
                if result is not None:
                    continue
            prev_source = cur_source
            merged_sources.append(prev_source)
        
        return merged_sources
        
    def cache_dir(self, suffix=None):
        if 'cache_dir' in self.layer:
            cache_dir = os.path.join(base_config().cache.base_dir,
                                     self.layer['cache_dir'])
        else:
            cache_dir = os.path.join(base_config().cache.base_dir, self.name)
        
        cache_dir = abspath(cache_dir)
        
        if suffix is not None:
            cache_dir += '_' + str(suffix)
        
        if cache_dir in self.cache_dirs:
            n = 2
            while cache_dir + '_' + str(n) in self.cache_dirs:
                n += 1
            cache_dir += '_' + str(n)
        
        self.cache_dirs.add(cache_dir)
        return cache_dir
        
    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.name, self.layer)

class Source(object):
    """
    :ivar layer_conf: the `LayerConf` of this source
    :ivar source: the source configuration
    :ivar param: the parameters for this source
    """
    is_cache = False
    
    def __init__(self, layer_conf, source, param=None):
        """
        :param param: the param for this source,
                      if ``None`` the param of the layer will be used.
        """
        self.layer_conf = layer_conf
        self.source = source
        if param is None:
            param = self.layer_conf.param
        self.param = param
        
        self.supported_srs = set(SRS(x) for x in self.source.get('supported_srs', []))
        if not self.supported_srs:
            self.supported_srs = None
    
    @property
    def name(self):
        return self.layer_conf.name
        
class CacheSource(Source):
    is_cache = True
    def __init__(self, layer_conf, source, param=None):
        Source.__init__(self, layer_conf, source, param)
        self.transparent = False
        self._configured_cache = None
        
        self.file_cache = None
        self.mgr = None
        self.creator = None
        self.src = None
        self.grid = None
        
    @property
    def name(self):
        srs = self.param['srs'].replace(':', '').upper()
        return self.layer_conf.name + '_' + srs

    def configured_cache(self):
        if self._configured_cache is None:
            self.init_grid()
            self.init_tile_source()
            self.init_file_cache()
            self.init_tile_creator()
            self.init_cache_manager()
        
            self._configured_cache = Cache(self.mgr, self.grid, self.transparent)
        
        return self._configured_cache
    
    def configured_layer(self):
        raise NotImplementedError()
    
    def init_grid(self):
        raise NotImplementedError()

    def init_tile_source(self):
        raise NotImplementedError()
    
    def init_file_cache(self):
        suffix = self.param['srs'].replace(':', '')
        cache_dir = self.layer_conf.cache_dir(suffix=suffix)
        format = self.param['format'].split('/')[1]
        link_single_color_images = self.param.get('link_single_color_images', False)
        tile_filter = self.get_tile_filter()
        self.file_cache = FileCache(cache_dir, file_ext=format,
                                    pre_store_filter=tile_filter,
                                    link_single_color_images=link_single_color_images)
    
    def get_tile_filter(self):
        filters = []
        for tile_filter in tile_filters:
            f = tile_filter().create_filter(self.layer_conf)
            if f is not None:
                filters.append(f)
        return filters
                
    def init_tile_creator(self):
        self.creator = threaded_tile_creator
    
    def init_cache_manager(self):
        self.mgr = CacheManager(self.file_cache, self.src, self.creator)


from mapproxy.core.grid import TileGrid
from mapproxy.wms.conf_loader import create_request, wms_clients_for_requests
from mapproxy.wms.cache import WMSTileSource
from mapproxy.wms.server import WMSServer
from mapproxy.wms.layer import WMSCacheLayer, VLayer, FeatureInfoSource
from mapproxy.core import defaults
from mapproxy.tms import TileServer
from mapproxy.tms.layer import TileServiceLayer
from mapproxy.kml import KMLServer

from mapproxy.core.cache import WMSClient, WMSSource, TileManager, CacheMapLayer

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
        
        self.grids['GLOBAL_GEODETIC'] = GridConfiguration(srs='EPSG:4326', bbox=[-180, -90, 180, 90])
        self.grids['GLOBAL_MERCATOR'] = GridConfiguration(srs='EPSG:900913')
        
        for grid_name, grid_conf in self.configuration.get('grids', {}).iteritems():
            self.grids[grid_name] = GridConfiguration(**grid_conf)
    
    def load_caches(self):
        self.caches = {}
        for cache_name, cache_conf in self.configuration.get('caches', {}).iteritems():
            self.caches[cache_name] = CacheConfiguration(name=cache_name, **cache_conf)
    
    def load_sources(self):
        self.sources = {}
        for source_name, source_conf in self.configuration.get('sources', {}).iteritems():
            self.sources[source_name] = SourceConfiguration.load(**source_conf)

    def load_layers(self):
        self.layers = {}
        for layer_name, layer_conf in self.configuration.get('layers', {}).iteritems():
            self.layers[layer_name] = LayerConfiguration(name=layer_name, **layer_conf)

    def load_services(self):
        self.services = ServiceConfiguration(**self.configuration.get('services', {}))
        # for service_name, service_conf in self.configuration.get('services', {}).iteritems():
        #     self.services[service_name] = ServiceConfiguration(name=service_name, **service_conf)


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
                raise ConfigurationError('unexpected key %s' % k)
            self.conf[k] = v
        
        for k in self.required_keys:
            if k not in self.conf:
                raise ConfigurationError('missing key %s' % k)
        
        for k, v in self.defaults.iteritems():
            if k not in self.conf:
                self.conf[k] = v

class GridConfiguration(ConfigurationBase):
    optional_keys = set('res srs bbox bbox_srs num_levels tile_size base'.split())
    
    def tile_grid(self, context):
        if 'base' in self.conf:
            base_grid_name = self.conf['base']
            conf = context.grids[base_grid_name].conf.copy()
            conf.update(self.conf)
        else:
            conf = self.conf
        
        bbox = conf.get('bbox')
        if isinstance(bbox, basestring):
            bbox = [float(x) for x in bbox.split(',')]
        if bbox and 'bbox_srs' in conf:
            bbox_srs = SRS(conf['bbox_srs'])
            srs = SRS(conf['srs'])
            bbox = bbox_srs.transform_bbox_to(srs, conf['bbox'])
        
        tile_size = conf.get('tile_size')
        if not tile_size:
            tile_size = context.globals.conf['tile_size']
        tile_size = tuple(tile_size)
        
        res = conf.get('res')
        if isinstance(res, list):
            res.sort(reverse=True)
        
        return TileGrid(
            srs=conf['srs'],
            tile_size=tile_size,
            res=res,
            bbox=bbox,
            levels=conf.get('num_levels'),
        )

class GlobalConfiguration(ConfigurationBase):
    defaults = {
        'tile_size': [256, 256],
        'meta_size': [4, 4],
        'meta_buffer': 0
    }

class SourceConfiguration(ConfigurationBase):
    @classmethod
    def load(cls, **kw):
        source_type = kw['type']
        for subclass in cls.__subclasses__():
            if source_type in subclass.source_type:
                return subclass(**kw)
        
        raise ValueError()

class WMSSourceConfiguration(SourceConfiguration):
    source_type = ('wms',)
    optional_keys = set('''type supported_srs image_resampling 
        use_direct_from_level wms_opts meta_size meta_buffer'''.split())
    required_keys = set('req'.split())
    defaults = {'meta_size': [1, 1], 'meta_buffer': 0}
    
    
    def source(self, grid_conf, cache_conf, context):
        tile_grid = grid_conf.tile_grid(context)
        
        #TODO legacy
        params = cache_conf.conf.copy()
        # params['bbox'] = ','.join(str(x) for x in tile_grid.bbox)
        # params['srs'] = tile_grid.srs.srs_code
        
        supported_srs = [SRS(code) for code in self.conf.get('supported_srs', [])]
        version = self.conf.get('wms_opts', {}).get('version', '1.1.1')
        request = create_request(self.conf['req'], params, version=version)
        client = WMSClient(request, supported_srs)
        return WMSSource(client)
    
    def fi_source(self, grid_conf, cache_conf, context):
        tile_grid = grid_conf.tile_grid(context)
        
        params = cache_conf.conf.copy()
        params['bbox'] = ','.join(str(x) for x in tile_grid.bbox)
        params['srs'] = tile_grid.srs.srs_code
        supported_srs = [SRS(code) for code in self.conf.get('supported_srs', [])]
        
        fi_source = None
        if self.conf.get('wms_opts', {}).get('featureinfo', False):
            version = self.conf.get('wms_opts', {}).get('version', '1.1.1')
            fi_request = create_request(self.conf['req'], params,
                req_type='featureinfo', version=version)
            fi_clients = wms_clients_for_requests([fi_request], supported_srs)
            fi_source = FeatureInfoSource(fi_clients)
        return fi_source
        
class CacheConfiguration(ConfigurationBase):
    optional_keys = set('format cache_dir grids link_single_color_images'.split())
    required_keys = set('name sources'.split())
    defaults = {'format': 'image/png', 'grids': ['GLOBAL_MERCATOR']}
    
    @property
    def format(self):
        return self.conf['format'].split('/')[1]
    
    def cache_dir(self, context):
        if 'cache_dir' in self.conf: 
            cache_dir = self.conf['cache_dir']
        else:
            cache_dir = context.configuration.get('global', {}).get('cache', {}).get('base_dir', None)
        
        if not cache_dir:
            cache_dir = base_config().cache.base_dir
        
        return abspath(cache_dir)
        
    def _file_cache(self, grid_conf, context):
        cache_dir = self.cache_dir(context)
        suffix = grid_conf.conf['srs'].replace(':', '')
        cache_dir = os.path.join(cache_dir, self.conf['name'] + '_' + suffix)
        link_single_color_images = self.conf.get('link_single_color_images', False)
        # tile_filter = self.get_tile_filter()
        return FileCache(cache_dir, file_ext=self.format,
            link_single_color_images=link_single_color_images)
    
    def obj(self, context):
        caches = []
        for source_conf in [context.sources[s] for s in self.conf['sources']]:
            for grid_conf in [context.grids[g] for g in self.conf['grids']]:
                file_cache = self._file_cache(grid_conf, context)
                tile_grid = grid_conf.tile_grid(context)
                source = source_conf.source(grid_conf, self, context)
                mgr = TileManager(tile_grid, file_cache, [source], self.format)
                caches.append(mgr)
        
        return caches
        

class LayerConfiguration(ConfigurationBase):
    optional_keys = set(''.split())
    required_keys = set('name title caches'.split())
    
    def wms_layer(self, context):
        caches = []
        for cache_name in self.conf['caches']:
            cache_source = context.caches[cache_name].obj(context)[0]
            caches.append(WMSCacheLayer(CacheMapLayer(cache_source)))
            
            # cache_sources_conf = context.sources[context.caches[cache_name].conf['sources'][0]]
            # grid_conf = context.grids[context.caches[cache_name].conf['grids'][0]]
            # fi_source = cache_sources_conf.fi_source(grid_conf, context.caches[cache_name], context)
            # 
            # cache = WMSCacheLayer(cache_source, fi_source)
            # caches.append(cache)
        
        layer = VLayer({'title': self.conf['title'], 'name': self.conf['name']}, caches)
        return layer
    
    def tile_layer(self, context):
        # todo multiple caches
        if len(self.conf['caches']) > 1: return None
        for cache_name in self.conf['caches']:
            cache_source = context.caches[cache_name].obj(context)[0]
            md = {}
            md['title'] = self.conf['title']
            md['name'] = self.conf['name']
            md['name_path'] = (self.conf['name'], cache_source.grid.srs.srs_code.replace(':', '').upper())
            md['name_internal'] = md['name_path'][0] + '_' + md['name_path'][1]
            md['format'] = context.caches[cache_name].conf['format']
            
            return TileServiceLayer(md, cache_source)
        
        

class ServiceConfiguration(ConfigurationBase):
    optional_keys = set('wms tms kml'.split())
    
    def services(self, context):
        services = {}
        for service_name, service_conf in self.conf.iteritems():
            creator = getattr(self, service_name + '_service', None)
            if not creator:
                raise ValueError('unknown service: %s' % service_name)
            services[service_name] = creator(service_conf or {}, context)
        return services
    
    def kml_service(self, conf, context):
        md = conf.get('md', {})
        layers = {}
        for layer_name, layer_conf in context.layers.iteritems():
            tile_layer = layer_conf.tile_layer(context)
            if not tile_layer: continue
            layers[tile_layer.md['name_internal']] = tile_layer
        
        return KMLServer(layers, md)
    
    def tms_service(self, conf, context):
        md = conf.get('md', {})
        layers = {}
        for layer_name, layer_conf in context.layers.iteritems():
            tile_layer = layer_conf.tile_layer(context)
            if not tile_layer: continue
            layers[tile_layer.md['name_internal']] = tile_layer
        
        return TileServer(layers, md)
    
    def wms_service(self, conf, context):
        md = conf.get('md', {})
        layers = {}
        for layer_name, layer_conf in context.layers.iteritems():
            layers[layer_name] = layer_conf.wms_layer(context)
        return WMSServer(layers, md)
    
def load_new_services(conf_file):
    if hasattr(conf_file, 'read'):
        conf_data = conf_file.read()
    else:
        conf_data = open(conf_file).read()
    conf_dict = yaml.load(conf_data)
    conf = ProxyConfiguration(conf_dict)
    
    return conf.services.services(conf)
    
        

