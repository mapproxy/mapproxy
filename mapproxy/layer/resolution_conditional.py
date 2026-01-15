from __future__ import division

import logging

from mapproxy.image import BaseImageResult
from mapproxy.layer import merge_layer_res_ranges
from mapproxy.layer.map_layer import MapLayer
from mapproxy.query import MapQuery

log = logging.getLogger(__name__)


class ResolutionConditional(MapLayer):
    supports_meta_tiles = True

    def __init__(self, one, two, resolution, srs, extent, opacity=None):
        super().__init__()
        self.one = one
        self.two = two
        self.res_range = merge_layer_res_ranges([one, two])
        self.resolution = resolution
        self.srs = srs

        self.opacity = opacity
        self.extent = extent

    def get_map(self, query: MapQuery) -> BaseImageResult:
        self.check_res_range(query)
        bbox = query.bbox
        if query.srs != self.srs:
            bbox = query.srs.transform_bbox_to(self.srs, bbox)

        xres = (bbox[2] - bbox[0]) / query.size[0]
        yres = (bbox[3] - bbox[1]) / query.size[1]
        res = min(xres, yres)
        log.debug('actual res: %s, threshold res: %s', res, self.resolution)

        if res > self.resolution:
            return self.one.get_map(query)
        else:
            return self.two.get_map(query)
