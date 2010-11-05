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
from mapproxy.image import concat_legends
from mapproxy.layer import MapExtent, BlankImage
from mapproxy.source import Source, InfoSource, SourceError, LegendSource
from mapproxy.srs import SRS
from mapproxy.client.http import HTTPClientError
from mapproxy.util import reraise_exception

import logging
log = logging.getLogger(__name__)

class WMSSource(Source):
    supports_meta_tiles = True
    def __init__(self, client, transparent=False, coverage=None):
        Source.__init__(self)
        self.client = client
        self.transparent = transparent
        self.coverage = coverage
        if self.coverage:
            self.extent = MapExtent(self.coverage.bbox, self.coverage.srs)
        else:
            #TODO extent
            self.extent = MapExtent((-180, -90, 180, 90), SRS(4326))
    
    def get_map(self, query):
        if self.coverage and not self.coverage.intersects(query.bbox, query.srs):
            raise BlankImage
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
    def __init__(self, clients):
        self.clients = clients
    def get_legend(self, query):
        legends = []
        for client in self.clients:
            try:
                legends.append(client.get_legend(query))
            except SourceError, e:
                log.error(SourceError(e.args[0]))
        source = concat_legends(legends)
        return source.as_buffer(format=query.format).read()
