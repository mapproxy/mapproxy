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

"""
System-wide configuration.
"""
import os
import copy
import contextlib
from mapproxy.util.yaml import load_yaml_file
from mapproxy.util.ext.local import LocalStack
from mapproxy.compat import iteritems

class Options(dict):
    """
    Dictionary with attribute style access.

    >>> o = Options(bar='foo')
    >>> o.bar
    'foo'
    """
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, dict.__repr__(self))

    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            raise AttributeError(name)

    __setattr__ = dict.__setitem__

    def __delattr__(self, name):
        if name in self:
            del self[name]
        else:
            raise AttributeError(name)

    def update(self, other=None, **kw):
        if other is not None:
            if hasattr(other, 'iteritems'):
                it = other.iteritems()
            elif hasattr(other, 'items'):
                it = other.items()
            else:
                it = iter(other)
        else:
            it = iter(kw)
        for key, value in it:
            if key in self and isinstance(self[key], Options):
                self[key].update(value)
            else:
                self[key] = value

    def __deepcopy__(self, memo):
        return Options(copy.deepcopy(list(self.items()), memo))

_config = LocalStack()
def base_config():
    """
    Returns the context-local system-wide configuration.
    """
    config = _config.top
    if config is None:
        import warnings
        warnings.warn("calling un-configured base_config",
            DeprecationWarning, stacklevel=2)
        config = load_default_config()
        config.conf_base_dir = os.getcwd()
        finish_base_config(config)
        _config.push(config)
    return config

@contextlib.contextmanager
def local_base_config(conf):
    """
    Temporarily set the global configuration (mapproxy.config.base_config).

    The global mapproxy.config.base_config object is thread-local and
    is set per-request in the MapProxyApp. Use `local_base_config` to
    set base_config outside of a request context (e.g. system loading
    or seeding).
    """
    import mapproxy.config.config
    mapproxy.config.config._config.push(conf)
    try:
        yield
    finally:
        mapproxy.config.config._config.pop()

def _to_options_map(mapping):
    if isinstance(mapping, dict):
        opt = Options()
        for key, value in iteritems(mapping):
            opt[key] = _to_options_map(value)
        return opt
    elif isinstance(mapping, list):
        return [_to_options_map(m) for m in mapping]
    else:
        return mapping

def abspath(path, base_path=None):
    """
    Convert path to absolute path. Uses ``conf_base_dir`` as base, if
    path is relative and ``base_path`` is not set.
    """
    if base_path:
        return os.path.abspath(os.path.join(base_path, path))
    return os.path.join(base_config().conf_base_dir, path)


def finish_base_config(bc=None):
    bc = bc or base_config()
    if 'srs' in bc:
        # build union of default axis_order_xx_ and the user configured axis_order_xx
        default_ne = bc.srs.axis_order_ne_
        default_en = bc.srs.axis_order_en_
        # remove from default to allow overwrites
        default_ne.difference_update(set(bc.srs.axis_order_en))
        default_en.difference_update(set(bc.srs.axis_order_ne))
        bc.srs.axis_order_ne = default_ne.union(set(bc.srs.axis_order_ne))
        bc.srs.axis_order_en = default_en.union(set(bc.srs.axis_order_en))
        if 'proj_data_dir' in bc.srs:
            bc.srs.proj_data_dir = os.path.join(bc.conf_base_dir, bc.srs.proj_data_dir)

    if 'wms' in bc:
        bc.wms.srs = set(bc.wms.srs)

    if 'conf_base_dir' in bc:
        if 'cache' in bc:
            if 'base_dir' in bc.cache:
                bc.cache.base_dir = os.path.join(bc.conf_base_dir, bc.cache.base_dir)
            if 'lock_dir' in bc.cache:
                bc.cache.lock_dir = os.path.join(bc.conf_base_dir, bc.cache.lock_dir)

def load_base_config(config_file=None, clear_existing=False):
    """
    Load system wide base configuration.

    :param config_file: the file name of the mapproxy.yaml configuration.
                        if ``None``, load the internal proxylib/default.yaml conf
    :param clear_existing: if ``True`` remove the existing configuration settings,
                           else overwrite the settings.
    """

    if config_file is None:
        from mapproxy.config import defaults
        config_dict = {}
        for k, v in iteritems(defaults.__dict__):
            if k.startswith('_'): continue
            config_dict[k] = v
        conf_base_dir = os.getcwd()
        load_config(base_config(), config_dict=config_dict, clear_existing=clear_existing)
    else:
        conf_base_dir = os.path.abspath(os.path.dirname(config_file))
        load_config(base_config(), config_file=config_file, clear_existing=clear_existing)

    bc = base_config()
    finish_base_config(bc)

    bc.conf_base_dir = conf_base_dir

def load_default_config():
    from mapproxy.config import defaults
    config_dict = {}
    for k, v in iteritems(defaults.__dict__):
        if k.startswith('_'): continue
        config_dict[k] = v

    default_conf = Options()
    load_config(default_conf, config_dict=config_dict)
    return default_conf

def load_config(config, config_file=None, config_dict=None, clear_existing=False):
    if clear_existing:
        for key in list(config.keys()):
            del config[key]

    if config_dict is None:
        config_dict = load_yaml_file(config_file)

    defaults = _to_options_map(config_dict)

    if defaults:
        for key, value in iteritems(defaults):
            if key in config and hasattr(config[key], 'update'):
                config[key].update(value)
            else:
                config[key] = value
