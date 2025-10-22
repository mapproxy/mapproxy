# This file is part of the MapProxy project.
# Copyright (C) 2010-2016 Omniscale <http://omniscale.de>
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

"""
Configuration loading and system initializing.
"""
from __future__ import division

import json

from mapproxy.config.configuration.base import ConfigurationError
from mapproxy.config.configuration.proxy import ProxyConfiguration
from mapproxy.util.yaml import load_yaml_file, YAMLError
from mapproxy.config.spec import validate_options
from mapproxy.config.validator import validate

import os

import logging

log = logging.getLogger('mapproxy.config')


def load_plugins():
    """ Locate plugins that belong to the 'mapproxy' group and load them """
    try:
        import importlib.metadata
    except ImportError:
        return

    for dist in importlib.metadata.distributions():
        for ep in dist.entry_points:
            if ep.group == 'mapproxy':
                log.info('Loading plugin from package %s' % dist.metadata['name'])
                ep.load().plugin_entrypoint()


def load_configuration(mapproxy_conf, seed=False, ignore_warnings=True, renderd=False):

    load_plugins()

    conf_base_dir = os.path.abspath(os.path.dirname(mapproxy_conf))

    # A configuration is checked/validated four times, each step has a different
    # focus and returns different errors. The steps are:
    # 1. YAML loading: checks YAML syntax like tabs vs. space, indention errors, etc.
    # 2. Options: checks all options agains the spec and validates their types,
    #             e.g is disable_storage a bool, is layers a list, etc.
    # 3. References: checks if all referenced caches, sources and grids exist
    # 4. Initialization: creates all MapProxy objects, returns on first error

    try:
        conf_dict = load_configuration_file([os.path.basename(mapproxy_conf)], conf_base_dir)
        log.debug('Loaded configuration file: %s', json.dumps(conf_dict, indent=2, default=str))
    except YAMLError as ex:
        raise ConfigurationError(ex)
    errors, informal_only = validate_options(conf_dict)
    for error in errors:
        log.warning(error)
    if not informal_only or (errors and not ignore_warnings):
        raise ConfigurationError('invalid configuration')
    errors = validate(conf_dict)
    for error in errors:
        log.warning(error)

    services = conf_dict.get('services')
    if services is not None and 'demo' in services:
        log.warning('Application has demo page enabled. It is recommended to disable this in production.')

    return ProxyConfiguration(conf_dict, conf_base_dir=conf_base_dir, seed=seed,
                              renderd=renderd)


def load_configuration_file(files, working_dir):
    """
    Return configuration dict from imported files
    """
    # record all config files with timestamp for reloading
    conf_dict = {'__config_files__': {}}
    for conf_file in files:
        conf_file = os.path.normpath(os.path.join(working_dir, conf_file))
        log.info('reading: %s' % conf_file)
        current_dict = load_yaml_file(conf_file)
        conf_dict['__config_files__'][os.path.abspath(conf_file)] = os.path.getmtime(conf_file)
        if 'base' in current_dict:
            current_working_dir = os.path.dirname(conf_file)
            base_files = current_dict.pop('base')
            if isinstance(base_files, str):
                base_files = [base_files]
            imported_dict = load_configuration_file(base_files, current_working_dir)
            current_dict = merge_dict(current_dict, imported_dict)
        conf_dict = merge_dict(conf_dict, current_dict)

    return conf_dict


def merge_dict(conf, base):
    """
    Return `base` dict with values from `conf` merged in.
    """
    for k, v in conf.items():
        if k not in base:
            base[k] = v
        else:
            if isinstance(base[k], dict):
                if v is not None:
                    base[k] = merge_dict(v, base[k])
            elif isinstance(base[k], list):
                if v is not None:
                    if k in ['bbox', 'tile_size', 'max_output_pixels', 'sources', 'grids', 'res']:
                        base[k] = v
                    elif k in ['layers']:
                        base[k] = merge_layers(v, base[k])
                    elif len(v) == 0:  # delete
                        base[k] = None
                    else:
                        base[k] = base[k] + v
            else:
                base[k] = v
    return base


def merge_layers(conf, base):
    """
    Return `base` dict with values from `conf` merged in.
    """
    out = []
    remaining_conf = []
    for conf_layer in conf:
        remaining_conf.append(conf_layer['name'])

    for base_layer in base:
        found = False
        for conf_layer in conf:
            if conf_layer['name'] in remaining_conf and base_layer['name'] == conf_layer['name']:
                new_layer = merge_dict(conf_layer, base_layer)
                out.append(new_layer)
                remaining_conf.remove(conf_layer['name'])
                found = True
                break

        if not found:
            out.append(base_layer)

    for conf_layer in conf:
        if conf_layer['name'] in remaining_conf:
            out.append(conf_layer)

    return out
