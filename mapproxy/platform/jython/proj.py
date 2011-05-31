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

import mapproxy.platform

if mapproxy.platform.is_jython:
    from org.geotools.referencing import CRS
    from jarray import zeros

RAD_TO_DEG = 57.29577951308232
DEG_TO_RAD = .0174532925199432958

class ProjError(RuntimeError):
        pass

class ProjInitError(ProjError):
        pass

class Proj(object):
    
    def __init__(self, proj_def=None, init=None):
        if isinstance(init,basestring):
            self._crs = CRS.decode(init, True)
            self._srs_def = init
        elif isinstance(proj_def, basestring):
            self._crs = CRS.parseWKT(proj_def)
            self._srs_def = proj_def
        else:
            raise ProjInitError('error initializing Proj(proj_def=%r, init=%r)'
                                % (proj_def, init))
            
    def is_latlong(self):
        axis1 = str(self._crs.getCoordinateSystem().getAxis(0)).lower()
        return 'latitude' in axis1 or 'longitude' in axis1
    
    @property
    def _proj(self):
        #return str(CRS.lookupIdentifier(self._crs, True))
        return self._crs
    
    @property
    def srs(self):
        return self._srs_def
    
    def __del__(self):
        return
    
def transform(from_srs, to_srs, x, y, z=None):
    if from_srs == to_srs:
        return (x, y) if z is None else(x, y, z)

    if isinstance(x, (float, int)):
        x = [x]
        y = [y]
    assert len(x) == len(y)
    
    math_trans = CRS.findMathTransform(from_srs._proj, to_srs._proj)    
    coord_pairs = []
    
    for i in range(len(x)):
        coord_pairs.append(x[i])
        coord_pairs.append(y[i])
    len_pairs = len(coord_pairs)
    transformed_coord_pairs = zeros(len_pairs, 'd')
    math_trans.transform(coord_pairs,0,transformed_coord_pairs,0,len_pairs/2)
    
    x = []
    y = []
    for i in range(0,len(transformed_coord_pairs)-1,2):
        x.append(transformed_coord_pairs[i])
        y.append(transformed_coord_pairs[i+1])

    if len(x) == 1:
            x = x[0]
            y = y[0]
            z = z[0] if z else None
            
    return (x, y) if z is None else (x, y, z)
    
def set_datapath(path):
    return