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

import os
from mapproxy.util.lib import load_library

import mapproxy.platform

if mapproxy.platform.is_cpython:
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

__all__ = ['Proj', 'transform', 'set_datapath']


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

class ProjError(RuntimeError):
    pass

class ProjInitError(ProjError):
    pass


_use_libproj = _use_pyproj = False
if 'MAPPROXY_USE_LIBPROJ' in os.environ:
    _use_libproj = True

if 'MAPPROXY_USE_PYPROJ' in os.environ:
    _use_pyproj = True

if not _use_libproj and not _use_pyproj:
    _use_libproj = True # Default
    _use_pyproj = True # Fallback

libproj = None

if _use_libproj:
    libproj = init_libproj()

if libproj is None:
    if _use_pyproj:
        try:
            from pyproj import Proj, transform, set_datapath
            Proj, transform, set_datapath #prevent pyflakes arnings
            log_system.info('using pyproj for coordinate transformation')
        except ImportError:
            if _use_libproj:
                raise ImportError('could not found either libproj or pyproj')
            else:
                raise ImportError('could not found pyproj')
            
    else:
        raise ImportError('could not found libproj')
else:
    log_system.info('using libproj for coordinate transformation')

    # search_path and finder_func must be defined in module
    # context to avoid garbage collection
    search_path = SearchPath()
    finder_func = FINDERCMD(search_path.finder)
    _finder_callback_set = False

    RAD_TO_DEG = 57.29577951308232
    DEG_TO_RAD = .0174532925199432958

    class Proj(object):
        def __init__(self, proj_def=None, init=None):
            if init:
                self._proj = libproj.pj_init_plus('+init=%s' % init)
            else:
                self._proj = libproj.pj_init_plus(proj_def)
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
            x = map(lambda x: x*DEG_TO_RAD, x)
            y = map(lambda y: y*DEG_TO_RAD, y)
    
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
            x = map(lambda x: x*RAD_TO_DEG, x)
            y = map(lambda y: y*RAD_TO_DEG, y)
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

if __name__ == '__main__':
    
    prj1 = Proj(init='epsg:4326')
    prj2 = Proj(init='epsg:31467')
    
    coords = [(8.2, 8.22, 8.3), (53.1, 53.15, 53.2)]
    # coords = [(8, 9, 10), (50, 50, 50)]
    print coords
    coords = transform(prj1, prj2, *coords)
    print coords
    coords = transform(prj2, prj1, *coords)
    print coords
