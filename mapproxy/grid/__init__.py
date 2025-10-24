# This file is part of the MapProxy project.
# Copyright (C) 2025 terrestris GmbH & Co. KG <https://terrestris.de>
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
from mapproxy.srs import SRS
from mapproxy.util.bbox import bbox_tuple


class GridError(Exception):
    pass


class NoTiles(GridError):
    pass


def _create_tile_list(xs, ys, level, grid_size):
    """
    Returns an iterator tile_coords for the given tile ranges (`xs` and `ys`).
    If the one tile_coord is negative or out of the `grid_size` bound,
    the coord is None.
    """
    x_limit = grid_size[0]
    y_limit = grid_size[1]
    for y in ys:
        for x in xs:
            if x < 0 or y < 0 or x >= x_limit or y >= y_limit:
                yield None
            else:
                yield x, y, level


class _default_bboxs(object):
    _defaults: dict[int, tuple[float, float, float, float]] = {
        4326: (-180, -90, 180, 90),
    }
    for epsg_num in (900913, 3857, 102100, 102113):
        _defaults[epsg_num] = (-20037508.342789244,
                               -20037508.342789244,
                               20037508.342789244,
                               20037508.342789244)
    defaults = None

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __getitem__(self, key):
        if self.defaults is None:
            defaults = {}
            for epsg, bbox in self._defaults.items():
                defaults[SRS(epsg)] = bbox
            self.defaults = defaults
        return self.defaults[key]


default_bboxs = _default_bboxs()


def grid_bbox(bbox, bbox_srs, srs):
    bbox = bbox_tuple(bbox)
    if bbox_srs:
        bbox = SRS(bbox_srs).transform_bbox_to(srs, bbox)
    return bbox


ORIGIN_UL = 'ul'
ORIGIN_LL = 'll'


def origin_from_string(origin):
    if origin is None:
        origin = ORIGIN_LL
    elif origin.lower() in ('ll', 'sw'):
        origin = ORIGIN_LL
    elif origin.lower() in ('ul', 'nw'):
        origin = ORIGIN_UL
    else:
        raise ValueError("unknown origin value '%s'" % origin)
    return origin
