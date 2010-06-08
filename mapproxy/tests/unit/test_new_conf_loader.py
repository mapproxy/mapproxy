from cStringIO import StringIO
from mapproxy.core.srs import SRS
from mapproxy.core.conf_loader import (
    GridConfiguration,
    ProxyConfiguration,
    WMSSourceConfiguration,
    load_services,
)


from nose.tools import eq_

class TestGridConfiguration(object):
    def test_simple_grid(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55]}}}
        
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid(conf)
        
        eq_(grid.srs, SRS(4326))

    def test_simple_grid_w_base(self):
        conf = {'grids': {
            'base_grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55]},
            'grid': {'base': 'base_grid'}
        }}
        
        conf = ProxyConfiguration(conf)
        
        grid = conf.grids['grid'].tile_grid(conf)
        
        eq_(grid.srs, SRS(4326))



class TestWMSSourceConfiguration(object):
    def test_simple_grid(self):
        conf_dict = {
            'grids': {
                'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55]},
            },
            'sources': {
                'osm': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://localhost/service?',
                        'layers': 'base',
                    },
                },
            },
            'caches': {
                'osm': {
                    'sources': ['osm'],
                    'grids': ['grid'],
                }
            }
        }
        
        conf = ProxyConfiguration(conf_dict)
        
        # caches = conf.caches['osm'].obj(conf)
        
        # assert isinstance(caches[0], Cache)
        

class TestConfLoading(object):
    yaml_string = """
grids:
  germany:
    bbox: [6, 45, 12, 51]
    srs: 'EPSG:4326'
    tile_size: [512, 512]

caches:
  osm_wgs:
      grids: [germany]
      image:
        resampling_method: 'nearest'
      sources: [osm]

sources:
  osm:
    type: wms
    supported_srs: ['EPSG:31467']
    req: 
        url: http://foo
        layers: base
"""
    
    def test_loading(self):
        f = StringIO(self.yaml_string)
        wms = load_services(f)
        print wms