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
Map/information sources for layers or tile cache.
"""

from mapproxy.layer import MapLayer, MapExtent, MapError, MapBBOXError, BlankImage
from mapproxy.image.message import message_image
from mapproxy.image.opts import ImageOptions
from mapproxy.srs import SRS

class SourceError(MapError):
    pass

class SourceBBOXError(SourceError, MapBBOXError):
    pass

class InvalidSourceQuery(SourceError):
    pass

class Source(MapLayer):
    supports_meta_tiles = False
    
    def __init__(self, image_opts=None):
        MapLayer.__init__(self, image_opts=image_opts)

class InfoSource(object):
    def get_info(self, query):
        raise NotImplementedError

class LegendSource(object):
    def get_legend(self, query):
        raise NotImplementedError

class DebugSource(Source):
    def __init__(self):
        Source.__init__(self)
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
        return message_image(debug_info, size=query.size,
            image_opts=ImageOptions(transparent=True))

class DummySource(Source):
    """
    Source that always returns a blank image.
    
    Used internally for 'offline' sources (e.g. seed_only).
    """
    def __init__(self):
        Source.__init__(self)
        self.extent = MapExtent((-180, -90, 180, 90), SRS(4326))
        self.transparent = True
    def get_map(self, query):
        raise BlankImage()
