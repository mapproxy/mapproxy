from __future__ import division

from typing import Optional

from mapproxy.layer import BlankImage
from mapproxy.image.opts import ImageOptions
from mapproxy.util.coverage import Coverage


class MapLayer:
    supports_meta_tiles = False

    res_range = None

    coverage: Optional[Coverage] = None

    def __init__(self, image_opts=None):
        self.image_opts = image_opts or ImageOptions()

    def _get_opacity(self):
        return self.image_opts.opacity

    def _set_opacity(self, value):
        self.image_opts.opacity = value

    opacity = property(_get_opacity, _set_opacity)

    def is_opaque(self, query):
        """
        Whether the query result is opaque.

        This method is used for optimizations: layers below an opaque
        layer can be skipped. As sources with `transparent: false`
        still can return transparent images (min_res/max_res/coverages),
        implementations of this method need to be certain that the image
        is indeed opaque. is_opaque should return False if in doubt.
        """
        return False

    def check_res_range(self, query):
        if (self.res_range and
                not self.res_range.contains(query.bbox, query.size, query.srs)):
            raise BlankImage()

    def get_map(self, query):
        raise NotImplementedError

    def combined_layer(self, other, query):
        return None
