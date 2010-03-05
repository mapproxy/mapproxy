from mapproxy.tms.conf_loader import configured_cache_layers
from mapproxy.kml import KMLServer

def create_kml_server(proxy_conf):
    layers = configured_cache_layers(proxy_conf)
    return KMLServer(layers, proxy_conf.service_md)
