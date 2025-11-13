from __future__ import division

import os
import warnings
from collections import OrderedDict
from copy import deepcopy

from mapproxy.config import defaults
from mapproxy.config.configuration.service import ServiceConfiguration
from mapproxy.config.configuration.layer import WMSLayerConfiguration, LayerConfiguration
from mapproxy.config.configuration.cache import CacheConfiguration
from mapproxy.config.configuration.source import SourcesCollection, SourceConfiguration
from mapproxy.config.configuration.global_conf import GlobalConfiguration
from mapproxy.config.configuration.grid import GridConfiguration


class ProxyConfiguration(object):
    def __init__(self, conf, conf_base_dir=None, seed=False, renderd=False):
        self.configuration = conf
        self.seed = seed
        self.renderd = renderd

        if conf_base_dir is None:
            conf_base_dir = os.getcwd()

        self.load_globals(conf_base_dir=conf_base_dir)
        self.load_grids()
        self.load_caches()
        self.load_sources()
        self.load_wms_root_layer()
        self.load_tile_layers()
        self.load_services()

    def load_globals(self, conf_base_dir):
        self.globals = GlobalConfiguration(conf_base_dir=conf_base_dir,
                                           conf=self.configuration.get('globals') or {},
                                           context=self)

    def load_grids(self):
        self.grids = {}
        grid_configs = dict(defaults.grids)
        grid_configs.update(self.configuration.get('grids') or {})
        for grid_name, grid_conf in grid_configs.items():
            grid_conf.setdefault('name', grid_name)
            self.grids[grid_name] = GridConfiguration(grid_conf, context=self)

    def load_caches(self):
        self.caches = OrderedDict()
        caches_conf = self.configuration.get('caches')
        if not caches_conf:
            return
        if isinstance(caches_conf, list):
            caches_conf = list_of_dicts_to_ordered_dict(caches_conf)
        for cache_name, cache_conf in caches_conf.items():
            cache_conf['name'] = cache_name
            self.caches[cache_name] = CacheConfiguration(conf=cache_conf, context=self)

    def load_sources(self):
        self.sources = SourcesCollection()
        for source_name, source_conf in (self.configuration.get('sources') or {}).items():
            source_conf['name'] = source_name
            self.sources[source_name] = SourceConfiguration.load(conf=source_conf, context=self)

    def load_tile_layers(self):
        self.layers = OrderedDict()
        layers_conf = deepcopy(self._layers_conf_dict())
        if layers_conf is None:
            return
        layers = self._flatten_layers_conf_dict(layers_conf)
        for layer_name, layer_conf in layers.items():
            layer_conf['name'] = layer_name
            self.layers[layer_name] = LayerConfiguration(conf=layer_conf, context=self)

    def _legacy_layers_conf_dict(self):
        """
        Read old style layer configuration with a dictionary where
        the key is the layer name. Optionally: a list an each layer
        is wrapped in such dictionary.

        ::
          layers:
            foo:
              title: xxx
              sources: []
            bar:
              title: xxx
              sources: []

        or

        ::

          layers:
            - foo:
               title: xxx
               sources: []
            - bar:
               title: xxx
               sources: []

        """
        warnings.warn('old layer configuration syntax is deprecated since 1.4.0. '
                      'use list of dictionaries as documented', RuntimeWarning)
        layers = []
        layers_conf = self.configuration.get('layers')
        if not layers_conf:
            return None  # TODO config error
        if isinstance(layers_conf, list):
            layers_conf = list_of_dicts_to_ordered_dict(layers_conf)
        for layer_name, layer_conf in layers_conf.items():
            layer_conf['name'] = layer_name
            layers.append(layer_conf)
        return dict(title=None, layers=layers)

    def _layers_conf_dict(self):
        """
        Returns (recursive) layer configuration as a dictionary
        in unified structure:

        ::
            {
             title: 'xxx', # required, might be None
             name: 'xxx', # optional
             # sources or layers or both are required
             sources: [],
             layers: [
                {..., ...} # more layers like this
             ]
            }

        Multiple layers will be wrapped in an unnamed root layer, if the
        first level starts with multiple layers.
        """
        layers_conf = self.configuration.get('layers')
        if layers_conf is None:
            return

        if isinstance(layers_conf, list):
            if isinstance(layers_conf[0], dict) and len(layers_conf[0].keys()) == 1:
                # looks like ordered legacy config
                layers_conf = self._legacy_layers_conf_dict()
            elif len(layers_conf) == 1 and (
                'layers' in layers_conf[0]
                or 'sources' in layers_conf[0]
                    or 'tile_sources' in layers_conf[0]):
                # single root layer in list -> remove list
                layers_conf = layers_conf[0]
            else:
                # layer list without root -> wrap in root layer
                layers_conf = dict(title=None, layers=layers_conf)

        if len(layers_conf.keys() &
               set('layers name title sources'.split())) < 2:
            # looks like unordered legacy config
            layers_conf = self._legacy_layers_conf_dict()

        return layers_conf

    def _flatten_layers_conf_dict(self, layers_conf, _layers=None):
        """
        Returns a dictionary with all layers that have a name and sources.
        Flattens the layer tree.
        """
        layers = _layers if _layers is not None else OrderedDict()

        if 'layers' in layers_conf:
            for layer in layers_conf.pop('layers'):
                self._flatten_layers_conf_dict(layer, layers)

        if 'name' in layers_conf and ('sources' in layers_conf or 'tile_sources' in layers_conf):
            layers[layers_conf['name']] = layers_conf

        return layers

    def load_wms_root_layer(self):
        self.wms_root_layer = None

        layers_conf = self._layers_conf_dict()
        if layers_conf is None:
            return
        self.wms_root_layer = WMSLayerConfiguration(layers_conf, context=self)

    def load_services(self):
        self.services = ServiceConfiguration(self.configuration.get('services', {}), context=self)

    def configured_services(self):
        import mapproxy.config.config
        mapproxy.config.config._config.push(self.base_config)
        services = self.services.services()
        mapproxy.config.config._config.pop()
        return services

    @property
    def base_config(self):
        return self.globals.base_config

    def config_files(self):
        """
        Returns a dictionary with all configuration filenames and there timestamps.
        Contains any included files as well (see `base` option).
        """
        return self.configuration.get('__config_files__', {})


def list_of_dicts_to_ordered_dict(dictlist):
    """
    >>> d = list_of_dicts_to_ordered_dict([{'a': 1}, {'b': 2}, {'c': 3}])
    >>> list(d.items())
    [('a', 1), ('b', 2), ('c', 3)]
    """

    result = OrderedDict()
    for d in dictlist:
        for k, v in d.items():
            result[k] = v
    return result
