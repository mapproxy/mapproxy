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
Retrieve maps/information from WMS servers.
"""
import sys
from mapproxy.request.base import split_mime_type
from mapproxy.cache.legend import Legend, legend_identifier
from mapproxy.image import concat_legends
from mapproxy.layer import MapExtent, DefaultMapExtent, BlankImage, LegendQuery
from mapproxy.source import Source, InfoSource, SourceError, LegendSource
from mapproxy.srs import SRS
from mapproxy.client.http import HTTPClientError
from mapproxy.util import reraise_exception

import logging
log = logging.getLogger(__name__)

class WMSSource(Source):
    supports_meta_tiles = True
    def __init__(self, client, transparent=False, coverage=None, res_range=None):
        Source.__init__(self)
        self.client = client
        self.transparent = transparent
        self.coverage = coverage
        self.res_range = res_range
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
            return self.client.get_map(query)
        except HTTPClientError, e:
            reraise_exception(SourceError(e.args[0]), sys.exc_info())
        

class WMSInfoSource(InfoSource):
    def __init__(self, client):
        self.client = client
    
    def get_info(self, query):
        return self.client.get_info(query).read()
        
class WMSLegendSource(LegendSource):
    def __init__(self, clients, legend_cache):
        self.clients = clients
        self.identifier = legend_identifier(
            [(c.request_template.url, c.request_template.params.layer)
             for c in self.clients])
        self._cache = legend_cache
        self._size = None
    
    @property
    def size(self):
        if not self._size:
            legend = self.get_legend(LegendQuery(format='image/png', scale=None))
            # TODO image size without as_image?
            self._size = legend.as_image().size
        return self._size
    
    def get_legend(self, query):
        legend = Legend(id=self.identifier, scale=query.scale)
        if not self._cache.load(legend):
            legends = []
            error_occured = False
            for client in self.clients:
                try:
                    legends.append(client.get_legend(query))
                except HTTPClientError, e:
                    error_occured = True
                    log.error(e.args[0])
                except SourceError, e:
                    error_occured = True
                    # TODO errors?
                    log.error(e.args[0])
            format = split_mime_type(query.format)[1]
            legend = Legend(source=concat_legends(legends, format=format),
                            id=self.identifier, scale=query.scale)
            if not error_occured:
                self._cache.store(legend)
        return legend.source
    
