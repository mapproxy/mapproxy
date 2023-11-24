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
from mapproxy.image import ImageSource
from mapproxy.image.transform import ImageTransformer
from mapproxy.image.opts import create_image

import logging
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

    def merge(self, ordered_tiles, image_opts):
        """
        Merge all tiles into one image.

        :param ordered_tiles: list of tiles, sorted row-wise (top to bottom)
        :rtype: `ImageSource`
        """
        if self.tile_grid == (1, 1):
            assert len(ordered_tiles) == 1
            if ordered_tiles[0] is not None:
                tile = ordered_tiles.pop()
                return tile
        src_size = self._src_size()

        result = create_image(src_size, image_opts)

        cacheable = True

        for i, source in enumerate(ordered_tiles):
            if source is None:
                continue
            try:
                if not source.cacheable:
                    cacheable = False
                tile = source.as_image()
                pos = self._tile_offset(i)
                tile.draft(image_opts.mode, self.tile_size)
                result.paste(tile, pos)
                source.close_buffers()
            except IOError as e:
                if e.errno is None: # PIL error
                    log.warning('unable to load tile %s, removing it (reason was: %s)'
                             % (source, str(e)))
                    if getattr(source, 'filename'):
                        if os.path.exists(source.filename):
                            os.remove(source.filename)
                else:
                    raise
        return ImageSource(result, size=src_size, image_opts=image_opts, cacheable=cacheable)

    def _src_size(self):
        width = self.tile_grid[0]*self.tile_size[0]
        height = self.tile_grid[1]*self.tile_size[1]
        return width, height

    def _tile_offset(self, i):
        """
        Return the image offset (upper-left coord) of the i-th tile,
        where the tiles are ordered row-wise, top to bottom.
        """
        return (i%self.tile_grid[0]*self.tile_size[0],
                i//self.tile_grid[0]*self.tile_size[1])


class TileSplitter(object):
    """
    Splits a large image into multiple tiles.
    """
    def __init__(self, meta_tile, image_opts):
        self.meta_img = meta_tile.as_image()
        self.image_opts = image_opts

    def get_tile(self, crop_coord, tile_size):
        """
        Return the cropped tile.
        :param crop_coord: the upper left pixel coord to start
        :param tile_size: width and height of the new tile
        :rtype: `ImageSource`
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
        return ImageSource(crop, size=tile_size, image_opts=self.image_opts)


class TiledImage(object):
    """
    An image built-up from multiple tiles.
    """
    def __init__(self, tiles, tile_grid, tile_size, src_bbox, src_srs):
        """
        :param tiles: all tiles (sorted row-wise, top to bottom)
        :param tile_grid: the tile grid size
        :type tile_grid: ``(int(x_tiles), int(y_tiles))``
        :param tile_size: the size of each tile
        :param src_bbox: the bbox of all tiles
        :param src_srs: the srs of the bbox
        :param transparent: if the sources are transparent
        """
        self.tiles = tiles
        self.tile_grid = tile_grid
        self.tile_size = tile_size
        self.src_bbox = src_bbox
        self.src_srs = src_srs

    def image(self, image_opts):
        """
        Return the tiles as one merged image.

        :rtype: `ImageSource`
        """
        tm = TileMerger(self.tile_grid, self.tile_size)
        return tm.merge(self.tiles, image_opts=image_opts)

    def transform(self, req_bbox, req_srs, out_size, image_opts):
        """
        Return the the tiles as one merged and transformed image.

        :param req_bbox: the bbox of the output image
        :param req_srs: the srs of the req_bbox
        :param out_size: the size in pixel of the output image
        :rtype: `ImageSource`
        """
        transformer = ImageTransformer(self.src_srs, req_srs)
        src_img = self.image(image_opts)
        return transformer.transform(src_img, self.src_bbox, out_size, req_bbox,
            image_opts)
