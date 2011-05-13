# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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
        if yaml.__with_libyaml__:
            return yaml.load(doc, Loader=yaml.CLoader)
        else:
            return yaml.load(doc)
    except (yaml.scanner.ScannerError, yaml.parser.ParserError), ex:
        raise YAMLError(str(ex))

