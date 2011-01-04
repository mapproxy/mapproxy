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
Map/information sources for layers or tile cache.
"""

from mapproxy.layer import MapLayer, MapExtent, MapError, MapBBOXError, BlankImage
from mapproxy.image.message import message_image
from mapproxy.srs import SRS

class SourceError(MapError):
    pass

class SourceBBOXError(SourceError, MapBBOXError):
    pass

class InvalidSourceQuery(ValueError):
    pass

class Source(MapLayer):
    supports_meta_tiles = False
    transparent = False
    
    def __init__(self):
        MapLayer.__init__(self)

class InfoSource(object):
    def get_info(self, query):
        raise NotImplementedError

class LegendSource(object):
    def get_legend(self, query):
        raise NotImplementedError

class DebugSource(Source):
    def __init__(self):
        self.extent = MapExtent((-180, -90, 180, 90), SRS(4326))
        self.transparent = True
        self.res_range = None
    def get_map(self, query):
        bbox = query.bbox
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        res_x = w/query.size[0]
        res_y = h/query.size[1]
        debug_info = "bbox: %r\nres: %.8f(%.8f)" % (bbox, res_x, res_y)
        return message_image(debug_info, size=query.size, transparent=True)

class DummySource(Source):
    """
    Source that always returns a blank image.
    
    Used internally for 'offline' sources (e.g. seed_only).
    """
    def __init__(self):
        self.extent = MapExtent((-180, -90, 180, 90), SRS(4326))
        self.transparent = True
    def get_map(self, query):
        raise BlankImage()
