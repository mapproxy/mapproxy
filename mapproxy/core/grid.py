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

"""
(Meta-)Tile grids (data and calculations).
"""
from __future__ import division
import math

import logging
log = logging.getLogger(__name__)

from mapproxy.core.config import base_config
from mapproxy.core.srs import SRS, get_epsg_num

geodetic_epsg_codes = [4326, 31466, 31467, 31468, 31469]

def get_resolution(bbox, size):
    """
    Calculate the highest resolution needed to draw the bbox
    into an image with given size.
    
    >>> get_resolution((-180,-90,180,90), (256, 256))
    0.703125
    
    :returns: the resolution
    :rtype: float
    """
    w = abs(bbox[0] - bbox[2])
    h = abs(bbox[1] - bbox[3])
    return min(w/size[0], h/size[1])

def tile_grid_for_epsg(epsg, bbox=None, tile_size=(256, 256), res=None):
    """
    Create a tile grid that matches the given epsg code:
    
    :param epsg: the epsg code
    :type epsg: 'EPSG:0000', '0000' or 0000
    :param bbox: the bbox of the grid
    :param tile_size: the size of each tile
    :param res: a list with all resolutions
    """
    epsg = get_epsg_num(epsg)
    if epsg in geodetic_epsg_codes:
        return TileGrid(epsg, is_geodetic=True, bbox=bbox, tile_size=tile_size, res=res)
    return TileGrid(epsg, bbox=bbox, tile_size=tile_size, res=res)

RES_TYPE_SQRT2 = 'sqrt2'
RES_TYPE_GLOBAL = 'global'
RES_TYPE_CUSTOM = 'custom'

