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
ctypes based replacement of pyroj (with pyproj fallback).

This module implements the `Proj`, `transform` and `set_datapath` class/functions. This
module is a drop-in replacement for pyproj. It does implement just enough to work for
MapProxy, i.e. there is no numpy support, etc.

It uses the C libproj library. If the library could not be found/loaded it will fallback
to pyroj. You can force the usage of either backend by setting the environment variables
MAPPROXY_USE_LIBPROJ or MAPPROXY_USE_PYPROJ to any value.

"""
from __future__ import print_function

import os
import sys
from mapproxy.util.lib import load_library

import ctypes
from ctypes import (
   c_void_p,
   c_char_p,
   c_int,
   c_double,
   c_long,
   POINTER,
   create_string_buffer,
   addressof,
)

c_double_p = POINTER(c_double)
FINDERCMD = ctypes.CFUNCTYPE(c_char_p, c_char_p)

import logging
log_system = logging.getLogger('mapproxy.system')

__all__ = ['Proj', 'transform', 'set_datapath', 'ProjError']


def init_libproj():
    libproj = load_library('libproj')

    if libproj is None: return

    libproj.pj_init_plus.argtypes = [c_char_p]
    libproj.pj_init_plus.restype = c_void_p

    libproj.pj_is_latlong.argtypes = [c_void_p]
    libproj.pj_is_latlong.restype = c_int


    libproj.pj_get_def.argtypes = [c_void_p, c_int]
    libproj.pj_get_def.restype = c_void_p

    libproj.pj_strerrno.argtypes = [c_int]
    libproj.pj_strerrno.restype = c_char_p

    libproj.pj_get_errno_ref.argtypes = []
    libproj.pj_get_errno_ref.restype = POINTER(c_int)

    # free proj objects
    libproj.pj_free.argtypes = [c_void_p]
    # free() wrapper
    libproj.pj_dalloc.argtypes = [c_void_p]

    libproj.pj_transform.argtypes = [c_void_p, c_void_p, c_long, c_int,
                                     c_double_p, c_double_p, c_double_p]
    libproj.pj_transform.restype = c_int

    if hasattr(libproj, 'pj_set_searchpath'):
        libproj.pj_set_searchpath.argtypes = [c_int, POINTER(c_char_p)]
        libproj.pj_set_finder.argtypes = [FINDERCMD]

    return libproj

class SearchPath(object):
    def __init__(self):
        self.path = None
        self.finder_results = {}

    def clear(self):
        self.path = None
        self.finder_results = {}

    def set_searchpath(self, path):
        self.clear()
        if path is not None:
            path = path.encode(sys.getfilesystemencoding() or 'utf-8')
        self.path = path

    def finder(self, name):
        if self.path is None:
            return None

        if name in self.finder_results:
            result = self.finder_results[name]
        else:
            sysname = os.path.join(self.path, name)
            result = self.finder_results[name] = create_string_buffer(sysname)

        return addressof(result)

# search_path and finder_func must be defined in module
# context to avoid garbage collection
search_path = SearchPath()
finder_func = FINDERCMD(search_path.finder)
_finder_callback_set = False

class ProjError(RuntimeError):
    pass

class ProjInitError(ProjError):
    pass

def try_pyproj_import():
    try:
        from pyproj import Proj, transform, set_datapath
    except ImportError:
        return False
    log_system.info('using pyproj for coordinate transformation')
    return Proj, transform, set_datapath

def try_libproj_import():
    libproj = init_libproj()

    if libproj is None:
        return False

    log_system.info('using libproj for coordinate transformation')

    RAD_TO_DEG = 57.29577951308232
    DEG_TO_RAD = .0174532925199432958

    class Proj(object):
        def __init__(self, proj_def=None, init=None):
            if init:
                self._proj = libproj.pj_init_plus(b'+init=' + init.encode('ascii'))
            else:
                self._proj = libproj.pj_init_plus(proj_def.encode('ascii'))
            if not self._proj:
                errno = libproj.pj_get_errno_ref().contents
                raise ProjInitError('error initializing Proj(proj_def=%r, init=%r): %s' %
                    (proj_def, init, libproj.pj_strerrno(errno)))

            self.srs = self._srs()
            self._latlong = bool(libproj.pj_is_latlong(self._proj))

        def is_latlong(self):
            """
            >>> Proj(init='epsg:4326').is_latlong()
            True
            >>> Proj(init='epsg:4258').is_latlong()
            True
            >>> Proj(init='epsg:31467').is_latlong()
            False
            >>> Proj('+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 '
            ...      '+lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m '
            ...      '+nadgrids=@null +no_defs').is_latlong()
            False
            """
            return self._latlong

        def _srs(self):
            res = libproj.pj_get_def(self._proj, 0)
            srs_def = ctypes.c_char_p(res).value
            libproj.pj_dalloc(res)
            return srs_def

        def __del__(self):
            if self._proj and libproj:
                libproj.pj_free(self._proj)
                self._proj = None

    def transform(from_srs, to_srs, x, y, z=None):
        if from_srs == to_srs:
            return (x, y) if z is None else (x, y, z)

        if isinstance(x, (float, int)):
            x = [x]
            y = [y]
        assert len(x) == len(y)

        if from_srs.is_latlong():
            x = [x*DEG_TO_RAD for x in x]
            y = [y*DEG_TO_RAD for y in y]

        x = (c_double * len(x))(*x)
        y = (c_double * len(y))(*y)
        if z is not None:
            z = (c_double * len(z))(*z)
        else:
            # use explicit null pointer instead of None
            # http://bugs.python.org/issue4606
            z = c_double_p()

        res = libproj.pj_transform(from_srs._proj, to_srs._proj,
                                   len(x), 0, x, y, z)

        if res:
            raise ProjError(libproj.pj_strerrno(res))

        if to_srs.is_latlong():
            x = [x*RAD_TO_DEG for x in x]
            y = [y*RAD_TO_DEG for y in y]
        else:
            x = x[:]
            y = y[:]

        if len(x) == 1:
            x = x[0]
            y = y[0]
            z = z[0] if z else None

        return (x, y) if z is None else (x, y, z)

    def set_datapath(path):
        global _finder_callback_set
        if not _finder_callback_set:
            libproj.pj_set_finder(finder_func)
            _finder_callback_set = True
        search_path.set_searchpath(path)

    return Proj, transform, set_datapath


proj_imports = []

if 'MAPPROXY_USE_LIBPROJ' in os.environ:
    proj_imports = [try_libproj_import]

if 'MAPPROXY_USE_PYPROJ' in os.environ:
    proj_imports = [try_pyproj_import]

if not proj_imports:
    if sys.platform == 'win32':
        # prefer pyproj on windows
        proj_imports = [try_pyproj_import, try_libproj_import]
    else:
        proj_imports = [try_libproj_import, try_pyproj_import]

for try_import in proj_imports:
    res = try_import()
    if res:
        Proj, transform, set_datapath = res
        break
else:
    raise ImportError('could not find libproj or pyproj')

if __name__ == '__main__':

    prj1 = Proj(init='epsg:4326')
    prj2 = Proj(init='epsg:31467')

    coords = [(8.2, 8.22, 8.3), (53.1, 53.15, 53.2)]
    # coords = [(8, 9, 10), (50, 50, 50)]
    print(coords)
    coords = transform(prj1, prj2, *coords)
    print(coords)
    coords = transform(prj2, prj1, *coords)
    print(coords)
