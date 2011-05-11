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

from __future__ import absolute_import

import sys
from cStringIO import StringIO

from mapproxy.grid import tile_grid
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.layer import MapExtent, DefaultMapExtent, BlankImage
from mapproxy.source import Source, SourceError
from mapproxy.client.http import HTTPClientError
from mapproxy.util import reraise_exception

try:
    import mapnik
    mapnik
except ImportError:
    mapnik = None

import logging
log = logging.getLogger(__name__)

class MapnikSource(Source):
    supports_meta_tiles = True
    def __init__(self, mapfile, image_opts=None, coverage=None, res_range=None, lock=None):
        Source.__init__(self, image_opts=image_opts)
        self.mapfile = mapfile
        self.coverage = coverage
        self.res_range = res_range
        self.lock = lock
        if self.coverage:
            self.extent = MapExtent(self.coverage.bbox, self.coverage.srs)
        else:
            self.extent = DefaultMapExtent()
    
    def get_map(self, query):
        if self.res_range and not self.res_range.contains(query.bbox, query.size,
                                                          query.srs):
            raise BlankImage()
        if self.coverage and not self.coverage.intersects(query.bbox, query.srs):
            raise BlankImage()
        
        try:
            try:
                resp = self.render(query)
            except RuntimeError, ex:
                raise SourceError(ex.args[0])
            resp.opacity = self.opacity
            return resp
            
        except HTTPClientError, e:
            reraise_exception(SourceError(e.args[0]), sys.exc_info())
    
    def render(self, query):
        mapfile = self.mapfile
        if '%(webmercator_level)' in mapfile:
            _bbox, level = tile_grid(3857).get_affected_bbox_and_level(
                query.bbox, query.size, req_srs=query.srs)
            mapfile = mapfile % {'webmercator_level': level}
        
        if self.lock:
            with self.lock():
                return self.render_mapfile(mapfile, query)
        else:
            return self.render_mapfile(mapfile, query)
    
    def render_mapfile(self, mapfile, query):
        m = mapnik.Map(query.size[0], query.size[1])
        mapnik.load_map(m, str(mapfile))
        m.srs = '+init=%s' % str(query.srs.srs_code.lower())
        envelope = mapnik.Envelope(*query.bbox)
        m.zoom_to_box(envelope)
        img = mapnik.Image(query.size[0], query.size[1])
        mapnik.render(m, img)
        data = StringIO(img.tostring(str(query.format)))
        return ImageSource(data, size=query.size, 
            image_opts=ImageOptions(transparent=self.transparent, format=query.format))
