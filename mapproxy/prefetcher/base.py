# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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


class TilePrefetcherBase(object):
    """
    Base implementation of a tile prefetcher.
    """
    def __init__(self, tile_grid):
        self.tile_grid = tile_grid

    def prefetch_for_tile(self, tile):
        raise NotImplementedError()

    def prefetch_for_tiles(self, tiles):
        all_prefetched = set()
        for tile in tiles:
            # Get the requested tile
            all_prefetched.add(tile)
            # Get the related prefetches
            single_prefetch_set = self.prefetch_for_tile(tile)
            for prefetch_coord in single_prefetch_set:
                all_prefetched.add(prefetch_coord)
        return all_prefetched

    def _verify_proper_tile(self, coord):
        return self.tile_grid.limit_tile(coord) is not None
