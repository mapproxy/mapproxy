# -:- encoding: utf-8 -:-
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
Layer classes (direct, cached, etc.).

.. classtree:: mapproxy.core.layer.Layer

"""
from mapproxy.core.srs import SRS
from mapproxy.core.utils import cached_property

import logging
log = logging.getLogger(__name__)

class LayerMetaData(dict):
    """
    Dict-like object for layer metadata. Allows property-style access.
    
    >>> md = LayerMetaData({'name':'foo'})
    >>> md.name
    'foo'
    >>> md.invalid
    Traceback (most recent call last):
    ...
    AttributeError
    """
    def __init__(self, md):
        dict.__init__(self, md)
    def __getattr__(self, name):
        try:
            return dict.__getitem__(self, name)
        except KeyError:
            raise AttributeError
        

class Layer(object):
    """
    Base class for all renderable layers.
    """
    def render(self, request):
        """
        Render the response for the given `request`.
        :param request: the map request
        :return: one or more `ImageSource` with the rendered result
        :rtype: `ImageSource` or iterable with  multiple `ImageSource`
        """
        raise NotImplementedError()
    
    @cached_property
    def bbox(self):
        bbox = self._bbox()
        if bbox is None:
            bbox = (-180, -90, 180, 90)
            if self.srs != SRS(4326):
                bbox = SRS(4326).transform_bbox_to(self.srs, bbox)
        return bbox
    
    @cached_property
    def llbbox(self):
        """
        The LatLonBoundingBox in EPSG:4326
        """
        bbox = self.bbox
        if self.srs != SRS(4326):
            bbox = self.srs.transform_bbox_to(SRS(4326), bbox)
        return bbox
        
    def _bbox(self):
        return None    
    
    @cached_property
    def srs(self):
        srs = self._srs()
        if srs is None:
            srs = SRS(4326)
        return srs
    
    def _srs(self):
        return None
    