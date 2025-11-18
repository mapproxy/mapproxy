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
import itertools
import json
import os.path
from typing import Iterable, Optional, cast, Union

from jsonschema.exceptions import ValidationError
from jsonschema.validators import Draft202012Validator

import mapproxy.config.defaults

import logging
log = logging.getLogger('mapproxy.config')


with open(os.path.join(os.path.dirname(__file__), 'config-schema.json')) as schema_file:
    schema = json.load(schema_file)


TAGGED_SOURCE_TYPES = [
    'wms',
    'mapserver',
    'mapnik'
]


def get_error_messages(errors: Iterable[ValidationError]) -> list[str]:
    msgs = []
    for error in errors:
        path = error.json_path.replace('$', 'root')
        msg = f'{error.message} in {path}'
        msgs.append(msg)
        if error.context is not None:
            msgs += get_error_messages(error.context)
    return msgs


def add_service_to_config_schema(service_name, service_spec):
    """ Add a new service type to the schema.
        Used by plugins.
    """

    schema['properties']['services']['properties'][service_name] = service_spec


def validate(conf_dict: dict) -> list[str]:
    validator = Draft202012Validator(schema=schema)
    errors_iter = validator.iter_errors(conf_dict)
    errors = [] if errors_iter is None else get_error_messages(errors_iter)

    layers_conf = conf_dict.get('layers')

    if layers_conf is None:
        return errors
    else:
        return errors + list(itertools.chain.from_iterable(_validate_layer(conf_dict, layer) for layer in layers_conf))


def _validate_layer(conf_dict: dict, layer: dict) -> list[str]:
    layer_sources: list[str] = layer.get('sources', [])
    tile_sources: list[str] = layer.get('tile_sources', [])
    child_layers: list[dict] = layer.get('layers', [])

    caches_conf: dict = conf_dict.get('caches', {})
    sources_conf: dict = conf_dict.get('sources', {})

    errors = []

    for child_layer in child_layers:
        errors += _validate_layer(conf_dict, child_layer)

    for source in layer_sources:
        if source in caches_conf:
            errors += _validate_cache(conf_dict, source, caches_conf[source])
            continue

        source, layers = _split_tagged_source(source)
        if source in sources_conf:
            errors += _validate_source(conf_dict, source, sources_conf[source], layers)
            continue

        errors.append(
            f"Source '{source}' for layer '{layer['name']}' not in cache or source section"
        )

    for source in tile_sources:
        if source in caches_conf:
            errors += _validate_cache(conf_dict, source, caches_conf[source])
            continue

        errors.append(
            f"Tile source '{source}' for layer '{layer['name']}' not in cache section"
        )

    return errors


def _split_tagged_source(source_name: str) -> tuple[str, Optional[list[str]]]:
    layers = None
    if ':' in str(source_name):
        source_name, layers_str = str(source_name).split(':', 1)
        layers = layers_str.split(',') if layers_str is not None else None
    return source_name, layers


def _validate_source(conf_dict: dict, name: str, source: dict, layers: Optional[list[str]]) -> list[str]:
    source_type = source.get('type')
    if source_type == 'wms':
        return _validate_wms_source(name, source, layers)
    elif source_type == 'mapserver':
        return _validate_mapserver_source(conf_dict, name, source, layers)
    elif source_type == 'mapnik':
        return _validate_mapnik_source(name, source, layers)
    return []


def _validate_wms_source(name: str, source: dict, layers: Optional[list[str]]) -> list[str]:
    errors = []
    if source['req'].get('layers') is None and layers is None:
        errors.append("Missing 'layers' for source '%s'" % (
            name
        ))
    if source['req'].get('layers') is not None and layers is not None:
        errors += _validate_tagged_layer_source(
            name,
            source['req'].get('layers'),
            layers
        )
    return errors