class TileGrid(object):
    """
    This class represents a regular tile grid. The first level (0) contains a single
    tile, the origin is bottom-left.
    
    :ivar res_type: the type of the multi-resolution pyramid.
    :type res_type: `RES_TYPE_CUSTOM`, `RES_TYPE_GLOBAL`, `RES_TYPE_SQRT2`
    :ivar levels: the number of levels
    :ivar tile_size: the size of each tile in pixel
    :type tile_size: ``int(with), int(height)``
    :ivar srs: the srs of the grid
    :type srs: `SRS`
    :ivar bbox: the bbox of the grid, tiles may overlap this bbox
    """
    
    spheroid_a = 6378137.0 # for 900913
    
    def __init__(self, epsg=900913, bbox=None, tile_size=(256, 256), res=None,
                 is_geodetic=False, levels=None):
        """
        >>> grid = TileGrid(epsg=900913)
        >>> [round(x, 2) for x in grid.bbox]
        [-20037508.34, -20037508.34, 20037508.34, 20037508.34]
        """
        self.srs = SRS(epsg)
        self.tile_size = tile_size
        self.is_geodetic = is_geodetic
        
        self.stretch_factor = base_config().image.stretch_factor
        'allow images to be scaled by this factor before the next level will be selected'
        
        if levels is None:
            self.levels = 20
        else:
            self.levels = levels
        
        self.res_type = RES_TYPE_CUSTOM
        
        if bbox is None and res is None and tile_size == (256, 256):
            self.res_type = RES_TYPE_GLOBAL
        
        if bbox is None:
            bbox = self._calc_bbox()
        self.bbox = bbox
        
        if res is None:
            res = self._calc_res()
        elif res == 'sqrt2':
            self.res_type = RES_TYPE_SQRT2
            if levels is None:
                self.levels = 40
            res = self._calc_res(factor=math.sqrt(2))
        elif is_float(res):
            res = self._calc_res(factor=float(res))

        self.levels = len(res)
        self.resolutions = res
        
        self.grid_sizes = self._calc_grids()
    
    def _calc_grids(self):
        width = self.bbox[2] - self.bbox[0]
        height = self.bbox[3] - self.bbox[1]
        grids = []
        for res in self.resolutions:
            x = math.ceil(width / res / self.tile_size[0])
            y = math.ceil(height / res / self.tile_size[1])
            grids.append((int(x), int(y)))
        
        return grids
    
    def _calc_bbox(self):
        if self.is_geodetic:
            return (-180.0, -90.0, 180.0, 90.0)
        else:
            circum = 2 * math.pi * self.spheroid_a
            offset = circum / 2.0
            return (-offset, -offset, offset, offset)
    
    def _calc_res(self, factor=None):
        width = self.bbox[2] - self.bbox[0]
        height = self.bbox[3] - self.bbox[1]
        initial_res = max(width/self.tile_size[0], height/self.tile_size[1])
        if factor is None:
            return pyramid_res_level(initial_res, levels=self.levels)
        else:
            return pyramid_res_level(initial_res, factor, levels=self.levels)
    
    
    def resolution(self, level):
        """
        Returns the resolution of the `level` in units/pixel.
        
        :param level: the zoom level index (zero is top)
        
        >>> grid = TileGrid(epsg=900913)
        >>> grid.resolution(0)
        156543.03392804097
        >>> grid.resolution(1)
        78271.516964020484
        >>> grid.resolution(4)
        9783.9396205025605
        """
        return self.resolutions[level]
    
    def closest_level(self, res):
        """
        Returns the level index that offers the required resolution.
        
        :param res: the required resolution
        :returns: the level with the requested or higher resolution
        
        >>> grid = TileGrid(epsg=900913)
        >>> grid.stretch_factor = 1.1
        >>> l1_res = grid.resolution(1)
        >>> [grid.closest_level(x) for x in (320000.0, 160000.0, l1_res+50, l1_res, \
                                             l1_res-50, l1_res*0.91, l1_res*0.89, 8000.0)]
        [0, 0, 1, 1, 1, 1, 2, 5]
        """
        for level, l_res in enumerate(self.resolutions):
            if l_res <= res*self.stretch_factor:
                return level
        return level
    
    def tile(self, x, y, level):
        """
        Returns the tile id for the given point.
        
        >>> grid = TileGrid(epsg=900913)
        >>> grid.tile(1000, 1000, 0)
        (0, 0, 0)
        >>> grid.tile(1000, 1000, 1)
        (1, 1, 1)
        >>> grid = TileGrid(epsg=900913, tile_size=(512, 512))
        >>> grid.tile(1000, 1000, 2)
        (2, 2, 2)
        """
        res = self.resolution(level)
        x = x - self.bbox[0]
        y = y - self.bbox[1]
        tile_x = x/float(res*self.tile_size[0])
        tile_y = y/float(res*self.tile_size[1])
        return (int(math.floor(tile_x)), int(math.floor(tile_y)), level)
    
    def flip_tile_coord(self, (x, y, z)):
        """
        Flip the tile coord on the y-axis. (Switch between bottom-left and top-left
        origin.)
        
        >>> grid = TileGrid(epsg=900913)
        >>> grid.flip_tile_coord((0, 1, 1))
        (0, 0, 1)
        >>> grid.flip_tile_coord((1, 3, 2))
        (1, 0, 2)
        """
        return (x, self.grid_sizes[z][1]-1-y, z)
    
    def get_affected_tiles(self, bbox, size, req_srs=None, inverse=False):
        """
        Get a list with all affected tiles for a bbox and output size.
        
        :returns: the bbox, the size and a list with tile coordinates, sorted row-wise
        :rtype: ``bbox, (xs, yz), [(x, y, z), ...]``
        
        >>> grid = TileGrid()
        >>> bbox = (-20037508.34, -20037508.34, 20037508.34, 20037508.34)
        >>> tile_size = (256, 256)
        >>> grid.get_affected_tiles(bbox, tile_size)
        ... #doctest: +NORMALIZE_WHITESPACE +ELLIPSIS
        ((-20037508.342789244, -20037508.342789244,\
          20037508.342789244, 20037508.342789244), (1, 1),\
          <generator object at ...>)
        """
        if req_srs and req_srs != self.srs:
            src_bbox = req_srs.transform_bbox_to(self.srs, bbox)
        else:
            src_bbox = bbox
        
        res = get_resolution(src_bbox, size)
        level = self.closest_level(res)
        # remove 1/10 of a pixel so we don't get a tiles we only touch
        x_delta = (src_bbox[2]-src_bbox[0]) / size[0] / 10.0
        y_delta = (src_bbox[3]-src_bbox[1]) / size[1] / 10.0
        x0, y0, _ = self.tile(src_bbox[0]+x_delta, src_bbox[1]+y_delta, level)
        x1, y1, _ = self.tile(src_bbox[2]-x_delta, src_bbox[3]-y_delta, level)
        
        log.debug('BBOX: ' + str(src_bbox))
        log.debug('coords: %f, %f, %f, %f' % (x0, y0, x1, y1))
        log.debug('res: ' + str(res))
        
        xs = range(x0, x1+1)
        if inverse:
            y0 = int(self.grid_sizes[level][1]) - 1 - y0
            y1 = int(self.grid_sizes[level][1]) - 1 - y1
            ys = range(y1, y0+1)
        else:
            ys = range(y1, y0-1, -1)
        ll = (xs[0], ys[-1], level)
        ur = (xs[-1], ys[0], level)
        if inverse:
            ll = self.flip_tile_coord(ll)
            ur = self.flip_tile_coord(ur)
        abbox = self._get_bbox([ll, ur])
        return (abbox, (len(xs), len(ys)),
                _create_tile_list(xs, ys, level, self.grid_sizes[level]))
    
    def _get_bbox(self, tiles):
        """
        Returns the bbox of multiple tiles.
        The tiles should be ordered row-wise, bottom-up.
        
        :param tiles: ordered list of tiles
        :returns: the bbox of all tiles
        """
        ll = tiles[0]
        ur = tiles[-1]
        x0, y0 = self._get_south_west_point(ll)
        x1, y1 = self._get_south_west_point((ur[0]+1, ur[1]+1, ur[2]))
        return x0, y0, x1, y1
    
    def _get_south_west_point(self, tile_coord):
        """
        Returns the coordinate of the lower left corner.
        
        :param tile_coord: the tile coordinate
        :type tile_coord: ``(x, y, z)``
        
        >>> grid = TileGrid(epsg=900913)
        >>> [round(x, 2) for x in grid._get_south_west_point((0, 0, 0))]
        [-20037508.34, -20037508.34]
        >>> [round(x, 2) for x in grid._get_south_west_point((1, 1, 1))]
        [0.0, 0.0]
        """
        x, y, z = tile_coord
        res = self.resolution(z)
        x0 = self.bbox[0] + x * res * self.tile_size[0]
        y0 = self.bbox[1] + y * res * self.tile_size[1]
        return x0, y0
    
    def tile_bbox(self, (x, y, z)):
        """
        Returns the bbox of the given tile.
        
        >>> grid = TileGrid(epsg=900913)
        >>> [round(x, 2) for x in grid.tile_bbox((0, 0, 0))]
        [-20037508.34, -20037508.34, 20037508.34, 20037508.34]
        >>> [round(x, 2) for x in grid.tile_bbox((1, 1, 1))]
        [0.0, 0.0, 20037508.34, 20037508.34]
        """
        x0, y0 = self._get_south_west_point((x, y, z))
        res = self.resolution(z)
        width = res * self.tile_size[0]
        height = res * self.tile_size[1]
        return (x0, y0, x0+width, y0+height)
    
    def limit_tile(self, tile_coord):
        """
        Check if the `tile_coord` is in the grid.
        
        :returns: the `tile_coord` if it is within the ``grid``,
                  otherwise ``None``.
        
        >>> grid = TileGrid(epsg=900913)
        >>> grid.limit_tile((-1, 0, 2)) == None
        True
        >>> grid.limit_tile((1, 2, 1)) == None
        True
        >>> grid.limit_tile((1, 2, 2))
        (1, 2, 2)
        """
        x, y, z = tile_coord
        grid = self.grid_sizes[z]
        if z < 0 or z >= self.levels:
            return None
        if x < 0 or y < 0 or x >= grid[0] or y >= grid[1]:
            return None
        return x, y, z
    
    def __repr__(self):
        return '%s(%r, (%.4f, %.4f, %.4f, %.4f),...)' % (self.__class__.__name__,
            self.srs, self.bbox[0], self.bbox[1], self.bbox[2], self.bbox[3])


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

