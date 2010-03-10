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

from mapproxy.core.conf_loader import CacheSource
from mapproxy.core.grid import tile_grid_for_epsg
from mapproxy.tms.cache import TMSTileSource
from mapproxy.tms.layer import TileServiceLayer
from mapproxy.tms import TileServer

def create_tms_server(proxy_conf):
    layers = configured_cache_layers(proxy_conf)
    return TileServer(layers, proxy_conf.service_md)
     
def configured_cache_layers(proxy_conf):
    layers = {}
    for layer in proxy_conf.layer_confs.itervalues():
        cache_layers = _configured_cache_layers(layer) 
        for name, cache_layer in cache_layers.iteritems():
            layers[name] = cache_layer
    return layers

def _configured_cache_layers(conf_layer):
    """
    Return all caches of this layer.
    """
    cache_layers = {}
    if not conf_layer.multi_layer:
        multi_layer_sources = [conf_layer.sources]
    else:
        multi_layer_sources = conf_layer.sources
    
    for sources in multi_layer_sources:
        if len(sources) > 1:
            continue
        source = sources[0]
        if not source.is_cache:
            continue
        md = conf_layer.layer['md'].copy()
        md['name'] = conf_layer.name
        md['name_internal'] = source.name
        md['name_path'] = (conf_layer.name, source.param['srs'].replace(':', '').upper())
        md['format'] = source.param['format']
        cache_layers[source.name] = TileServiceLayer(md, source.configured_cache())
    return cache_layers
    

class TMSCacheSource(CacheSource):
    def init_grid(self):
        self.grid = tile_grid_for_epsg(epsg=900913, tile_size=(256, 256))
    def init_tile_source(self):
        url = self.source.get('url', 'http://b.tile.openstreetmap.org')
        ll_origin = self.source.get('ll_origin', True)
        inverse = not ll_origin
        self.src = TMSTileSource(self.grid, url=url, inverse=inverse)
