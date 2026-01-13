from __future__ import division

from mapproxy.image import BaseImageSource
from mapproxy.extent import MapExtent
from mapproxy.layer import merge_layer_res_ranges
from mapproxy.layer.map_layer import MapLayer
from mapproxy.srs import SupportedSRS, _SRS
from mapproxy.query import MapQuery


class SRSConditional(MapLayer):
    supports_meta_tiles = True

    def __init__(self, layers: list[tuple[MapLayer, _SRS]], extent: MapExtent, opacity=None, preferred_srs=None):
        super().__init__()
        self.srs_map: dict[_SRS, MapLayer] = {}
        self.res_range = merge_layer_res_ranges([x[0] for x in layers])

        supported_srs = []
        for layer, srs in layers:
            supported_srs.append(srs)
            self.srs_map[srs] = layer
        self.supported_srs = SupportedSRS(supported_srs, preferred_srs)
        self.extent = extent
        self.opacity = opacity

    def get_map(self, query: MapQuery) -> BaseImageSource:
        self.check_res_range(query)
        layer = self._select_layer(query.srs)
        return layer.get_map(query)

    def _select_layer(self, query_srs: _SRS) -> MapLayer:
        srs = self.supported_srs.best_srs(query_srs)
        return self.srs_map[srs]
