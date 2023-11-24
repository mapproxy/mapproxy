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

from mapproxy.template import bunch
from mapproxy.compat.modules import escape

__all__ = ['escape', 'indent', 'bunch', 'wms100format', 'wms100info_format',
    'wms111metadatatype']

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

def wms111metadatatype(type):
    if type == 'ISO19115:2003':
        return 'TC211'
    if type == 'FGDC:1998':
        return 'FGDC'
