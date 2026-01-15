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

"""
Tile caching (creation, caching and retrieval of tiles).

.. digraph:: Schematic Call Graph

    ranksep = 0.1;
    node [shape="box", height="0", width="0"]

    cl  [label="CacheMapLayer" href="<mapproxy.core.layer.CacheMapLayer>"]
    tm  [label="TileManager",  href="<TileManager>"];
    fc      [label="FileCache", href="<FileCache>"];
    s       [label="Source", href="<mapproxy.core.source.Source>"];

    {
        cl -> tm [label="load_tile_coords"];
        tm -> fc [label="load\\nstore\\nis_cached"];
        tm -> s  [label="get_map"]
    }


"""
from typing import Optional

from mapproxy.image import BlankImageSource, BaseImageSource
from mapproxy.image.tile import TileSplitter
import logging

log = logging.getLogger('mapproxy.cache.tile')


class Tile:
    """
    Internal data object for all tiles. Stores the tile-``coord`` and the tile data.
    """

    def __init__(self, coord: tuple[int, int, int], source: Optional[BaseImageSource] = None, cacheable: bool = True):
        self.coord = coord
        self.source = source
        self.location = None
        self.stored = False
        self._cacheable = cacheable
        self.size: Optional[int] = None
        self.timestamp: Optional[float] = None

    def _cacheable_get(self):
        return CacheInfo(cacheable=self._cacheable, timestamp=self.timestamp,
                         size=self.size)

    def _cacheable_set(self, cacheable):
        if isinstance(cacheable, bool):
            self._cacheable = cacheable
        else:  # assume cacheable is CacheInfo
            self._cacheable = cacheable.cacheable
            self.timestamp = cacheable.timestamp
            self.size = cacheable.size

    cacheable = property(_cacheable_get, _cacheable_set)

    def source_buffer(self, *args, **kw):
        if self.source is not None:
            return self.source.as_buffer(*args, **kw)
        else:
            return None

    def source_image(self, *args, **kw):
        if self.source is not None:
            return self.source.as_image(*args, **kw)
        else:
            return None

    def is_missing(self) -> bool:
        """
        Returns ``True`` when the tile has no ``data``, except when the ``coord``
        is ``None``. It doesn't check if the tile exists.

        >>> Tile((1, 2, 3)).is_missing()
        True
        >>> Tile((1, 2, 3), './tmp/foo').is_missing()
        False
        >>> Tile(None).is_missing()
        False
        """
        if self.coord is None:
            return False
        return self.source is None

    def __eq__(self, other):
        """
        >>> Tile((0, 0, 1)) == Tile((0, 0, 1))
        True
        >>> Tile((0, 0, 1)) == Tile((1, 0, 1))
        False
        >>> Tile((0, 0, 1)) is None
        False
        """
        if isinstance(other, Tile):
            return (self.coord == other.coord and
                    self.source == other.source)
        else:
            return NotImplemented

    def __ne__(self, other):
        """
        >>> Tile((0, 0, 1)) != Tile((0, 0, 1))
        False
        >>> Tile((0, 0, 1)) != Tile((1, 0, 1))
        True
        >>> Tile((0, 0, 1)) != None
        True
        """
        equal_result = self.__eq__(other)
        if equal_result is NotImplemented:
            return NotImplemented
        else:
            return not equal_result

    def __repr__(self):
        return 'Tile(%r, source=%r)' % (self.coord, self.source)


class CacheInfo(object):
    def __init__(self, cacheable=True, timestamp=None, size=None):
        self.cacheable = cacheable
        self.timestamp = timestamp
        self.size = size

    def __bool__(self):
        return self.cacheable


class TileCollection(object):
    def __init__(self, tile_coords):
        self.tiles = [Tile(coord) for coord in tile_coords]
        self.tiles_dict = {}
        for tile in self.tiles:
            self.tiles_dict[tile.coord] = tile

    def __getitem__(self, idx_or_coord):
        if isinstance(idx_or_coord, int):
            return self.tiles[idx_or_coord]
        if idx_or_coord in self.tiles_dict:
            return self.tiles_dict[idx_or_coord]
        return Tile(idx_or_coord)

    def __contains__(self, tile_or_coord):
        if isinstance(tile_or_coord, tuple):
            return tile_or_coord in self.tiles_dict
        if hasattr(tile_or_coord, 'coord'):
            return tile_or_coord.coord in self.tiles_dict
        return False

    def __len__(self):
        return len(self.tiles)

    def __iter__(self):
        return iter(self.tiles)

    @property
    def empty(self):
        """
        Returns True if no tile in this collection contains a source.
        """
        return all((t.source is None for t in self.tiles))

    @property
    def blank(self):
        """
        Returns True if all sources collection are BlankImageSources or have not source at all.
        """
        return all((t.source is None or isinstance(t.source, BlankImageSource) for t in self.tiles))

    def __repr__(self):
        return 'TileCollection(%r)' % self.tiles


def split_meta_tiles(meta_tile, tiles, tile_size, image_opts):
    try:
        # TODO png8
        # if not self.transparent and format == 'png':
        #     format = 'png8'
        splitter = TileSplitter(meta_tile, image_opts)
    except IOError:
        # TODO
        raise
    split_tiles = []
    for tile in tiles:
        tile_coord, crop_coord = tile
        if tile_coord is None:
            continue
        data = splitter.get_tile(crop_coord, tile_size)
        new_tile = Tile(tile_coord, cacheable=meta_tile.cacheable)
        new_tile.source = data
        split_tiles.append(new_tile)
    return split_tiles
