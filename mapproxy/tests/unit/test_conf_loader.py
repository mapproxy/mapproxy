# -.- encoding: utf-8 -.-
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

from __future__ import with_statement

from mapproxy.wms.cache import WMSTileSource
from mapproxy.tms.cache import TMSTileSource
from mapproxy.wms.layer import WMSLayer, DirectLayer, DebugLayer
from mapproxy.core.conf_loader import ProxyConf, LayerConf
from mapproxy.wms.conf_loader import create_wms_server, configured_layer
from mapproxy.core.srs import SRS

from nose.tools import eq_
from mapproxy.tests.helper import TempFiles

class TestDebugLayerLoader(object):
    def test_loading(self):
        name = 'debug'
        layer_config = {'md': {'title': 'Debug Layer'},
                        'sources': [{'type': 'debug'}]}
        layer = configured_layer(LayerConf(name, layer_config, {}, set()))
        assert isinstance(layer, DebugLayer)
        eq_(layer.md.title, 'Debug Layer')
        eq_(layer.md.name, 'debug')

class TestDirectLayerLoader(object):
    def test_loading(self):
        name = 'direct'
        layer_config = {'md': {'title': 'Direct Layer'},
                        'sources': [{'type': 'direct',
                                     'req': {'url': 'http://localhost:5050/service?'}}]}
        layer = configured_layer(LayerConf(name, layer_config, {}, set()))
        assert isinstance(layer, DirectLayer)
        eq_(layer.md.title, 'Direct Layer')
        eq_(layer.md.name, 'direct')
        eq_(layer.wms.request_template.url, 'http://localhost:5050/service?')
    

class TestTMSTileCacheLoader(object):
    def test_loading_w_defaults(self):
        name = 'tms'
        layer_config = {'md': {'title': 'TMS Cache Layer'},
                        'sources': [{'type': 'cache_tms'}]}
        layer = configured_layer(LayerConf(name, layer_config, {}, set()))
        assert isinstance(layer, WMSLayer)
        eq_(layer.md.title, 'TMS Cache Layer')
        eq_(layer.md.name, 'tms')
        assert isinstance(layer.cache.cache_mgr.tile_source,
                          TMSTileSource)
        cache_dir = layer.cache.cache_mgr.cache.cache_dir.replace('\\', '/')
        assert cache_dir.endswith('/../var/cache_data/tms_EPSG900913')
    

class TestWMSTileCacheLoader(object):
    def test_loading_w_defaults(self):
        name = 'wms'
        layer_config = {'md': {'title': 'WMS Cache Layer'},
                        'sources': [{'type': 'cache_wms',
                                     'req': {'url': 'http://localhost/service?',
                                             'layers': 'osm'}}]}
        layer = configured_layer(LayerConf(name, layer_config, {}, set()))
        assert isinstance(layer, WMSLayer)
        eq_(layer.md.title, 'WMS Cache Layer')
        eq_(layer.md.name, 'wms')
        cache_dir = layer.cache.cache_mgr.cache.cache_dir.replace('\\', '/')
        assert cache_dir.endswith('/../var/cache_data/wms_EPSG900913')
        
        wms_source = layer.cache.cache_mgr.tile_source
        assert isinstance(wms_source, WMSTileSource)
        eq_(len(wms_source.clients), 1)
        req = wms_source.clients[0].request_template
        eq_(req.url, 'http://localhost/service?')
        eq_(req.params['format'], 'image/png')
        eq_(req.params['srs'], 'EPSG:900913')
        eq_(req.params['layers'], 'osm')
    
    def test_loading_w_param(self):
        name = 'wms2'
        layer_config = {'md': {'title': u'WMS Cæch Layêr'},
                        'param': {'srs': 'EPSG:4326',
                                  'bbox': '5.40731,46.8447,15.5072,55.4314',
                                  'res': [0.001, 0.0001, 0.00001],
                                  'format': 'image/jpeg'},
                        'sources': [{'type': 'cache_wms',
                                     'req': {'url': 'http://localhost/service?',
                                             'layers': 'coast,roads'}}]}
        layer = configured_layer(LayerConf(name, layer_config, {}, set()))
        assert isinstance(layer, WMSLayer)
        eq_(layer.md.title, u'WMS Cæch Layêr')
        eq_(layer.md.name, 'wms2')
        cache_dir = layer.cache.cache_mgr.cache.cache_dir.replace('\\', '/')
        assert cache_dir.endswith('/../var/cache_data/wms2_EPSG4326')
        
        wms_source = layer.cache.cache_mgr.tile_source
        assert isinstance(wms_source, WMSTileSource)
        assert(not wms_source.transparent)
        eq_(len(wms_source.clients), 1)
        req = wms_source.clients[0].request_template
        eq_(req.url, 'http://localhost/service?')
        eq_(req.params['format'], 'image/jpeg')
        eq_(req.params['srs'], 'EPSG:4326')
        eq_(req.params['layers'], 'coast,roads')
        
        grid = wms_source.grid
        eq_(grid.srs, SRS(4326))
        eq_(grid.bbox, (5.40731,46.8447,15.5072,55.4314))
        eq_(len(grid.resolutions), 3)
    
    def test_loading_w_two_wms_sources(self):
        name = 'wms3'
        layer_config = {'md': {'title': u'WMS Merge'},
                        'cache_dir': '/tmp/cache_data/wms',
                        'param': {'srs': 'EPSG:4326',
                                  'bbox': '5.40731,46.8447,15.5072,55.4314',
                                  'res': [0.001, 0.0001, 0.00001]},
                        'sources': [{'type': 'cache_wms',
                                     'req': {'url': 'http://localhost/service?',
                                             'layers': 'roads',
                                             'transparent': 'true'}},
                                    {'type': 'cache_wms',
                                     'req': {'url': 'http://localhost/service2?',
                                             'layers': 'raster'}}]}
        layer = configured_layer(LayerConf(name, layer_config, {}, set()))
        assert isinstance(layer, WMSLayer)
        eq_(layer.cache.cache_mgr.cache.cache_dir, '/tmp/cache_data/wms_EPSG4326')
        
        wms_source = layer.cache.cache_mgr.tile_source
        assert isinstance(wms_source, WMSTileSource)
        assert(wms_source.transparent)
        eq_(len(wms_source.clients), 2)
        req = wms_source.clients[0].request_template
        eq_(req.url, 'http://localhost/service2?')
        eq_(req.params['format'], 'image/png')
        eq_(req.params['srs'], 'EPSG:4326')
        eq_(req.params['layers'], 'raster')
        req = wms_source.clients[1].request_template
        eq_(req.url, 'http://localhost/service?')
        eq_(req.params['format'], 'image/png')
        eq_(req.params['srs'], 'EPSG:4326')
        eq_(req.params['transparent'], 'true')
        eq_(req.params['layers'], 'roads')

