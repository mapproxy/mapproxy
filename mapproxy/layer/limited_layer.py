from __future__ import division

from mapproxy.util.coverage import Coverage
from mapproxy.layer.map_layer import MapLayer


class LimitedLayer:
    """
    Wraps an existing layer temporary and stores additional
    attributes for geographical limits.
    """

    def __init__(self, layer: MapLayer, coverage: Coverage):
        self._layer = layer
        self.coverage = coverage

    def __getattr__(self, name):
        return getattr(self._layer, name)

    def combined_layer(self, other, query):
        if self.coverage == other.coverage:
            combined = self._layer.combined_layer(other, query)
            if combined:
                return LimitedLayer(combined, self.coverage)
        return None

    def get_info(self, query):
        if self.coverage:
            if not self.coverage.contains(query.coord, query.srs):
                return None
        return self._layer.get_info(query)
