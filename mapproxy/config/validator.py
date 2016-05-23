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

import os.path
from mapproxy.compat import string_type, iteritems

import logging
log = logging.getLogger('mapproxy.config')

import mapproxy.config.defaults

TAGGED_SOURCE_TYPES = [
    'wms',
    'mapserver',
    'mapnik'
]


def validate_references(conf_dict):
    validator = Validator(conf_dict)
    return validator.validate()


class Validator(object):

    def __init__(self, conf_dict):
        self.sources_conf = conf_dict.get('sources', {})
        self.caches_conf = conf_dict.get('caches', {})
        self.layers_conf = conf_dict.get('layers')
        self.services_conf = conf_dict.get('services')
        self.grids_conf = conf_dict.get('grids')
        self.globals_conf = conf_dict.get('globals')

        self.errors = []
        self.known_grids = set(mapproxy.config.defaults.grids.keys())
        if self.grids_conf:
            self.known_grids.update(self.grids_conf.keys())

    def validate(self):
        if not self.layers_conf:
            self.errors.append("Missing layers section")
        if isinstance(self.layers_conf, dict):
            return []
        if not self.services_conf:
            self.errors.append("Missing services section")

        if len(self.errors) > 0:
            return self.errors

        for layer in self.layers_conf:
            self._validate_layer(layer)

        return self.errors

    def _validate_layer(self, layer):
        layer_sources = layer.get('sources', [])
        tile_sources = layer.get('tile_sources', [])
        child_layers = layer.get('layers', [])

        if not layer_sources and not child_layers and not tile_sources:
            self.errors.append(
                "Missing sources for layer '%s'" % layer.get('name')
            )
        for child_layer in child_layers:
            self._validate_layer(child_layer)

        for source in layer_sources:
            if source in self.caches_conf:
                self._validate_cache(source, self.caches_conf[source])
                continue
            if source in self.sources_conf:
                source, layers = self._split_tagged_source(source)
                self._validate_source(source, self.sources_conf[source], layers)
                continue

            self.errors.append(
                "Source '%s' for layer '%s' not in cache or source section" % (
                    source,
                    layer['name']
                )
            )

        for source in tile_sources:
            if source in self.caches_conf:
                self._validate_cache(source, self.caches_conf[source])
                continue

            self.errors.append(
                "Tile source '%s' for layer '%s' not in cache section" % (
                    source,
                    layer['name']
                )
            )


    def _split_tagged_source(self, source_name):
        layers = None
        if ':' in str(source_name):
            source_name, layers = str(source_name).split(':')
            layers = layers.split(',') if layers is not None else None
        return source_name, layers

    def _validate_source(self, name, source, layers):
        source_type = source.get('type')
        if source_type == 'wms':
            self._validate_wms_source(name, source, layers)
        if source_type == 'mapserver':
            self._validate_mapserver_source(name, source, layers)
        if source_type == 'mapnik':
            self._validate_mapnik_source(name, source, layers)

    def _validate_wms_source(self, name, source, layers):
        if source['req'].get('layers') is None and layers is None:
            self.errors.append("Missing 'layers' for source '%s'" % (
                name
            ))
        if source['req'].get('layers') is not None and layers is not None:
            self._validate_tagged_layer_source(
                name,
                source['req'].get('layers'),
                layers
            )

    def _validate_mapserver_source(self, name, source, layers):
        mapserver = source.get('mapserver')
        if mapserver is None:
            if (
                not self.globals_conf or
                not self.globals_conf.get('mapserver') or
                not self.globals_conf['mapserver'].get('binary')
            ):
                self.errors.append("Missing mapserver binary for source '%s'" % (
                    name
                ))
            elif not os.path.isfile(self.globals_conf['mapserver']['binary']):
                self.errors.append("Could not find mapserver binary (%s)" % (
                    self.globals_conf['mapserver'].get('binary')
                ))
        elif mapserver is None or not source['mapserver'].get('binary'):
            self.errors.append("Missing mapserver binary for source '%s'" % (
                name
            ))
        elif not os.path.isfile(source['mapserver']['binary']):
            self.errors.append("Could not find mapserver binary (%s)" % (
                source['mapserver']['binary']
            ))

        if source['req'].get('layers') and layers is not None:
            self._validate_tagged_layer_source(
                name,
                source['req'].get('layers'),
                layers
            )

    def _validate_mapnik_source(self, name, source, layers):
        if source.get('layers') and layers is not None:
            self._validate_tagged_layer_source(name, source.get('layers'), layers)

    def _validate_tagged_layer_source(self, name, supported_layers, requested_layers):
        if isinstance(supported_layers, string_type):
            supported_layers = [supported_layers]
        if not set(requested_layers).issubset(set(supported_layers)):
            self.errors.append(
                "Supported layers for source '%s' are '%s' but tagged source requested "
                "layers '%s'" % (
                    name,
                    ', '.join(supported_layers),
                    ', '.join(requested_layers)
                ))

    def _validate_cache(self, name, cache):
        if isinstance(cache.get('sources', []), dict):
            self._validate_bands(name, set(cache['sources'].keys()))
            for band, confs  in iteritems(cache['sources']):
                for conf in confs:
                    band_source = conf['source']
                    self._validate_cache_source(name, band_source)
        else:
            for cache_source in cache.get('sources', []):
                self._validate_cache_source(name, cache_source)

        for grid in cache.get('grids', []):
            if grid not in self.known_grids:
                self.errors.append(
                    "Grid '%s' for cache '%s' not found in config" % (
                        grid,
                        name
                    )
                )

    def _validate_cache_source(self, cache_name, source_name):
        source_name, layers = self._split_tagged_source(source_name)
        if self.sources_conf and source_name in self.sources_conf:
            source = self.sources_conf.get(source_name)
            if (
                layers is not None and
                source.get('type') not in TAGGED_SOURCE_TYPES
            ):
                self.errors.append(
                    "Found tagged source '%s' in cache '%s' but tagged sources only "
                    "supported for '%s' sources" % (
                        source_name,
                        cache_name,
                        ', '.join(TAGGED_SOURCE_TYPES)
                    )
                )
                return
            self._validate_source(source_name, source, layers)
            return
        if self.caches_conf and source_name in self.caches_conf:
            self._validate_cache(source_name, self.caches_conf[source_name])
            return
        self.errors.append(
            "Source '%s' for cache '%s' not found in config" % (
                source_name,
                cache_name
            )
        )

    def _validate_bands(self, cache_name, bands):
        if 'l' in bands and len(bands) > 1:
            self.errors.append(
                "Cannot combine 'l' band with bands in cache '%s'" % (
                    cache_name
                )
            )

