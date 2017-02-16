# -:- encoding: UTF8 -:-
# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import division, with_statement
import yaml
import time
from mapproxy.srs import SRS
from mapproxy.config.loader import (
    ProxyConfiguration,
    load_configuration,
    merge_dict,
    ConfigurationError,
)
from mapproxy.config.coverage import load_coverage
from mapproxy.config.spec import validate_options
from mapproxy.cache.tile import TileManager
from mapproxy.seed.spec import validate_seed_conf
from mapproxy.test.helper import TempFile
from mapproxy.test.unit.test_grid import assert_almost_equal_bbox
from nose.tools import eq_, assert_raises
from nose.plugins.skip import SkipTest

class TestLayerConfiguration(object):
    def _test_conf(self, yaml_part):
        base = {'sources': {'s': {'type': 'wms', 'req': {'url': ''}}}}
        base.update(yaml.load(yaml_part))
        return base

    def test_legacy_ordered(self):
        conf = self._test_conf('''
            layers:
              - one:
                 title: Layer One
                 sources: [s]
              - two:
                 title: Layer Two
                 sources: [s]
              - three:
                 title: Layer Three
                 sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()

        # no root layer defined
        eq_(root.title, None)
        eq_(root.name, None)
        layers = root.child_layers()

        # names are in order
        eq_(layers.keys(), ['one', 'two', 'three'])

        eq_(len(layers), 3)
        eq_(layers['one'].title, 'Layer One')
        eq_(layers['two'].title, 'Layer Two')
        eq_(layers['three'].title, 'Layer Three')

        layers_conf = conf.layers
        eq_(len(layers_conf), 3)

    def test_legacy_unordered(self):
        conf = self._test_conf('''
            layers:
              one:
                title: Layer One
                sources: [s]
              two:
                title: Layer Two
                sources: [s]
              three:
                title: Layer Three
                sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()

        # no root layer defined
        eq_(root.title, None)
        eq_(root.name, None)
        layers = root.child_layers()

        # names might not be in order
        # layers.keys() != ['one', 'two', 'three']

        eq_(len(layers), 3)
        eq_(layers['one'].title, 'Layer One')
        eq_(layers['two'].title, 'Layer Two')
        eq_(layers['three'].title, 'Layer Three')

    def test_with_root(self):
        conf = self._test_conf('''
            layers:
              name: root
              title: Root Layer
              layers:
                - name: one
                  title: Layer One
                  sources: [s]
                - name: two
                  title: Layer Two
                  sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()

        eq_(root.title, 'Root Layer')
        eq_(root.name, 'root')
        layers = root.child_layers()

        # names are in order
        eq_(layers.keys(), ['root', 'one', 'two'])

        eq_(len(layers), 3)
        eq_(layers['root'].title, 'Root Layer')
        eq_(layers['one'].title, 'Layer One')
        eq_(layers['two'].title, 'Layer Two')

        layers_conf = conf.layers
        eq_(len(layers_conf), 2)

    def test_with_unnamed_root(self):
        conf = self._test_conf('''
            layers:
              title: Root Layer
              layers:
                - name: one
                  title: Layer One
                  sources: [s]
                - name: two
                  title: Layer Two
                  sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()

        eq_(root.title, 'Root Layer')
        eq_(root.name, None)

        layers = root.child_layers()
        # names are in order
        eq_(layers.keys(), ['one', 'two'])

    def test_without_root(self):
        conf = self._test_conf('''
            layers:
                - name: one
                  title: Layer One
                  sources: [s]
                - name: two
                  title: Layer Two
                  sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()

        eq_(root.title, None)
        eq_(root.name, None)

        layers = root.child_layers()
        # names are in order
        eq_(layers.keys(), ['one', 'two'])

    def test_hierarchy(self):
        conf = self._test_conf('''
            layers:
              title: Root Layer
              layers:
                - name: one
                  title: Layer One
                  layers:
                    - name: onea
                      title: Layer One A
                      sources: [s]
                    - name: oneb
                      title: Layer One B
                      layers:
                        - name: oneba
                          title: Layer One B A
                          sources: [s]
                        - name: onebb
                          title: Layer One B B
                          sources: [s]
                - name: two
                  title: Layer Two
                  sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()

        eq_(root.title, 'Root Layer')
        eq_(root.name, None)

        layers = root.child_layers()
        # names are in order
        eq_(layers.keys(), ['one', 'onea', 'oneb', 'oneba', 'onebb', 'two'])

        layers_conf = conf.layers
        eq_(len(layers_conf), 4)
        eq_(layers_conf.keys(), ['onea', 'oneba', 'onebb', 'two'])
        eq_(layers_conf['onea'].conf['title'], 'Layer One A')
        eq_(layers_conf['onea'].conf['name'], 'onea')
        eq_(layers_conf['onea'].conf['sources'], ['s'])

    def test_hierarchy_root_is_list(self):
        conf = self._test_conf('''
            layers:
              - title: Root Layer
                layers:
                    - name: one
                      title: Layer One
                      sources: [s]
                    - name: two
                      title: Layer Two
                      sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()

        eq_(root.title, 'Root Layer')
        eq_(root.name, None)

        layers = root.child_layers()
        # names are in order
        eq_(layers.keys(), ['one', 'two'])

    def test_without_sources_or_layers(self):
        conf = self._test_conf('''
            services:
                wms:
            layers:
              title: Root Layer
              layers:
                - name: one
                  title: Layer One
        ''')
        conf = ProxyConfiguration(conf)
        assert conf.wms_root_layer.wms_layer() == None
        try:
            conf.services.services()
        except ConfigurationError:
            # found no WMS layer
            pass
        else:
            assert False, 'expected ConfigurationError'


class TestGridConfiguration(object):
    def test_default_grids(self):
        conf = {}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['GLOBAL_MERCATOR'].tile_grid()
        eq_(grid.srs, SRS(900913))

        grid = conf.grids['GLOBAL_GEODETIC'].tile_grid()
        eq_(grid.srs, SRS(4326))


    def test_simple(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55]}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid()
        eq_(grid.srs, SRS(4326))

    def test_with_base(self):
        conf = {'grids': {
            'base_grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55]},
            'grid': {'base': 'base_grid'}
        }}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid()
        eq_(grid.srs, SRS(4326))

    def test_with_num_levels(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55], 'num_levels': 8}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid()
        eq_(len(grid.resolutions), 8)

    def test_with_bbox_srs(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:25832', 'bbox': [5, 50, 10, 55], 'bbox_srs': 'EPSG:4326'}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid()
        assert_almost_equal_bbox([213372, 5538660, 571666, 6102110], grid.bbox, -3)

    def test_with_min_res(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55], 'min_res': 0.0390625}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid()
        assert_almost_equal_bbox([5, 50, 10, 55], grid.bbox, 2)
        eq_(grid.resolution(0), 0.0390625)
        eq_(grid.resolution(1), 0.01953125)

    def test_with_max_res(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55], 'max_res': 0.0048828125}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid()
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

        caches = conf.caches['osm'].caches()
        eq_(len(caches), 1)
        grid, extent, manager = caches[0]

        eq_(grid.srs, SRS(4326))
        eq_(grid.bbox, (5.0, 50.0, 10.0, 55.0))

        assert isinstance(manager, TileManager)

    def check_source_layers(self, conf_dict, layers):
        conf = ProxyConfiguration(conf_dict)
        caches = conf.caches['osm'].caches()
        eq_(len(caches), 1)
        grid, extent, manager = caches[0]
        source_layers = manager.sources[0].client.request_template.params.layers
        eq_(source_layers, layers)

    def test_tagged_source(self):
        conf_dict = {
            'sources': {
                'osm': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://localhost/service?',
                    },
                },
            },
            'caches': {
                'osm': {
                    'sources': ['osm:base,roads'],
                    'grids': ['GLOBAL_MERCATOR'],
                }
            }
        }
        self.check_source_layers(conf_dict, ['base', 'roads'])

    def test_tagged_source_with_layers(self):
        conf_dict = {
            'sources': {
                'osm': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://localhost/service?',
                        'layers': 'base,roads,poi'
                    },
                },
            },
            'caches': {
                'osm': {
                    'sources': ['osm:base,roads'],
                    'grids': ['GLOBAL_MERCATOR'],
                }
            }
        }
        self.check_source_layers(conf_dict, ['base', 'roads'])

    def test_tagged_source_with_layers_missing(self):
        conf_dict = {
            'sources': {
                'osm': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://localhost/service?',
                        'layers': 'base,poi'
                    },
                },
            },
            'caches': {
                'osm': {
                    'sources': ['osm:base,roads'],
                    'grids': ['GLOBAL_MERCATOR'],
                }
            }
        }
        conf = ProxyConfiguration(conf_dict)
        try:
            conf.caches['osm'].caches()
        except ConfigurationError as ex:
            assert 'base,roads' in ex.args[0]
            assert ('base,poi' in ex.args[0] or 'poi,base' in ex.args[0])
        else:
            assert False, 'expected ConfigurationError'

    def test_tagged_source_on_non_wms_source(self):
        conf_dict = {
            'sources': {
                'osm': {
                    'type': 'tile',
                    'url': 'http://example.org/'
                },
            },
            'caches': {
                'osm': {
                    'sources': ['osm:base,roads'],
                    'grids': ['GLOBAL_MERCATOR'],
                }
            }
        }
        conf = ProxyConfiguration(conf_dict)
        try:
            conf.caches['osm'].caches()
        except ConfigurationError as ex:
            assert 'osm:base,roads' in ex.args[0]
        else:
            assert False, 'expected ConfigurationError'


    def test_layer_tagged_source(self):
        conf_dict = {
            'layers': [
                {
                    'name': 'osm',
                    'title': 'OSM',
                    'sources': ['osm:base,roads']
                }
            ],
            'sources': {
                'osm': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://localhost/service?',
                    },
                },
            },
        }
        conf = ProxyConfiguration(conf_dict)
        wms_layer = conf.layers['osm'].wms_layer()
        layers = wms_layer.map_layers[0].client.request_template.params.layers
        eq_(layers, ['base', 'roads'])

    def test_tagged_source_encoding(self):
        conf_dict = {
            'layers': [
                {
                    'name': 'osm',
                    'title': 'OSM',
                    'sources': [u'osm:☃']
                }
            ],
            'sources': {
                'osm': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://localhost/service?',
                    },
                },
            },
            'caches': {
                'osm': {
                    'sources': [u'osm:☃'],
                    'grids': ['GLOBAL_MERCATOR'],
                }
            }
        }
        # from source
        conf = ProxyConfiguration(conf_dict)
        wms_layer = conf.layers['osm'].wms_layer()
        layers = wms_layer.map_layers[0].client.request_template.params.layers
        eq_(layers, [u'☃'])
        # from cache
        self.check_source_layers(conf_dict, [u'☃'])

    def test_https_source_insecure(self):
        conf_dict = {
            'sources': {
                'osm': {
                    'type': 'wms',
                    'http':{'ssl_no_cert_checks': True},
                    'req': {
                        'url': 'https://foo:bar@localhost/service?',
                        'layers': 'base',
                    },
                },
            },
        }

        conf = ProxyConfiguration(conf_dict)
        try:
            conf.sources['osm'].source({'format': 'image/png'})
        except ImportError:
            raise SkipTest('no ssl support')


class TestBandMergeConfig(object):

    def test_invalid_band(self):
        conf_dict = {
            'caches': {
                'osm': {
                    'sources': {'f': [{'source': 'foo', 'band': 1}]},
                    'grids': ['GLOBAL_WEBMERCATOR'],
                }
            }
        }
        errors, informal_only = validate_options(conf_dict)
        eq_(len(errors), 1)
        assert "unknown 'f' in caches" in errors[0]

    def test_no_band_cache(self):
        conf_dict = {
            'caches': {
                'osm': {
                    'sources': {'l': [{'source': 'foo'}]},
                    'grids': ['GLOBAL_WEBMERCATOR'],
                }
            }
        }
        errors, informal_only = validate_options(conf_dict)
        eq_(len(errors), 1)
        assert "missing 'band', not in caches" in errors[0], errors


def load_services(conf_file):
    conf = load_configuration(conf_file)
    return conf.configured_services()

class TestConfLoading(object):
    yaml_string = b"""
services:
  wms:

layers:
  - name: osm
    title: OSM
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
        with TempFile() as f:
            open(f, 'wb').write(self.yaml_string)
            services = load_services(f)
        assert 'service' in services[0].names

    def test_loading_broken_yaml(self):
        with TempFile() as f:
            open(f, 'wb').write(b'\tbroken:foo')
            try:
                load_services(f)
            except ConfigurationError:
                pass
            else:
                assert False, 'expected configuration error'


class TestConfImport(object):

    yaml_string = """
globals:
  http:
    client_timeout: 1
    headers:
      baz: quux
"""

    yaml_parent = """
globals:
  http:
    client_timeout: 2
    headers:
      foo: bar
      bar: qux
      baz: qax
"""

    yaml_grand_parent = """
globals:
  http:
    client_timeout: 3
    method: GET
    headers:
      bar: baz
"""

    def test_loading(self):
        with TempFile() as gp:
            open(gp, 'wb').write(self.yaml_grand_parent.encode('utf-8'))
            self.yaml_parent = """
base:
  - %s
%s
""" % (gp, self.yaml_parent)

            with TempFile() as p:
                open(p, 'wb').write(self.yaml_parent.encode("utf-8"))

                self.yaml_string = """
base: [%s]
%s
""" % (p, self.yaml_string)

                with TempFile() as cfg:
                    open(cfg, 'wb').write(self.yaml_string.encode("utf-8"))

                    config = load_configuration(cfg)

                    http = config.globals.get_value('http')
                    eq_(http['client_timeout'], 1)
                    eq_(http['headers']['bar'], 'qux')
                    eq_(http['headers']['foo'], 'bar')
                    eq_(http['headers']['baz'], 'quux')
                    eq_(http['method'], 'GET')

                    config_files = config.config_files()
                    eq_(set(config_files.keys()), set([gp, p, cfg]))
                    assert abs(config_files[gp] - time.time()) < 10
                    assert abs(config_files[p] - time.time()) < 10
                    assert abs(config_files[cfg] - time.time()) < 10


class TestConfMerger(object):
    def test_empty_base(self):
        a = {'a': 1, 'b': [12, 13]}
        b = {}
        m = merge_dict(a, b)
        eq_(a, m)

    def test_empty_conf(self):
        a = {}
        b = {'a': 1, 'b': [12, 13]}
        m = merge_dict(a, b)
        eq_(b, m)

    def test_differ(self):
        a = {'a': 12}
        b = {'b': 42}
        m = merge_dict(a, b)
        eq_({'a': 12, 'b': 42}, m)

    def test_recursive(self):
        a = {'a': {'aa': 12, 'a':{'aaa': 100}}}
        b = {'a': {'aa': 11, 'ab': 13, 'a':{'aaa': 101, 'aab': 101}}}
        m = merge_dict(a, b)
        eq_({'a': {'aa': 12, 'ab': 13, 'a':{'aaa': 100, 'aab': 101}}}, m)


class TestLoadConfiguration(object):
    def test_with_warnings(object):
        with TempFile() as f:
            open(f, 'wb').write(b"""
services:
  unknown:
                """)
            load_configuration(f) # defaults to ignore_warnings=True

            assert_raises(ConfigurationError, load_configuration, f, ignore_warnings=False)


class TestImageOptions(object):
    def test_default_format(self):
        conf_dict = {
        }
        conf = ProxyConfiguration(conf_dict)
        image_opts = conf.globals.image_options.image_opts({}, 'image/png')
        eq_(image_opts.format, 'image/png')
        eq_(image_opts.mode, None)
        eq_(image_opts.colors, 256)
        eq_(image_opts.transparent, None)
        eq_(image_opts.resampling, 'bicubic')

    def test_default_format_paletted_false(self):
        conf_dict = {'globals': {'image': { 'paletted': False }}}
        conf = ProxyConfiguration(conf_dict)
        image_opts = conf.globals.image_options.image_opts({}, 'image/png')
        eq_(image_opts.format, 'image/png')
        eq_(image_opts.mode, None)
        eq_(image_opts.colors, None)
        eq_(image_opts.transparent, None)
        eq_(image_opts.resampling, 'bicubic')

    def test_update_default_format(self):
        conf_dict = {'globals': {'image': {'formats': {
            'image/png': {'colors': 16, 'resampling_method': 'nearest',
                     'encoding_options': {'quantizer': 'mediancut'}}
        }}}}
        conf = ProxyConfiguration(conf_dict)
        image_opts = conf.globals.image_options.image_opts({}, 'image/png')
        eq_(image_opts.format, 'image/png')
        eq_(image_opts.mode, None)
        eq_(image_opts.colors, 16)
        eq_(image_opts.transparent, None)
        eq_(image_opts.resampling, 'nearest')
        eq_(image_opts.encoding_options['quantizer'], 'mediancut')

    def test_custom_format(self):
        conf_dict = {'globals': {'image': {'resampling_method': 'bilinear',
            'formats': {
                'image/foo': {'mode': 'RGBA', 'colors': 42}
            }
        }}}
        conf = ProxyConfiguration(conf_dict)
        image_opts = conf.globals.image_options.image_opts({}, 'image/foo')
        eq_(image_opts.format, 'image/foo')
        eq_(image_opts.mode, 'RGBA')
        eq_(image_opts.colors, 42)
        eq_(image_opts.transparent, None)
        eq_(image_opts.resampling, 'bilinear')

    def test_format_grid(self):
        conf_dict = {
            'globals': {
                'image': {
                    'resampling_method': 'bilinear',
                }
            },
            'caches': {
                'test': {
                    'sources': [],
                    'grids': ['GLOBAL_MERCATOR'],
                    'format': 'image/png',
                }
            }
        }
        conf = ProxyConfiguration(conf_dict)
        image_opts = conf.caches['test'].image_opts()
        eq_(image_opts.format, 'image/png')
        eq_(image_opts.mode, None)
        eq_(image_opts.colors, 256)
        eq_(image_opts.transparent, None)
        eq_(image_opts.resampling, 'bilinear')

    def test_custom_format_grid(self):
        conf_dict = {
            'globals': {
                'image': {
                    'resampling_method': 'bilinear',
                    'formats': {
                        'png8': {'mode': 'P', 'colors': 256},
                        'image/png': {'mode': 'RGBA', 'transparent': True}
                    },
                }
            },
            'caches': {
                'test': {
                    'sources': [],
                    'grids': ['GLOBAL_MERCATOR'],
                    'format': 'png8',
                    'image': {
                        'colors': 16,
                    }
                },
                'test2': {
                    'sources': [],
                    'grids': ['GLOBAL_MERCATOR'],
                    'format': 'image/png',
                    'image': {
                        'colors': 8,
                    }
                }
            }
        }
        conf = ProxyConfiguration(conf_dict)
        image_opts = conf.caches['test'].image_opts()
        eq_(image_opts.format, 'image/png')
        eq_(image_opts.mode, 'P')
        eq_(image_opts.colors, 16)
        eq_(image_opts.transparent, None)
        eq_(image_opts.resampling, 'bilinear')

        image_opts = conf.caches['test2'].image_opts()
        eq_(image_opts.format, 'image/png')
        eq_(image_opts.mode, 'RGBA')
        eq_(image_opts.colors, 8)
        eq_(image_opts.transparent, True)
        eq_(image_opts.resampling, 'bilinear')

    def test_custom_format_source(self):
        conf_dict = {
            'globals': {
                'image': {
                    'resampling_method': 'bilinear',
                    'formats': {
                        'png8': {'mode': 'P', 'colors': 256, 'format': 'image/png'},
                        'image/png': {'mode': 'RGBA', 'transparent': True}
                    },
                }
            },
            'caches': {
                'test': {
                    'sources': ['test_source'],
                    'grids': ['GLOBAL_MERCATOR'],
                    'format': 'png8',
                    'image': {
                        'colors': 16,
                    }
                },
            },
            'sources': {
                'test_source': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://example.org/',
                        'layers': 'foo',
                    }
                }
            }
        }
        conf = ProxyConfiguration(conf_dict)
        _grid, _extent, tile_mgr = conf.caches['test'].caches()[0]
        image_opts = tile_mgr.image_opts
        eq_(image_opts.format, 'image/png')
        eq_(image_opts.mode, 'P')
        eq_(image_opts.colors, 16)
        eq_(image_opts.transparent, None)
        eq_(image_opts.resampling, 'bilinear')

        image_opts = tile_mgr.sources[0].image_opts
        eq_(image_opts.format, 'image/png')
        eq_(image_opts.mode, 'P')
        eq_(image_opts.colors, 256)
        eq_(image_opts.transparent, None)
        eq_(image_opts.resampling, 'bilinear')


        conf_dict['caches']['test']['request_format'] = 'image/tiff'
        conf = ProxyConfiguration(conf_dict)
        _grid, _extent, tile_mgr = conf.caches['test'].caches()[0]
        image_opts = tile_mgr.image_opts
        eq_(image_opts.format, 'image/png')
        eq_(image_opts.mode, 'P')
        eq_(image_opts.colors, 16)
        eq_(image_opts.transparent, None)
        eq_(image_opts.resampling, 'bilinear')

        image_opts = tile_mgr.sources[0].image_opts
        eq_(image_opts.format, 'image/tiff')
        eq_(image_opts.mode, None)
        eq_(image_opts.colors, None)
        eq_(image_opts.transparent, None)
        eq_(image_opts.resampling, 'bilinear')

    def test_encoding_options_errors(self):
        conf_dict = {
            'globals': {
                'image': {
                    'formats': {
                        'image/jpeg': {
                            'encoding_options': {
                                'foo': 'baz',
                            }
                        }
                    },
                }
            },
        }

        try:
            conf = ProxyConfiguration(conf_dict)
        except ConfigurationError:
            pass
        else:
            raise False('expected ConfigurationError')


        conf_dict['globals']['image']['formats']['image/jpeg']['encoding_options'] = {
            'quantizer': 'foo'
        }
        try:
            conf = ProxyConfiguration(conf_dict)
        except ConfigurationError:
            pass
        else:
            raise False('expected ConfigurationError')


        conf_dict['globals']['image']['formats']['image/jpeg']['encoding_options'] = {}
        conf = ProxyConfiguration(conf_dict)
        try:
            conf.globals.image_options.image_opts({'encoding_options': {'quantizer': 'foo'}}, 'image/jpeg')
        except ConfigurationError:
            pass
        else:
            raise False('expected ConfigurationError')


        conf_dict['globals']['image']['formats']['image/jpeg']['encoding_options'] = {
            'quantizer': 'fastoctree'
        }
        conf = ProxyConfiguration(conf_dict)

        conf.globals.image_options.image_opts({}, 'image/jpeg')

class TestLoadCoverage(object):
    def test_union(self):
        conf = {
            'coverages': {
                'covname': {
                    'union': [
                        {'bbox': [0, 0, 10, 10], 'srs': 'EPSG:4326'},
                        {'bbox': [10, 0, 20, 10], 'srs': 'EPSG:4326', 'unknown': True},
                    ],
                },
            },
        }

        errors, informal_only = validate_seed_conf(conf)
        assert informal_only
        assert len(errors) == 1
        eq_(errors[0], "unknown 'unknown' in coverages.covname.union[1]")
