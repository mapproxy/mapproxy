# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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

# TODO LOG
# TODO Literal edge cases

from mapproxy.prefetcher.base import TilePrefetcherBase


class ExpanderPrefetcher(TilePrefetcherBase):
    """
    This class is responsible to prefetch based on incoming requests.
    """
    def __init__(self, prefetcher_values, tile_grid):
        super(ExpanderPrefetcher, self).__init__(tile_grid)
        self.expansion_amount = prefetcher_values.get('expansion_amount', '1')

    def prefetch_for_tile(self, tile):
        tiles_to_prefetch = []
        for x in range(tile[0] - self.expansion_amount, tile[0] + self.expansion_amount + 1):
            for y in range(tile[1] - self.expansion_amount, tile[1] + self.expansion_amount + 1):
                current_coord = (x, y, tile[2])
                if self._verify_proper_tile(current_coord):
                    tiles_to_prefetch.append(current_coord)
        return tiles_to_prefetch
