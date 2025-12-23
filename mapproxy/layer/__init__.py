from __future__ import division

from functools import reduce

from mapproxy.grid.resolutions import merge_resolution_range


class BlankImage(Exception):
    pass


class MapError(Exception):
    pass


class MapBBOXError(Exception):
    pass


class InfoLayer:
    def get_info(self, query):
        raise NotImplementedError


class Dimension(list):
    def __init__(self, identifier, values, default=None):
        self.identifier = identifier
        if not default and values:
            default = values[0]
        self.default = default
        list.__init__(self, values)


def merge_layer_res_ranges(layers):
    ranges = [s.res_range for s in layers
              if hasattr(s, 'res_range')]

    if ranges:
        ranges = reduce(merge_resolution_range, ranges)

    return ranges
