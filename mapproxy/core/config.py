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

"""
System-wide configuration.
"""
from __future__ import with_statement
import os
import yaml #pylint: disable-msg=F0401

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
            else:
                it = iter(other)
        else:
            it = iter(kw)
        for key, value in it:
            if key in self and isinstance(self[key], Options):
                self[key].update(value)
            else:
                self[key] = value

_config = None
def base_config():
    """
    Returns the system wide configuration.
    """
    global _config
    if _config is None:
        _config = Options()
        load_base_config()
    return _config

def _to_options_map(mapping):
    if isinstance(mapping, dict):
        opt = Options()
        for key, value in mapping.iteritems():
            opt[key] = _to_options_map(value)
        return opt
    elif isinstance(mapping, list):
        return [_to_options_map(m) for m in mapping]
    else:
        return mapping

def abspath(path):
    """
    Convert path to absolute path. Uses ``conf_base_dir`` as base, if path is relative. 
    """
    return os.path.join(base_config().conf_base_dir, path)


def load_base_config(config_file=None, clear_existing=False):
    """
    Load system wide base configuration.
    
    :param config_file: the file name of the proxy.yaml configuration.
                        if ``None``, load the internal proxylib/default.yaml conf
    :param clear_existing: if ``True`` remove the existing configuration settings,
                           else overwrite the settings.
    """
    
    if config_file is None:
        from mapproxy.core import defaults
        config_dict = {}
        for k, v in defaults.__dict__.iteritems():
            if k.startswith('_'): continue
            config_dict[k] = v
        conf_base_dir = os.getcwd()
        load_config(base_config(), config_dict=config_dict, clear_existing=clear_existing)
    else:
        conf_base_dir = os.path.abspath(os.path.dirname(config_file))
        load_config(base_config(), config_file=config_file, clear_existing=clear_existing)
    
    base_config().conf_base_dir = conf_base_dir

def load_config(config, config_file=None, config_dict=None, clear_existing=False):
    if clear_existing:
        for key in config.keys():
            del config[key] 
    
    if config_dict is None:
        with open(config_file) as f:
            config_dict = yaml.load(f)
    
    defaults = _to_options_map(config_dict)
    
    if defaults:
        for key, value in defaults.iteritems():
            if key in config and hasattr(config[key], 'update'):
                config[key].update(value)
            else:
                config[key] = value
