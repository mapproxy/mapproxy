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

from mapproxy.core.cache import (FileCache, CacheManager, Cache,
                                  threaded_tile_creator)
from mapproxy.core.config import base_config, abspath

try:
    services_doc = open(os.path.join(os.path.dirname(__file__), '..', 'doc', 'services_yaml.rst')).read()
    __doc__ += '\n' + services_doc
    del services_doc
except:
    pass

def loader(loaders, name):
    """
    Return named class/function from loaders map.
    """
    entry_point = loaders[name]
    module_name, class_name = entry_point.split(':')
    module = __import__(module_name, {}, {}, class_name)
    return getattr(module, class_name)

source_loaders = {
    'cache_wms': 'mapproxy.wms.conf_loader:WMSCacheSource',
    'cache_tms': 'mapproxy.tms.conf_loader:TMSCacheSource',
    'debug': 'mapproxy.wms.conf_loader:DebugSource',
    'direct': 'mapproxy.wms.conf_loader:DirectSource',
}

def source_loader(name):
    return loader(source_loaders, name)


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
        layer_confs = {}
        for name, layer in self.conf['layers'].iteritems():
            layer_conf = LayerConf(name, layer, self.conf['service'],
                                   self.cache_dirs)
            layer_confs[name] = layer_conf
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
                conf_source = source_loader(source['type'])(self, source, param)
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
        tile_filter = self.get_tile_filter()
        self.file_cache = FileCache(cache_dir, file_ext=format,
                                    pre_store_filter=tile_filter)
    
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