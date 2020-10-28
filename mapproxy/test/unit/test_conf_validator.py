# This file is part of the MapProxy project.
# Copyright (C) 2015 Omniscale <http://omniscale.de>
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

from __future__ import print_function

import yaml

from mapproxy.config.validator import validate_references


class TestValidator(object):
    def _test_conf(self, yaml_part=None):
        base = yaml.safe_load('''
            services:
                wms:
                    md:
                        title: MapProxy
            layers:
                - name: one
                  title: One
                  sources: [one_cache]
            caches:
                one_cache:
                    grids: [GLOBAL_MERCATOR]
                    sources: [one_source]
            sources:
                one_source:
                    type: wms
                    req:
                        url: http://localhost/service?
                        layers: one
        ''')
        if yaml_part is not None:
            base.update(yaml.safe_load(yaml_part))
        return base

    def test_valid_config(self):
        conf = self._test_conf()

        errors = validate_references(conf)
        assert errors == []

    def test_missing_layer_source(self):
        conf = self._test_conf()
        del conf['caches']['one_cache']

        errors = validate_references(conf)
        assert errors == [
            "Source 'one_cache' for layer 'one' not in cache or source section"
        ]

    def test_empty_layer_sources(self):
        conf = self._test_conf('''
            layers:
                - name: one
                  title: One
                  sources: []
        ''')

        errors = validate_references(conf)
        assert errors == [
            "Missing sources for layer 'one'"
        ]

    def test_missing_cache_source(self):
        conf = self._test_conf()
        del conf['sources']['one_source']

        errors = validate_references(conf)
        assert errors == [
            "Source 'one_source' for cache 'one_cache' not found in config"
        ]

    def test_missing_layers_section(self):
        conf = self._test_conf()
        del conf['layers']

        errors = validate_references(conf)
        assert errors == [
            'Missing layers section'
        ]

    def test_missing_services_section(self):
        conf = self._test_conf()
        del conf['services']
        errors = validate_references(conf)
        assert errors == [
            'Missing services section'
        ]

    def test_tile_source(self):
        conf = self._test_conf('''
            layers:
                - name: one
                  tile_sources: [missing]
        ''')

        errors = validate_references(conf)
        assert errors == [
            "Tile source 'missing' for layer 'one' not in cache section"
        ]

    def test_missing_grid(self):
        conf = self._test_conf('''
            caches:
                one_cache:
                    grids: [MYGRID_OTHERGRID]
            grids:
                MYGRID:
                    base: GLOBAL_GEODETIC
        ''')

        errors = validate_references(conf)
        assert errors == [
            "Grid 'MYGRID_OTHERGRID' for cache 'one_cache' not found in config"
        ]

    def test_misconfigured_wms_source(self):
        conf = self._test_conf()

        del conf['sources']['one_source']['req']['layers']

        errors = validate_references(conf)
        assert errors == [
            "Missing 'layers' for source 'one_source'"
        ]

    def test_misconfigured_mapserver_source_without_globals(self):
        conf = self._test_conf('''
            sources:
                one_source:
                    type: mapserver
                    req:
                        map: foo.map
                    mapserver:
                        binary: /foo/bar/baz
        ''')

        errors = validate_references(conf)
        assert errors == [
            'Could not find mapserver binary (/foo/bar/baz)'
        ]

        del conf['sources']['one_source']['mapserver']['binary']

        errors = validate_references(conf)
        assert errors == [
            "Missing mapserver binary for source 'one_source'"
        ]

        del conf['sources']['one_source']['mapserver']

        errors = validate_references(conf)
        assert errors == [
            "Missing mapserver binary for source 'one_source'"
        ]

    def test_misconfigured_mapserver_source_with_globals(self):
        conf = self._test_conf('''
            sources:
                one_source:
                    type: mapserver
                    req:
                        map: foo.map
            globals:
                mapserver:
                    binary: /foo/bar/baz
        ''')

        errors = validate_references(conf)
        assert errors == [
            'Could not find mapserver binary (/foo/bar/baz)'
        ]

        del conf['globals']['mapserver']['binary']

        errors = validate_references(conf)
        assert errors == [
            "Missing mapserver binary for source 'one_source'"
        ]

    def test_tagged_sources_with_layers(self):
        conf = self._test_conf('''
            caches:
                one_cache:
                    grids: [GLOBAL_MERCATOR]
                    sources: ['one_source:foo,bar']
        ''')

        errors = validate_references(conf)
        assert errors == [
            "Supported layers for source 'one_source' are 'one' but tagged source "
            "requested layers 'foo, bar'"
        ]

    def test_tagged_layer_sources_with_layers(self):
        conf = self._test_conf('''
            layers:
                - name: one
                  title: One
                  sources: ['one_source:foo,bar']
        ''')

        errors = validate_references(conf)
        assert errors == [
            "Supported layers for source 'one_source' are 'one' but tagged source "
            "requested layers 'foo, bar'"
        ]

    def test_tagged_layer_sources_without_layers(self):
        conf = self._test_conf('''
            layers:
                - name: one
                  title: One
                  sources: ['one_source:foo,bar']
        ''')

        del conf['sources']['one_source']['req']['layers']

        errors = validate_references(conf)
        assert errors == []

    def test_tagged_source_without_layers(self):
        conf = self._test_conf('''
            caches:
                one_cache:
                    grids: [GLOBAL_MERCATOR]
                    sources: ['one_source:foo,bar']
        ''')

        del conf['sources']['one_source']['req']['layers']

        errors = validate_references(conf)
        assert errors == []

    def test_tagged_source_with_colons(self):
        conf = self._test_conf('''
            caches:
                one_cache:
                    grids: [GLOBAL_MERCATOR]
                    sources: ['one_source:ns:foo,ns:bar']
        ''')

        del conf['sources']['one_source']['req']['layers']

        errors = validate_references(conf)
        assert errors == []

    def test_with_grouped_layer(self):
        conf = self._test_conf('''
            layers:
                - name: group
                  title: Group
                  layers:
                    - name: one
                      title: One
                      sources: [one_cache]
        ''')

        errors = validate_references(conf)
        assert errors == []

    def test_without_cache(self):
        conf = self._test_conf('''
            layers:
              - name: one
                title: One
                sources: [one_source]
        ''')

        errors = validate_references(conf)
        assert errors == []

    def test_mapserver_with_tagged_layers(self):
        conf = self._test_conf('''
            sources:
                one_source:
                    type: mapserver
                    req:
                        map: foo.map
                        layers: one
                    mapserver:
                        binary: /foo/bar/baz
            caches:
                one_cache:
                    grids: [GLOBAL_MERCATOR]
                    sources: ['one_source:foo,bar']
        ''')

        errors = validate_references(conf)
        assert errors == [
            'Could not find mapserver binary (/foo/bar/baz)',
            "Supported layers for source 'one_source' are 'one' but tagged source "
            "requested layers 'foo, bar'"
        ]

    def test_mapnik_with_tagged_layers(self):
        conf = self._test_conf('''
            sources:
                one_source:
                    type: mapnik
                    mapfile: foo.map
                    layers: one
            caches:
                one_cache:
                    grids: [GLOBAL_MERCATOR]
                    sources: ['one_source:foo,bar']
        ''')

        errors = validate_references(conf)
        assert errors == [
            "Supported layers for source 'one_source' are 'one' but tagged source "
            "requested layers 'foo, bar'"
        ]

    def test_tagged_layers_for_unsupported_source_type(self):
        conf = self._test_conf('''
            sources:
                one_source:
                    type: tile
                    url: http://localhost/tiles/
            caches:
                one_cache:
                    grids: [GLOBAL_MERCATOR]
                    sources: ['one_source:foo,bar']
        ''')

        errors = validate_references(conf)
        assert errors == [
            "Found tagged source 'one_source' in cache 'one_cache' but tagged sources "
            "only supported for 'wms, mapserver, mapnik' sources"
        ]

    def test_cascaded_caches(self):
        conf = self._test_conf('''
            caches:
                one_cache:
                    sources: [two_cache]
                two_cache:
                    grids: [GLOBAL_MERCATOR]
                    sources: ['one_source']
        ''')

        errors = validate_references(conf)
        assert errors == []

    def test_with_int_0_as_names_and_layers(self):
        conf = self._test_conf('''
            services:
                wms:
                    md:
                        title: MapProxy
            layers:
                - name: 0
                  title: One
                  sources: [0]
            caches:
                0:
                    grids: [GLOBAL_MERCATOR]
                    sources: [0]
            sources:
                0:
                    type: wms
                    req:
                        url: http://localhost/service?
                        layers: 0
        ''')

        errors = validate_references(conf)
        assert errors == []

    def test_band_merge_missing_source(self):
        conf = self._test_conf('''
            caches:
                one_cache:
                    sources:
                        l:
                            - source: dop
                              band: 1
                              factor: 0.4
                            - source: missing1
                              band: 2
                              factor: 0.2
                            - source: cache_missing_source
                              band: 2
                              factor: 0.2
                    grids: [GLOBAL_MERCATOR]
                cache_missing_source:
                    sources: [missing2]
                    grids: [GLOBAL_MERCATOR]

            sources:
                dop:
                    type: wms
                    req:
                        url: http://localhost/service?
                        layers: dop
        ''')

        errors = validate_references(conf)
        assert errors == [
            "Source 'missing1' for cache 'one_cache' not found in config",
            "Source 'missing2' for cache 'cache_missing_source' not found in config",
        ]