def _validate_mapserver_source(conf_dict: dict[str, dict], name: str, source: dict,
                               layers: Optional[list[str]]) -> list[str]:
    globals_conf = cast(dict, conf_dict.get('globals'))
    errors: list[str] = []
    mapserver = cast(dict, source.get('mapserver'))
    if mapserver is None:
        if (
                not globals_conf or
                not globals_conf.get('mapserver') or
                not globals_conf['mapserver'].get('binary')
        ):
            errors.append(f"Missing mapserver binary for source '{name}'")
        elif not os.path.isfile(globals_conf['mapserver']['binary']):
            errors.append(f"Could not find mapserver binary ({globals_conf['mapserver'].get('binary')})")
    elif mapserver is None or not source['mapserver'].get('binary'):
        errors.append(f"Missing mapserver binary for source '{name}'")
    elif not os.path.isfile(source['mapserver']['binary']):
        errors.append(f"Could not find mapserver binary ({source['mapserver']['binary']})")

    if source['req'].get('layers') and layers is not None:
        errors += _validate_tagged_layer_source(
            name,
            source['req'].get('layers'),
            layers
        )

    return errors


def _validate_mapnik_source(name: str, source: dict, layers: Optional[list[str]]) -> list[str]:
    source_layers = source.get('layers')
    if source_layers is not None and layers is not None:
        return _validate_tagged_layer_source(name, source_layers, layers)
    return []


def _validate_tagged_layer_source(
        name: str, supported_layers: Union[str, list[str]], requested_layers: list[str]) -> list[str]:
    errors: list[str] = []
    if isinstance(supported_layers, str):
        supported_layers = supported_layers.split(',')
    if not set(requested_layers).issubset(set(supported_layers)):
        return [
            f"Supported layers for source '{name}' are '{', '.join(supported_layers)}' but tagged source requested"
            f" layers '{', '.join(requested_layers)}'"
        ]
    return errors


def _validate_cache(conf_dict: dict, name: str, cache: dict) -> list[str]:
    errors = []
    if isinstance(cache.get('sources', []), dict):
        errors += _validate_bands(name, set(cache['sources'].keys()))
        for band, confs in cache['sources'].items():
            for conf in confs:
                band_source = conf['source']
                errors += _validate_cache_source(conf_dict, name, band_source)
    else:
        for cache_source in cache.get('sources', []):
            errors += _validate_cache_source(conf_dict, name, cache_source)

    for grid in cache.get('grids', []):
        if grid not in _get_known_grids(conf_dict):
            errors.append(
                f"Grid '{grid}' for cache '{name}' not found in config"
            )

    return errors


def _validate_cache_source(conf_dict: dict, cache_name: str, source_name: str) -> list[str]:
    errors = []
    sources_conf: dict = conf_dict.get('sources', {})
    caches_conf: dict = conf_dict.get('caches', {})
    source_name, layers = _split_tagged_source(source_name)
    if sources_conf and source_name in sources_conf:
        source = sources_conf.get(source_name)
        if source is None:
            errors.append(f"Did not find source with name {source_name}")
            return errors
        if layers is not None and source.get('type') not in TAGGED_SOURCE_TYPES:
            errors.append(
                f"Found tagged source '{source_name}' in cache '{cache_name}' but tagged sources only supported for"
                f" '{', '.join(TAGGED_SOURCE_TYPES)}' sources"
            )
            return errors
        errors += _validate_source(conf_dict, source_name, source, layers)
        return errors
    if caches_conf and source_name in caches_conf:
        errors += _validate_cache(conf_dict, source_name, caches_conf[source_name])
        return errors
    errors.append(
        f"Source '{source_name}' for cache '{cache_name}' not found in config"
    )
    return errors


def _validate_bands(cache_name: str, bands: set[str]) -> list[str]:
    if 'l' in bands and len(bands) > 1:
        return [
            f"Cannot combine 'l' band with bands in cache '{cache_name}'"
        ]
    return []


def _get_known_grids(conf_dict: dict) -> set[str]:
    grids_conf = conf_dict.get('grids')
    known_grids = set(mapproxy.config.defaults.grids.keys())
    if grids_conf:
        known_grids.update(grids_conf.keys())
    return known_grids
