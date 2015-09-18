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

import os.path

import logging
log = logging.getLogger('mapproxy.config')

KNOWN_GRIDS = [
    'GLOBAL_GEODETIC',
    'GLOBAL_MERCATOR',
    'GLOBAL_WEBMERCATOR',
]

TAGGED_SOURCE_TYPES = [
    'wms',
    'mapserver',
    'mapnik'
]


def validate(conf_dict):
    log.info('Validator starts')
    errors = []
    sources_conf = conf_dict.get('sources', False)
    caches_conf = conf_dict.get('caches', False)
    layers_conf = conf_dict.get('layers', False)
    services_conf = conf_dict.get('services', False)
    grids_conf = conf_dict.get('grids', False)
    globals_conf = conf_dict.get('globals', False)

    if not layers_conf:
        errors.append('Missing layers section')
    if not services_conf:
        errors.append('Missing services section')

    if len(errors) > 0:
        return errors

    known_grids = set(KNOWN_GRIDS)
    if grids_conf:
        known_grids = known_grids.union(set(grids_conf.keys()))

    for layer in layers_conf:
        layer_sources = layer.get('sources', False)
        if not layer_sources:
            errors.append(
                'Missing sources for layer %s' % layer.get('name')
            )
        for source in layer_sources:
            if caches_conf and source in caches_conf:
                errors += validate_cache(source, caches_conf.get(source), sources_conf,
                                         caches_conf, globals_conf, known_grids)
                continue
            if sources_conf and source in sources_conf:
                source, layers = split_tagged_source(source)
                errors += validate_source(source, sources_conf.get(source), layers,
                                          globals_conf)
                continue

            errors.append(
                'Source %s for layer %s not in cache or source section' % (
                    source,
                    layer['name']
                )
            )
    return errors


def validate_source(name, source, layers, globals_conf):
    source_type = source.get('type', False)
    if source_type == 'wms':
        return validate_wms_source(name, source, layers)
    if source_type == 'mapserver':
        return validate_mapserver_source(name, source, layers, globals_conf)
    if source_type == 'mapnik':
        return validate_mapnik_source(name, source, layers)
    return []


def validate_wms_source(name, source, layers):
    errors = []
    if not source['req'].get('layers', False) and layers is None:
        errors.append('Missing "layers" for source %s' % (
            name
        ))
    if source['req'].get('layers', False) and layers is not None:
        errors += validate_tagged_layer_source(
            name,
            source['req'].get('layers'),
            layers
        )
    return errors


def validate_mapserver_source(name, source, layers, globals_conf):
    errors = []
    mapserver = source.get('mapserver', False)
    if mapserver is False:
        if (
            not globals_conf or
            not globals_conf.get('mapserver', False) or
            not globals_conf['mapserver'].get('binary', False)
        ):
            errors.append('Missing mapserver binary for source %s' % (
                name
            ))
        elif not os.path.isfile(globals_conf['mapserver'].get('binary', False)):
            errors.append('Could not find mapserver binary (%s)' % (
                globals_conf['mapserver'].get('binary', False)
            ))
    elif mapserver is None or not source['mapserver'].get('binary', False):
        errors.append('Missing mapserver binary for source %s' % (
            name
        ))
    elif not os.path.isfile(source['mapserver'].get('binary', False)):
        errors.append('Could not find mapserver binary (%s)' % (
            source['mapserver'].get('binary', False)
        ))

    if source['req'].get('layers', False) and layers is not None:
        errors += validate_tagged_layer_source(
            name,
            source['req'].get('layers'),
            layers
        )
    return errors


def validate_mapnik_source(name, source, layers):
    if source.get('layers', False) and layers is not None:
        return validate_tagged_layer_source(
            name,
            source.get('layers'),
            layers
        )
    return []


def split_tagged_source(source_name):
    layers = None
    if ':' in source_name:
        source_name, layers = source_name.split(':')
        layers = layers.split(',') if layers is not None else None
    return source_name, layers


def validate_tagged_layer_source(name, supported_layers, requested_layers):
    if isinstance(supported_layers, basestring):
        supported_layers = [supported_layers]
    if not set(requested_layers).issubset(set(supported_layers)):
        return [
            'Supported layers for source %s are %s but tagged source requested '
            'layers %s' % (
                name,
                ', '.join(supported_layers),
                ', '.join(requested_layers)
            )]
    return []


def validate_cache(name, cache, sources_conf, caches_conf, globals_conf, known_grids):
    errors = []
    for cache_source in cache.get('sources', []):
        cache_source, layers = split_tagged_source(cache_source)
        if sources_conf and cache_source in sources_conf:
            source = sources_conf.get(cache_source)
            if (
                layers is not None and
                source.get('type', None) not in TAGGED_SOURCE_TYPES
            ):
                errors += [
                    'Found tagged source %s in cache %s but tagged sources only '
                    'supported for %s sources' % (
                        cache_source,
                        name,
                        ', '.join(TAGGED_SOURCE_TYPES)
                    )
                ]
                continue
            errors += validate_source(
                cache_source,
                source,
                layers,
                globals_conf
            )
            continue
        if caches_conf and cache_source in caches_conf:
            errors += validate_cache(
                cache_source,
                caches_conf.get(cache_source),
                sources_conf,
                caches_conf,
                globals_conf,
                known_grids
            )
            continue
        errors.append(
            'Source %s for cache %s not found in config' % (
                cache_source,
                name
            )
        )

    for grid in cache.get('grids', False):
        if grid not in known_grids:
            errors.append(
                'Grid %s for cache %s not found in config' % (
                    grid,
                    name
                )
            )

    return errors
