# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

from __future__ import absolute_import
import os
import re
import warnings

import yaml
ENV_PATTERN = re.compile(r"\$(\w+)|\$\{([^}]+)\}")

# Tracks variable names for which a warning has already been issued (once per name).
_warned_env_vars: set = set()


class YAMLError(Exception):
    pass



def load_yaml_file(file_or_filename):
    """
    Load yaml from file object or filename.
    """
    if isinstance(file_or_filename, str):
        with open(file_or_filename, 'rb') as f:
            return load_yaml(f)
    return load_yaml(file_or_filename)


def _load_yaml(doc):
    # try different methods to load yaml
    try:
        if getattr(yaml, '__with_libyaml__', False):
            try:
                return yaml.load(doc, Loader=yaml.CSafeLoader)
            except AttributeError:
                # handle cases where __with_libyaml__ is True but
                # CLoader doesn't work (missing .dispose())
                return yaml.safe_load(doc)
        return yaml.safe_load(doc)
    except (yaml.scanner.ScannerError, yaml.parser.ParserError) as ex:
        raise YAMLError(str(ex))


def load_yaml(doc):
    """
    Load yaml from file object or string.
    """
    data = expand_env(_load_yaml(doc))
    if type(data) is not dict:
        raise YAMLError("configuration not a YAML dictionary")
    return data


# functions for using env-names in variables
def replace_env_vars(value):
    """Replaces $VAR and ${VAR} in a string.
    If the environment variable is not set, the original placeholder is kept
    as a fallback value and a :class:`UserWarning` is issued once per
    unknown variable name.
    """
    def repl(match):
        var_name = match.group(1) or match.group(2)
        if var_name in os.environ:
            return os.environ[var_name]
        fallback = match.group(0)
        if var_name not in _warned_env_vars:
            _warned_env_vars.add(var_name)
            warnings.warn(
                f"Environment variable '{var_name}' is not set. "
                f"Using fallback value: '{fallback}'",
                UserWarning,
                stacklevel=2,
            )
        return fallback

    return ENV_PATTERN.sub(repl, value)


def expand_env(obj):
    """Recursively traverse a nested Python object."""
    if isinstance(obj, dict):
        return {k: expand_env(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [expand_env(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(expand_env(v) for v in obj)
    elif isinstance(obj, str):
        return replace_env_vars(obj)
    else:
        return obj
