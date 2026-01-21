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

import os
from typing import Optional

from mapproxy.image import BaseImageResult
from mapproxy.image import ImageResult
from mapproxy.image.transform import ImageTransformer
from mapproxy.image.opts import create_image

import logging

from mapproxy.srs import _SRS
from mapproxy.util.bbox import BBOX

log = logging.getLogger(__name__)


class TileMerger(object):
    """
    Merge multiple tiles into one image.
    """

    def __init__(self, tile_grid, tile_size):
        """
        :param tile_grid: the grid size
        :type tile_grid: ``(int(x_tiles), int(y_tiles))``
        :param tile_size: the size of each tile
        """
        self.tile_grid = tile_grid
        self.tile_size = tile_size

    def merge(self, ordered_tiles: list[BaseImageResult], image_opts) -> BaseImageResult:
        """
        Merge all tiles into one image.

        :param ordered_tiles: list of tiles, sorted row-wise (top to bottom)
        :rtype: `ImageResult`
        """
        if self.tile_grid == (1, 1):
            assert len(ordered_tiles) == 1
            if ordered_tiles[0] is not None:
                return ordered_tiles.pop()
        src_size = self._src_size()

        result = create_image(src_size, image_opts)

        cacheable = True

        for i, tile in enumerate(ordered_tiles):
            if tile is None:
                continue
            try:
                if not tile.cacheable:
                    cacheable = False
                image = tile.as_image()
                pos = self._tile_offset(i)
                image.draft(image_opts.mode, self.tile_size)
                result.paste(image, pos)
                tile.close_buffers()
            except IOError as e:
                if e.errno is None:  # PIL error
                    log.warning('unable to load tile %s, removing it (reason was: %s)'
                                % (tile, str(e)))
                    filename = getattr(tile, 'filename')
                    if filename:
                        if os.path.exists(filename):
                            os.remove(filename)
                else:
                    raise
        return ImageResult(result, size=src_size, image_opts=image_opts, cacheable=cacheable)

    def _src_size(self):
        width = self.tile_grid[0]*self.tile_size[0]
        height = self.tile_grid[1]*self.tile_size[1]
        return width, height

    def _tile_offset(self, i):
        """
        Return the image offset (upper-left coord) of the i-th tile,
        where the tiles are ordered row-wise, top to bottom.
        """
        return (i % self.tile_grid[0]*self.tile_size[0],
                i//self.tile_grid[0]*self.tile_size[1])


class TileSplitter:
    """
    Splits a large image into multiple tiles.
    """

    def __init__(self, meta_tile, image_opts):
        self.meta_img = meta_tile.as_image()
        self.image_opts = image_opts

    def get_tile(self, crop_coord: tuple[int, int], tile_size: tuple[int, int]) -> ImageResult:
        """
        Return the cropped tile.
        :param crop_coord: the upper left pixel coord to start
        :param tile_size: width and height of the new tile
        :rtype: `ImageResult`
        """
        minx, miny = crop_coord
        maxx = minx + tile_size[0]
        maxy = miny + tile_size[1]

        if (minx < 0 or miny < 0 or maxx > self.meta_img.size[0]
                or maxy > self.meta_img.size[1]):

            crop = self.meta_img.crop((
                max(minx, 0),
                max(miny, 0),
                min(maxx, self.meta_img.size[0]),
                min(maxy, self.meta_img.size[1])))
            result = create_image(tile_size, self.image_opts)
            result.paste(crop, (abs(min(minx, 0)), abs(min(miny, 0))))
            crop = result
        else:
            crop = self.meta_img.crop((minx, miny, maxx, maxy))
        return ImageResult(crop, size=tile_size, image_opts=self.image_opts)


class TiledImage:
    """
    An image built-up from multiple tiles.
    """

    def __init__(self, tiles: list[Optional[BaseImageResult]], tile_grid_size: tuple[int, int],
                 tile_size: tuple[int, int], src_bbox: BBOX, src_srs: _SRS):
        """
        :param tiles: all tiles (sorted row-wise, top to bottom)
        :param tile_grid_size: the tile grid size
        :type tile_grid_size: ``(int(x_tiles), int(y_tiles))``
        :param tile_size: the size of each tile
        :param src_bbox: the bbox of all tiles
        :param src_srs: the srs of the bbox
        """
        self.tiles = tiles
        self.tile_grid = tile_grid_size
        self.tile_size = tile_size
        self.src_bbox = src_bbox
        self.src_srs = src_srs

    def image(self, image_opts):
        """
        Return the tiles as one merged image.

        :rtype: `ImageResult`
        """
        tm = TileMerger(self.tile_grid, self.tile_size)
        return tm.merge(self.tiles, image_opts=image_opts)

    def transform(self, req_bbox, req_srs, out_size, image_opts):
        """
        Return the the tiles as one merged and transformed image.

        :param req_bbox: the bbox of the output image
        :param req_srs: the srs of the req_bbox
        :param out_size: the size in pixel of the output image
        :rtype: `ImageResult`
        """
        transformer = ImageTransformer(self.src_srs, req_srs)
        src_img = self.image(image_opts)
        return transformer.transform(src_img, self.src_bbox, out_size, req_bbox,
                                     image_opts)
