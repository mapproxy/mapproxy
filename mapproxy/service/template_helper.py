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

from cgi import escape
from mapproxy.template import bunch

__all__ = ['escape', 'indent', 'bunch', 'wms100format', 'wms100info_format', 'limit_llbbox']

def indent(text, n=2):
  return '\n'.join(' '*n + line for line in text.split('\n'))

def wms100format(format):
    """
    >>> wms100format('image/png')
    'PNG'
    >>> wms100format('image/GeoTIFF')
    """
    _mime_class, sub_type = format.split('/')
    sub_type = sub_type.upper()
    if sub_type in ['PNG', 'TIFF', 'GIF', 'JPEG']:
        return sub_type
    else:
        return None

def wms100info_format(format):
    """
    >>> wms100info_format('text/html')
    'MIME'
    >>> wms100info_format('application/vnd.ogc.gml')
    'GML.1'
    """
    if format in ('application/vnd.ogc.gml', 'text/xml'):
        return 'GML.1'
    return 'MIME'

def limit_llbbox(bbox):
    """
    Limit the long/lat bounding box to +-180/89.99999999 degrees.
    
    Some clients can't handle +-90 north/south, so we subtract a tiny bit.
    
    >>> ', '.join('%.6f' % x for x in limit_llbbox((-200,-90.0, 180, 90)))
    '-180.000000, -89.999999, 180.000000, 89.999999'
    >>> ', '.join('%.6f' % x for x in limit_llbbox((-20,-9.0, 10, 10)))
    '-20.000000, -9.000000, 10.000000, 10.000000'
    """
    minx, miny, maxx, maxy = bbox
    
    minx = max(-180, minx)
    miny = max(-89.999999, miny)
    maxx = min(180, maxx)
    maxy = min(89.999999, maxy)
    
    return minx, miny, maxx, maxy