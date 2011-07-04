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

from __future__ import with_statement, absolute_import
import yaml


class YAMLError(Exception):
    pass

def load_yaml_file(file_or_filename):
    """
    Load yaml from file object or filename.
    """
    if isinstance(file_or_filename, basestring):
        with open(file_or_filename) as f:
            return load_yaml(f)
    return load_yaml(file_or_filename)

def load_yaml(doc):
    """
    Load yaml from file object or string.
    """
    try:
        if getattr(yaml, '__with_libyaml__', False):
            return yaml.load(doc, Loader=yaml.CLoader)
        else:
            return yaml.load(doc)
    except (yaml.scanner.ScannerError, yaml.parser.ParserError), ex:
        raise YAMLError(str(ex))

