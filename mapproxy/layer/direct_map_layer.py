from __future__ import division

from mapproxy.layer.map_layer import MapLayer
from mapproxy.source.wms import WMSSource


class DirectMapLayer(MapLayer):
    supports_meta_tiles = True

    def __init__(self, source: WMSSource, extent):
        MapLayer.__init__(self)
        self.source = source
        self.res_range = getattr(source, 'res_range', None)
        self.extent = extent

    def get_map(self, query):
        self.check_res_range(query)
        return self.source.get_map(query)
