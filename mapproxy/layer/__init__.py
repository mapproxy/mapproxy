from __future__ import division

from functools import reduce
from typing import Protocol, Optional, Sequence

from mapproxy.grid.resolutions import merge_resolution_range, ResolutionRange


class BlankImageError(Exception):
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
        super().__init__(values)


class WithResRange(Protocol):
    @property
    def res_range(self) -> Optional[ResolutionRange]:
        pass


def merge_layer_res_ranges(layers: Sequence[WithResRange]) -> Optional[ResolutionRange]:
    ranges = [s.res_range for s in layers
              if hasattr(s, 'res_range')]

    if not ranges:
        return None

    return reduce(merge_resolution_range, ranges)
