from cStringIO import StringIO
from mapproxy.srs import SRS
from mapproxy.config.conf_loader import (
    GridConfiguration,
    ProxyConfiguration,
    WMSSourceConfiguration,
    load_services,
)
from mapproxy.cache import (
    TileManager,
)


from nose.tools import eq_
from nose.plugins.skip import SkipTest

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
        
        caches = conf.caches['osm'].caches(conf)
        eq_(len(caches), 1)
        grid, manager = caches[0]
        
        eq_(grid.srs, SRS(4326))
        eq_(grid.bbox, [5, 50, 10, 55])
        
        assert isinstance(manager, TileManager)
        
    def test_https_source_insecure(self):
        conf_dict = {
            'sources': {
                'osm': {
                    'type': 'wms',
                    'http':{'ssl': {'insecure': True}},
                    'req': {
                        'url': 'https://foo:bar@localhost/service?',
                        'layers': 'base',
                    },
                },
            },
        }
        
        conf = ProxyConfiguration(conf_dict)
        try:
            wms = conf.sources['osm'].source(conf, {'format': 'image/png'})
        except ImportError, e:
            raise SkipTest('no ssl support')
        
    
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