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

from __future__ import print_function

import os
import sys
import ctypes
from ctypes import c_void_p, c_char_p, c_int

from mapproxy.util.lib import load_library

def init_libgdal():
    libgdal = load_library(['libgdal', 'libgdal1', 'gdal110', 'gdal19', 'gdal18', 'gdal17'])

    if not libgdal: return

    libgdal.OGROpen.argtypes = [c_char_p, c_int, c_void_p]
    libgdal.OGROpen.restype = c_void_p

    # CPLGetLastErrorMsg is not part of the official and gets
    # name mangled on Windows builds. try to support _Foo@0
    # mangling, otherwise print no detailed errors
    if not hasattr(libgdal, 'CPLGetLastErrorMsg') and hasattr(libgdal, '_CPLGetLastErrorMsg@0'):
        libgdal.CPLGetLastErrorMsg = getattr(libgdal, '_CPLGetLastErrorMsg@0')

    if hasattr(libgdal, 'CPLGetLastErrorMsg'):
        libgdal.CPLGetLastErrorMsg.argtypes	= []
        libgdal.CPLGetLastErrorMsg.restype = c_char_p
    else:
        libgdal.CPLGetLastErrorMsg = None

    libgdal.OGR_DS_GetLayer.argtypes = [c_void_p, c_int]
    libgdal.OGR_DS_GetLayer.restype = c_void_p

    libgdal.OGR_FD_GetName.argtypes = [c_void_p]
    libgdal.OGR_FD_GetName.restype = c_char_p

    libgdal.OGR_L_GetLayerDefn.argtypes = [c_void_p]
    libgdal.OGR_L_GetLayerDefn.restype = c_void_p

    libgdal.OGR_DS_Destroy.argtypes = [c_void_p]

    libgdal.OGR_DS_ExecuteSQL.argtypes = [c_void_p, c_char_p, c_void_p, c_char_p]
    libgdal.OGR_DS_ExecuteSQL.restype = c_void_p
    libgdal.OGR_DS_ReleaseResultSet.argtypes = [c_void_p, c_void_p]

    libgdal.OGR_L_ResetReading.argtypes = [c_void_p]
    libgdal.OGR_L_GetNextFeature.argtypes = [c_void_p]
    libgdal.OGR_L_GetNextFeature.restype = c_void_p

    libgdal.OGR_F_Destroy.argtypes = [c_void_p]

    libgdal.OGR_F_GetGeometryRef.argtypes = [c_void_p]
    libgdal.OGR_F_GetGeometryRef.restype = c_void_p

    libgdal.OGR_G_ExportToWkt.argtypes = [c_void_p, ctypes.POINTER(c_char_p)]
    libgdal.OGR_G_ExportToWkt.restype = c_void_p

    libgdal.VSIFree.argtypes = [c_void_p]

    libgdal.OGRRegisterAll()

    return libgdal

class OGRShapeReaderError(Exception):
    pass

class CtypesOGRShapeReader(object):
    def __init__(self, datasource):
        self.datasource = datasource
        self._ds = None

    def open(self):
        if self._ds: return
        self._ds = libgdal.OGROpen(self.datasource.encode(sys.getdefaultencoding()), False, None)
        if self._ds is None:
            msg = None
            if libgdal.CPLGetLastErrorMsg:
                msg = libgdal.CPLGetLastErrorMsg()
            if not msg:
                msg = 'failed to open %s' % self.datasource
            raise OGRShapeReaderError(msg)

    def wkts(self, where=None):
        if not self._ds: self.open()

        if where:
            if not where.lower().startswith('select'):
                layer = libgdal.OGR_DS_GetLayer(self._ds, 0)
                layer_def = libgdal.OGR_L_GetLayerDefn(layer)
                name = libgdal.OGR_FD_GetName(layer_def)
                where = 'select * from %s where %s' % (name.decode('utf-8'), where)
            layer = libgdal.OGR_DS_ExecuteSQL(self._ds, where.encode('utf-8'), None, None)
        else:
            layer = libgdal.OGR_DS_GetLayer(self._ds, 0)
        if layer is None:
            msg = None
            if libgdal.CPLGetLastErrorMsg:
                msg = libgdal.CPLGetLastErrorMsg()
            raise OGRShapeReaderError(msg)

        libgdal.OGR_L_ResetReading(layer)
        while True:
            feature = libgdal.OGR_L_GetNextFeature(layer)
            if feature is None:
                break
            geom = libgdal.OGR_F_GetGeometryRef(feature)
            if geom is None:
                libgdal.OGR_F_Destroy(feature)
                continue
            res = c_char_p()
            libgdal.OGR_G_ExportToWkt(geom, ctypes.byref(res))
            yield res.value
            libgdal.VSIFree(res)
            libgdal.OGR_F_Destroy(feature)

        if where:
            libgdal.OGR_DS_ReleaseResultSet(self._ds, layer)

    def close(self):
        if self._ds:
            libgdal.OGR_DS_Destroy(self._ds)
            self._ds = None

    def __del__(self):
        self.close()


class OSGeoOGRShapeReader(object):
    def __init__(self, datasource):
        self.datasource = datasource
        self._ds = None

    def open(self):
        if self._ds: return
        self._ds = ogr.Open(self.datasource, False)
        if self._ds is None:
            msg = gdal.GetLastErrorMsg()
            if not msg:
                msg = 'failed to open %s' % self.datasource
            raise OGRShapeReaderError(msg)

    def wkts(self, where=None):
        if not self._ds: self.open()

        if where:
            if not where.lower().startswith('select'):
                layer = self._ds.GetLayerByIndex(0)
                name = layer.GetName()
                where = 'select * from %s where %s' % (name, where)
            layer = self._ds.ExecuteSQL(where)
        else:
            layer = self._ds.GetLayerByIndex(0)
        if layer is None:
            msg = gdal.GetLastErrorMsg()
            raise OGRShapeReaderError(msg)

        layer.ResetReading()
        while True:
            feature = layer.GetNextFeature()
            if feature is None:
                break
            geom = feature.geometry()
            yield geom.ExportToWkt()

    def close(self):
        if self._ds:
            self._ds = None


ogr = gdal = None
def try_osgeoogr_import():
    global ogr, gdal
    try:
        from osgeo import ogr; ogr
        from osgeo import gdal; gdal
    except ImportError:
        return
    return OSGeoOGRShapeReader

libgdal = None
def try_libogr_import():
    global libgdal
    libgdal = init_libgdal()
    if libgdal is not None:
        return CtypesOGRShapeReader

ogr_imports = []
if 'MAPPROXY_USE_OSGEOOGR' in os.environ:
    ogr_imports = [try_osgeoogr_import]

if 'MAPPROXY_USE_LIBOGR' in os.environ:
    ogr_imports = [try_libogr_import]

if not ogr_imports:
    if sys.platform == 'win32':
        # prefer osgeo.ogr on windows
        ogr_imports = [try_osgeoogr_import, try_libogr_import]
    else:
        ogr_imports = [try_libogr_import, try_osgeoogr_import]

for try_import in ogr_imports:
    res = try_import()
    if res:
        OGRShapeReader = res
        break
else:
    raise ImportError('could not find osgeo.ogr package or libgdal')


if __name__ == '__main__':
    import sys
    reader = OGRShapeReader(sys.argv[1])
    where = None
    if len(sys.argv) == 3:
        where = sys.argv[2]
    for wkt in reader.wkts(where):
        print(wkt)
