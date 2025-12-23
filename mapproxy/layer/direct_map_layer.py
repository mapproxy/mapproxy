from __future__ import division

from mapproxy.image import BaseImageSource
from mapproxy.layer.map_layer import MapLayer
from mapproxy.query import MapQuery
from mapproxy.source.wms import WMSSource


class DirectMapLayer(MapLayer):
    supports_meta_tiles = True

    def __init__(self, source: WMSSource, extent):
        super().__init__()
        self.source = source
        self.res_range = getattr(source, 'res_range', None)
        self.extent = extent

    def get_map(self, query: MapQuery) -> BaseImageSource:
        self.check_res_range(query)
        return self.source.get_map(query)
