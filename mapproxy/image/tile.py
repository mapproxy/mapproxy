# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from mapproxy.platform.image import Image
from mapproxy.image import ImageSource
from mapproxy.image.transform import ImageTransformer

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
    
    def merge(self, ordered_tiles, transparent=False):
        """
        Merge all tiles into one image.
        
        :param ordered_tiles: list of tiles, sorted row-wise (top to bottom)
        :rtype: `ImageSource`
        """
        if self.tile_grid == (1, 1):
            assert len(ordered_tiles) == 1
            if ordered_tiles[0] is not None:
                tile = ordered_tiles.pop()
                return ImageSource(tile.source, size=self.tile_size,
                                   transparent=transparent)
        src_size = self._src_size()
        
        if transparent:
            result = Image.new("RGBA", src_size, (255, 255, 255, 0))
        else:
            result = Image.new("RGB", src_size, (255, 255, 255))

        for i, source in enumerate(ordered_tiles):
            if source is None:
                continue
            try:
                tile = source.as_image()
                pos = self._tile_offset(i)
                if transparent:
                    tile.draft('RGBA', self.tile_size)
                else:
                    tile.draft('RGB', self.tile_size)
                result.paste(tile, pos)
                source.close_buffers()
            except IOError, e:
                if e.errno is None: # PIL error
                    log.warn('unable to load tile %s, removing it (reason was: %s)'
                             % (source, str(e)))
                    if getattr(source, 'filename'):
                        if os.path.exists(source.filename):
                            os.remove(source.filename)
                else:
                    raise
        return ImageSource(result, size=src_size, transparent=transparent)
    
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
    def __init__(self, meta_tile, format='png'):
        self.meta_img = meta_tile.as_image()
        if self.meta_img.mode == 'P' and format in ('png', 'gif'):
            self.meta_img = self.meta_img.convert('RGBA')
        self.format = format
    
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
        
        crop = self.meta_img.crop((minx, miny, maxx, maxy))
        return ImageSource(crop, self.format)
    

class TiledImage(object):
    """
    An image built-up from multiple tiles.
    """
    def __init__(self, tiles, tile_grid, tile_size, src_bbox, src_srs, transparent):
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
        self.transparent = transparent
    
    def image(self):
        """
        Return the tiles as one merged image.
        
        :rtype: `ImageSource`
        """
        tm = TileMerger(self.tile_grid, self.tile_size)
        return tm.merge(self.tiles, transparent=self.transparent)
    
    def transform(self, req_bbox, req_srs, out_size, resampling=None):
        """
        Return the the tiles as one merged and transformed image.
        
        :param req_bbox: the bbox of the output image
        :param req_srs: the srs of the req_bbox
        :param out_size: the size in pixel of the output image
        :rtype: `ImageSource`
        """
        transformer = ImageTransformer(self.src_srs, req_srs, resampling=resampling)
        src_img = self.image()
        return transformer.transform(src_img, self.src_bbox, out_size, req_bbox)