def is_float(x):
    try:
        float(x)
        return True
    except TypeError:
        return False

def pyramid_res_level(initial_res, factor=2.0, levels=20):
    """
    Return resolutions of an image pyramid.
    
    :param initial_res: the resolution of the top level (0)
    :param factor: the factor between each level, for tms access 2
    :param levels: number of resolutions to generate
    
    >>> pyramid_res_level(10000, levels=5)
    [10000.0, 5000.0, 2500.0, 1250.0, 625.0]
    >>> pyramid_res_level(10000, factor=1/0.75, levels=5)
    [10000.0, 7500.0, 5625.0, 4218.7500000000009, 3164.0625000000005]
    """
    return [initial_res/factor**n for n in range(levels)]

class MetaGrid(object):
    """
    This class contains methods to calculate bbox, etc. of metatiles.
    
    :param grid: the grid to use for the metatiles
    :param meta_size: the number of tiles a metatile consist
    :type meta_size: ``(x_size, y_size)``
    :param meta_buffer: the buffer size in pixel that is added to each metatile.
        the number is added to all four borders.
        this buffer may improve the handling of lables overlapping (meta)tile borders.
    :type meta_buffer: pixel
    """
    def __init__(self, grid, meta_size, meta_buffer=0):
        self.grid = grid
        self._meta_size = meta_size
        self.meta_buffer = meta_buffer
    
    def meta_bbox(self, tile_coord):
        """
        Returns the bbox of the metatile that contains `tile_coord`.
        
        :type tile_coord: ``(x, y, z)``
        
        >>> mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2))
        >>> [round(x, 2) for x in mgrid.meta_bbox((0, 0, 2))]
        [-20037508.34, -20037508.34, 0.0, 0.0]
        >>> mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2))
        >>> [round(x, 2) for x in mgrid.meta_bbox((0, 0, 0))]
        [-20037508.34, -20037508.34, 20037508.34, 20037508.34]
        
        """
        x, y, z = tile_coord
        meta_size = self.meta_size(z)
        
        if z == 0 and meta_size == (1, 1):
            return self.grid.tile_bbox((0, 0, 0))
        
        meta_x = x//meta_size[0]
        meta_y = y//meta_size[1]
        
        (minx, miny, maxx, maxy) = self.grid.tile_bbox((meta_x * meta_size[0],
                                                        meta_y * meta_size[1], z))
        width = (maxx - minx) * meta_size[0]
        height = (maxy - miny) * meta_size[1]
        maxx = minx + width
        maxy = miny + height
        
        if self.meta_buffer > 0:
            res = self.grid.resolution(z)
            minx -= self.meta_buffer * res
            miny -= self.meta_buffer * res
            maxx += self.meta_buffer * res
            maxy += self.meta_buffer * res
        
        return (minx, miny, maxx, maxy)
        
    def tiles(self, tile_coord):
        """
        Returns all tiles that belong to the same metatile as `tile_coord`.
        The result contains for each tile the ``tile_coord`` and the upper-left
        pixel coordinate of the tile in the meta tile image.
        
        >>> mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2))
        >>> tiles = list(mgrid.tiles((0, 1, 1)))
        >>> tiles[0], tiles[-1]
        (((0, 1, 1), (0, 0)), ((1, 0, 1), (256, 256)))
        >>> list(mgrid.tiles((0, 0, 0)))
        [((0, 0, 0), (0, 0))]
            """
        x, y, z = tile_coord
        
        meta_size = self.meta_size(z)
        if z == 0 and meta_size == (1, 1):
            yield ((0, 0, 0), (0, 0))
            raise StopIteration
        
        x0 = x//meta_size[0] * meta_size[0]
        y0 = y//meta_size[1] * meta_size[1]
        
        for i, y in enumerate(range(y0+(meta_size[1]-1), y0-1, -1)):
            for j, x in enumerate(range(x0, x0+meta_size[0])):
                yield (x, y, z), (j*self.grid.tile_size[0] + self.meta_buffer,
                                  i*self.grid.tile_size[1] + self.meta_buffer)
    
    def tile_size(self, level):
        """
        Returns the size of a metatile (includes ``meta_buffer`` if present).
        
        :param level: the zoom level
        
        >>> mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2), meta_buffer=10)
        >>> mgrid.tile_size(2)
        (532, 532)
        >>> mgrid.tile_size(0)
        (256, 256)
        """
        
        meta_size = self.meta_size(level)
        
        if level == 0 and meta_size == (1, 1):
            return self.grid.tile_size
        
        return (self.grid.tile_size[0] * meta_size[0] + 2*self.meta_buffer,
                self.grid.tile_size[1] * meta_size[1] + 2*self.meta_buffer)
    
    def meta_size(self, level):
        grid_size = self.grid.grid_sizes[level]
        return min(self._meta_size[0], grid_size[0]), min(self._meta_size[1], grid_size[1])

