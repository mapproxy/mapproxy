from __future__ import division

from mapproxy.layer import merge_layer_res_ranges
from mapproxy.layer.map_layer import MapLayer
from mapproxy.srs import SupportedSRS


class SRSConditional(MapLayer):
    supports_meta_tiles = True

    def __init__(self, layers, extent, opacity=None, preferred_srs=None):
        MapLayer.__init__(self)
        self.srs_map = {}
        self.res_range = merge_layer_res_ranges([x[0] for x in layers])

        supported_srs = []
        for layer, srs in layers:
            supported_srs.append(srs)
            self.srs_map[srs] = layer
        self.supported_srs = SupportedSRS(supported_srs, preferred_srs)
        self.extent = extent
        self.opacity = opacity

    def get_map(self, query):
        self.check_res_range(query)
        layer = self._select_layer(query.srs)
        return layer.get_map(query)

    def _select_layer(self, query_srs):
        srs = self.supported_srs.best_srs(query_srs)
        return self.srs_map[srs]
