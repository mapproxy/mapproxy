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
ctypes utilities.
"""

import sys
import os

from ctypes import CDLL
from ctypes.util import find_library as _find_library


default_locations = dict(
    darwin=dict(
        paths = ['/opt/local/lib'],
        exts = ['.dylib'],
    ),
    win32=dict(
        paths = [os.path.dirname(os.__file__) + '/../../../DLLs'],
        exts = ['.dll']
    )
)

additional_lib_path = os.environ.get('MAPPROXY_LIB_PATH')
if additional_lib_path:
    additional_lib_path = additional_lib_path.split(os.pathsep)
    additional_lib_path.reverse()
    for locs in default_locations.values():
        for path in additional_lib_path:
            locs['paths'].insert(0, path)

def load_library(lib_names, locations_conf=default_locations):
    """
    Load the `lib_name` library with ctypes.
    If ctypes.util.find_library does not find the library,
    different path and filename extensions will be tried.
    
    Retruns the loaded library or None.
    """
    if isinstance(lib_names, basestring):
        lib_names = [lib_names]
    
    for lib_name in lib_names:
        lib = load_library_(lib_name, locations_conf)
        if lib is not None: return lib

def load_library_(lib_name, locations_conf=default_locations):
    lib_path = find_library(lib_name)
    
    if lib_path:
        return CDLL(lib_path)
    
    if sys.platform in locations_conf:
        paths = locations_conf[sys.platform]['paths']
        exts = locations_conf[sys.platform]['exts']
        lib_path = find_library(lib_name, paths, exts)
    
    if lib_path:
        return CDLL(lib_path)
        

def find_library(lib_name, paths=None, exts=None):
    """
    Search for library in all permutations of `paths` and `exts`.
    If nothing is found None is returned.
    """
    if not paths or not exts:
        lib = _find_library(lib_name)
        if lib is None and lib_name.startswith('lib'):
            lib = _find_library(lib_name[3:])
        return lib
    
    for lib_name in [lib_name] + ([lib_name[3:]] if lib_name.startswith('lib') else []):
        for path in paths:
            for ext in exts:
                lib_path = os.path.join(path, lib_name + ext)
                if os.path.exists(lib_path):
                    return lib_path
    
    return None

if __name__ == '__main__':
    print load_library(sys.argv[1])
