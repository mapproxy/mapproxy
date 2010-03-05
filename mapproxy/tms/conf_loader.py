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