class TestMergedLayers(object):
    def test_loading_merged_layers(self):
        name = 'merged'
        layer_config = {'md': {'title': u'Merge'},
                        'cache_dir': '/var/proxy/cache_data/merge',
                        'param': {'srs': 'EPSG:4326',
                                  'bbox': '5.40731,46.8447,15.5072,55.4314',
                                  'res': [0.001, 0.0001, 0.00001]},
                        'sources': [{'type': 'cache_wms',
                                     'req': {'url': 'http://localhost/service?',
                                             'layers': 'roads',
                                             'transparent': 'true'}},
                                    {'type': 'direct',
                                     'req': {'url': 'http://localhost/service?',
                                             'layers': 'names',
                                             'transparent': 'true'}},
                                    {'type': 'cache_wms',
                                     'req': {'url': 'http://localhost/service2?',
                                             'layers': 'raster'}}]}
        layer = configured_layer(LayerConf(name, layer_config, {}, set()))
        assert len(layer.sources) == 3
        wms_layer = layer.sources[0]
        assert isinstance(wms_layer, WMSLayer)
        eq_(wms_layer.cache.cache_mgr.cache.cache_dir, '/var/proxy/cache_data/merge_EPSG4326_2')
        wms_source = wms_layer.cache.cache_mgr.tile_source
        assert isinstance(wms_source, WMSTileSource)
        eq_(len(wms_source.clients), 1)
        req = wms_source.clients[0].request_template
        eq_(req.url, 'http://localhost/service2?')
        eq_(req.params['format'], 'image/png')
        eq_(req.params['srs'], 'EPSG:4326')
        eq_(req.params['layers'], 'raster')
        
        direct_layer = layer.sources[1]
        assert isinstance(direct_layer, DirectLayer)
        req = direct_layer.wms.request_template
        eq_(req.url, 'http://localhost/service?')
        
        wms_layer = layer.sources[2]
        assert isinstance(wms_layer, WMSLayer)
        eq_(wms_layer.cache.cache_mgr.cache.cache_dir, '/var/proxy/cache_data/merge_EPSG4326')
        wms_source = wms_layer.cache.cache_mgr.tile_source
        assert isinstance(wms_source, WMSTileSource)
        eq_(len(wms_source.clients), 1)
        req = wms_source.clients[0].request_template
        eq_(req.url, 'http://localhost/service?')
        eq_(req.params['format'], 'image/png')
        eq_(req.params['srs'], 'EPSG:4326')
        eq_(req.params['transparent'], 'true')
        eq_(req.params['layers'], 'roads')
    

class TestProxyConf(object):
    def test_from_yaml(self):
        with TempFiles() as tmp:
            with open(tmp[0], 'w') as conf:
                conf.write("""
service:
    md:
        name: omniscale_wms
        title: Omniscale WMS Proxy
        abstract: This is the fantastic Omniscale WMS Proxy.

layers:
    direct:
        md:
            title: Direct DebugWMS
        sources:
        - req:
            url: http://localhost:5000/service
          type: direct
""")
            conf = ProxyConf(tmp[0])
            server = create_wms_server(conf)
            eq_(server.md['title'], 'Omniscale WMS Proxy')
            assert 'direct' in server.layers