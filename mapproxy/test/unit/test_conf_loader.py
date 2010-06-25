from __future__ import division
from cStringIO import StringIO
from mapproxy.srs import SRS
from mapproxy.config.loader import (
    GridConfiguration,
    ProxyConfiguration,
    WMSSourceConfiguration,
    load_services,
)
from mapproxy.cache.tile import TileManager

from mapproxy.test.unit.test_grid import assert_almost_equal_bbox
from nose.tools import eq_, assert_almost_equal
from nose.plugins.skip import SkipTest


class TestGridConfiguration(object):
    def test_default_grids(self):
        conf = {}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['GLOBAL_MERCATOR'].tile_grid(conf)
        eq_(grid.srs, SRS(900913))
    
        grid = conf.grids['GLOBAL_GEODETIC'].tile_grid(conf)
        eq_(grid.srs, SRS(4326))
    
    
    def test_simple(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55]}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid(conf)
        eq_(grid.srs, SRS(4326))

    def test_with_base(self):
        conf = {'grids': {
            'base_grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55]},
            'grid': {'base': 'base_grid'}
        }}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid(conf)
        eq_(grid.srs, SRS(4326))

    def test_with_num_levels(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55], 'num_levels': 8}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid(conf)
        eq_(len(grid.resolutions), 8)
    
    def test_with_bbox_srs(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:25832', 'bbox': [5, 50, 10, 55], 'bbox_srs': 'EPSG:4326'}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid(conf)
        assert_almost_equal_bbox([213372, 5538660, 571666, 6102110], grid.bbox, -3)
    
    def test_with_min_res(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55], 'min_res': 0.0390625}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid(conf)
        assert_almost_equal_bbox([5, 50, 10, 55], grid.bbox, 2)
        eq_(grid.resolution(0), 0.0390625)
        eq_(grid.resolution(1), 0.01953125)
    
    def test_with_max_res(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55], 'max_res': 0.0048828125}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid(conf)
        assert_almost_equal_bbox([5, 50, 10, 55], grid.bbox, 2)
        eq_(grid.resolution(0), 0.01953125)
        eq_(grid.resolution(1), 0.01953125/2)
    
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
        eq_(grid.bbox, (5.0, 50.0, 10.0, 55.0))
        
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