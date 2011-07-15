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
(Meta-)Tile grids (data and calculations).
"""
from __future__ import division
import math

from mapproxy.srs import SRS, get_epsg_num, merge_bbox
from mapproxy.util.collections import ImmutableDictList

geodetic_epsg_codes = [4326]

class GridError(Exception):
    pass

class NoTiles(GridError):
    pass

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


# defer loading of default bbox since custom proj settings
# are not loaded on import time
class _default_bboxs(object):
    _defaults = {
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
            for epsg, bbox in self._defaults.iteritems():
                defaults[SRS(epsg)] = bbox
            self.defaults = defaults
        return self.defaults[key]
default_bboxs = _default_bboxs()

def tile_grid(srs=None, bbox=None, bbox_srs=None, tile_size=(256, 256),
              res=None, res_factor=2.0, threshold_res=None,
              num_levels=None, min_res=None, max_res=None,
              stretch_factor=1.15, max_shrink_factor=4.0,
              align_with=None, origin='ll', name=None
              ):
    """
    This function creates a new TileGrid.
    """
    if srs is None: srs = 'EPSG:900913'
    srs = SRS(srs)
    
    if not bbox:
        bbox = default_bboxs.get(srs)
        if not bbox:
            raise ValueError('need a bbox for grid with %s' % srs)
    
    bbox = grid_bbox(bbox, srs=srs, bbox_srs=bbox_srs)
    
    if res:
        if isinstance(res, list):
            if isinstance(res[0], (tuple, list)):
                # named resolutions
                res = sorted(res, key=lambda x: x[1], reverse=True)
            else:
                res = sorted(res, reverse=True)
            assert min_res is None
            assert max_res is None
            assert align_with is None
        else:
            raise ValueError("res is not a list, use res_factor for float values")

    elif align_with is not None:
        res = aligned_resolutions(min_res, max_res, res_factor, num_levels, bbox, tile_size,
                                  align_with)
    else:
        res = resolutions(min_res, max_res, res_factor, num_levels, bbox, tile_size)
    
    return TileGrid(srs, bbox=bbox, tile_size=tile_size, res=res, threshold_res=threshold_res,
                    stretch_factor=stretch_factor, max_shrink_factor=max_shrink_factor,
                    origin=origin, name=name)

def aligned_resolutions(min_res=None, max_res=None, res_factor=2.0, num_levels=None,
                bbox=None, tile_size=(256, 256), align_with=None):
    
    
    alinged_res = align_with.resolutions
    res = list(alinged_res)
    
    if not min_res:
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        min_res = max(width/tile_size[0], height/tile_size[1])
        
    res = [r for r in res if r <= min_res]
    
    if max_res:
        res = [r for r in res if r >= max_res]

    if num_levels:
        res = res[:num_levels]
    
    factor_calculated = res[0]/res[1]
    if res_factor == 'sqrt2' and round(factor_calculated, 8) != round(math.sqrt(2), 8):
        if round(factor_calculated, 8) == 2.0:
            new_res = []
            for r in res:
                new_res.append(r)
                new_res.append(r/math.sqrt(2))
            res = new_res
    elif res_factor == 2.0 and round(factor_calculated, 8) != round(2.0, 8):
        if round(factor_calculated, 8) == round(math.sqrt(2), 8):
            res = res[::2]
    return res


def resolutions(min_res=None, max_res=None, res_factor=2.0, num_levels=None,
                bbox=None, tile_size=(256, 256)):
    if res_factor == 'sqrt2':
        res_factor = math.sqrt(2)

    res = []
    if not min_res:
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        min_res = max(width/tile_size[0], height/tile_size[1])
    
    if max_res:
        if num_levels:
            res_step = (math.log10(min_res) - math.log10(max_res)) / (num_levels-1)
            res = [10**(math.log10(min_res) - res_step*i) for i in range(num_levels)]
        else:
            res = [min_res]
            while True:
                next_res = res[-1]/res_factor
                if max_res >= next_res:
                    break
                res.append(next_res)
    else:
        if not num_levels:
            num_levels = 20 if res_factor != math.sqrt(2) else 40
        res = [min_res]
        while len(res) < num_levels:
            res.append(res[-1]/res_factor)
        
    return res

def grid_bbox(bbox, bbox_srs, srs):
    bbox = bbox_tuple(bbox)
    if bbox_srs:
        bbox = SRS(bbox_srs).transform_bbox_to(srs, bbox)
    return bbox
    
def bbox_tuple(bbox):
    """
    >>> bbox_tuple('20,-30,40,-10')
    (20.0, -30.0, 40.0, -10.0)
    >>> bbox_tuple([20,-30,40,-10])
    (20.0, -30.0, 40.0, -10.0)
    
    """
    if isinstance(bbox, basestring):
        bbox = bbox.split(',')
    bbox = tuple(map(float, bbox))
    return bbox
    


def bbox_width(bbox):
    return bbox[2] - bbox[0]

def bbox_height(bbox):
    return bbox[3] - bbox[1]

def bbox_size(bbox):
    return bbox_width(bbox), bbox_height(bbox)


class NamedGridList(ImmutableDictList):
    def __init__(self, items):
        tmp = []
        for i, value in enumerate(items):
            if isinstance(value, (tuple, list)):
                name, value = value
            else:
                name = str('%02d' % i)
            tmp.append((name, value))
        ImmutableDictList.__init__(self, tmp)

class TileGrid(object):
    """
    This class represents a regular tile grid. The first level (0) contains a single
    tile, the origin is bottom-left.
    
    :ivar levels: the number of levels
    :ivar tile_size: the size of each tile in pixel
    :type tile_size: ``int(with), int(height)``
    :ivar srs: the srs of the grid
    :type srs: `SRS`
    :ivar bbox: the bbox of the grid, tiles may overlap this bbox
    """
    
    spheroid_a = 6378137.0 # for 900913
    flipped_y_axis = False
    
    def __init__(self, srs=900913, bbox=None, tile_size=(256, 256), res=None,
                 threshold_res=None, is_geodetic=False, levels=None,
                 stretch_factor=1.15, max_shrink_factor=4.0, origin='ll',
                 name=None):
        """
        :param stretch_factor: allow images to be scaled up by this factor
            before the next level will be selected
        :param max_shrink_factor: allow images to be scaled down by this
            factor before NoTiles is raised
        
        >>> grid = TileGrid(srs=900913)
        >>> [round(x, 2) for x in grid.bbox]
        [-20037508.34, -20037508.34, 20037508.34, 20037508.34]
        """
        if isinstance(srs, (int, basestring)):
            srs = SRS(srs)
        self.srs = srs
        self.tile_size = tile_size
        self.origin = origin
        self.name = name

        if origin in ('ul', 'nw'):
            self.flipped_y_axis = True

        self.is_geodetic = is_geodetic
        
        self.stretch_factor = stretch_factor
        self.max_shrink_factor = max_shrink_factor
        
        if levels is None:
            self.levels = 20
        else:
            self.levels = levels
        
        if bbox is None:
            bbox = self._calc_bbox()
        self.bbox = bbox
        
        factor = None
        
        if res is None:
            factor = 2.0
            res = self._calc_res(factor=factor)
        elif res == 'sqrt2':
            if levels is None:
                self.levels = 40
            factor = math.sqrt(2)
            res = self._calc_res(factor=factor)
        elif is_float(res):
            factor = float(res)
            res = self._calc_res(factor=factor)
        
        self.levels = len(res)
        self.resolutions = NamedGridList(res)
        self.threshold_res = threshold_res
        
        self.grid_sizes = self._calc_grids()
    
    def _calc_grids(self):
        width = self.bbox[2] - self.bbox[0]
        height = self.bbox[3] - self.bbox[1]
        grids = []
        for idx, res in self.resolutions.iteritems():
            x = max(math.ceil(width // res / self.tile_size[0]), 1)
            y = max(math.ceil(height // res / self.tile_size[1]), 1)
            grids.append((idx, (int(x), int(y))))
        return NamedGridList(grids)
    
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
        
        >>> grid = TileGrid(SRS(900913))
        >>> '%.5f' % grid.resolution(0)
        '156543.03393'
        >>> '%.5f' % grid.resolution(1)
        '78271.51696'
        >>> '%.5f' % grid.resolution(4)
        '9783.93962'
        """
        return self.resolutions[level]
    
    def closest_level(self, res):
        """
        Returns the level index that offers the required resolution.
        
        :param res: the required resolution
        :returns: the level with the requested or higher resolution
        
        >>> grid = TileGrid(SRS(900913))
        >>> grid.stretch_factor = 1.1
        >>> l1_res = grid.resolution(1)
        >>> [grid.closest_level(x) for x in (320000.0, 160000.0, l1_res+50, l1_res, \
                                             l1_res-50, l1_res*0.91, l1_res*0.89, 8000.0)]
        [0, 0, 1, 1, 1, 1, 2, 5]
        """
        prev_l_res = self.resolutions[0]
        threshold = None
        thresholds = []
        if self.threshold_res:
            thresholds = self.threshold_res[::-1]
            threshold = thresholds.pop()
        
        threshold_result = None
        for level, l_res in enumerate(self.resolutions):
            if threshold and prev_l_res > threshold >= l_res:
                if res > threshold:
                    return level-1
                elif res >= l_res:
                    return level
                threshold = thresholds.pop() if thresholds else None
            
            if threshold_result is not None:
                return threshold_result

            if l_res <= res*self.stretch_factor:
                threshold_result = level
            prev_l_res = l_res
        return level
    
    def tile(self, x, y, level):
        """
        Returns the tile id for the given point.
        
        >>> grid = TileGrid(SRS(900913))
        >>> grid.tile(1000, 1000, 0)
        (0, 0, 0)
        >>> grid.tile(1000, 1000, 1)
        (1, 1, 1)
        >>> grid = TileGrid(SRS(900913), tile_size=(512, 512))
        >>> grid.tile(1000, 1000, 2)
        (2, 2, 2)
        """
        res = self.resolution(level)
        x = x - self.bbox[0]
        if self.flipped_y_axis:
            y = self.bbox[3] - y
        else:
            y = y - self.bbox[1]
        tile_x = x/float(res*self.tile_size[0])
        tile_y = y/float(res*self.tile_size[1])
        return (int(math.floor(tile_x)), int(math.floor(tile_y)), level)
    
    def flip_tile_coord(self, (x, y, z)):
        """
        Flip the tile coord on the y-axis. (Switch between bottom-left and top-left
        origin.)
        
        >>> grid = TileGrid(SRS(900913))
        >>> grid.flip_tile_coord((0, 1, 1))
        (0, 0, 1)
        >>> grid.flip_tile_coord((1, 3, 2))
        (1, 0, 2)
        """
        return (x, self.grid_sizes[z][1]-1-y, z)
    
    def supports_access_with_origin(self, origin):
        if self.origin == origin:
            return True
        grid_size = self.grid_sizes[0]
        level_0_bbox = self._tiles_bbox([(0, 0, 0), 
            (grid_size[0] - 1, grid_size[1] - 1, 0)])
        
        if self.bbox[1] == level_0_bbox[1] and self.bbox[3] == level_0_bbox[3]:
            return True
        else:
            return False
    
    def origin_tile(self, level, origin):
        assert self.supports_access_with_origin(origin), 'TODO error exception'
        tile = (0, 0, level)
        if self.origin != origin:
            tile = self.flip_tile_coord(tile)
        
        return tile
        
    def get_affected_tiles(self, bbox, size, req_srs=None):
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
          <generator object ...>)
        """
        src_bbox, level = self.get_affected_bbox_and_level(bbox, size, req_srs=req_srs)
        return self.get_affected_level_tiles(src_bbox, level)
    
    def get_affected_bbox_and_level(self, bbox, size, req_srs=None):
        if req_srs and req_srs != self.srs:
            src_bbox = req_srs.transform_bbox_to(self.srs, bbox)
        else:
            src_bbox = bbox
        
        if not bbox_intersects(self.bbox, src_bbox):
            raise NoTiles()
        
        res = get_resolution(src_bbox, size)
        level = self.closest_level(res)
        
        if res > self.resolutions[0]*self.max_shrink_factor:
            raise NoTiles()
        
        return src_bbox, level
    
    def get_affected_level_tiles(self, bbox, level):
        """
        Get a list with all affected tiles for a `bbox` in the given `level`.
        :returns: the bbox, the size and a list with tile coordinates, sorted row-wise
        :rtype: ``bbox, (xs, yz), [(x, y, z), ...]``

        >>> grid = TileGrid()
        >>> bbox = (-20037508.34, -20037508.34, 20037508.34, 20037508.34)
        >>> grid.get_affected_level_tiles(bbox, 0)
        ... #doctest: +NORMALIZE_WHITESPACE +ELLIPSIS
        ((-20037508.342789244, -20037508.342789244,\
          20037508.342789244, 20037508.342789244), (1, 1),\
          <generator object ...>)
        """
        # remove 1/10 of a pixel so we don't get a tiles we only touch
        delta = self.resolutions[level] / 10.0
        x0, y0, _ = self.tile(bbox[0]+delta, bbox[1]+delta, level)
        x1, y1, _ = self.tile(bbox[2]-delta, bbox[3]-delta, level)
        try:
            return self._tile_iter(x0, y0, x1, y1, level)
        except IndexError:
            raise GridError('Invalid BBOX')
        
    def _tile_iter(self, x0, y0, x1, y1, level):
        xs = range(x0, x1+1)
        if self.flipped_y_axis:
            y0, y1 = y1, y0
            ys = range(y0, y1+1)
        else:
            ys = range(y1, y0-1, -1)
        
        ll = (xs[0], ys[-1], level)
        ur = (xs[-1], ys[0], level)

        abbox = self._tiles_bbox([ll, ur])
        return (abbox, (len(xs), len(ys)),
                _create_tile_list(xs, ys, level, self.grid_sizes[level]))
        
    def _tiles_bbox(self, tiles):
        """
        Returns the bbox of multiple tiles.
        The tiles should be ordered row-wise, bottom-up.
        
        :param tiles: ordered list of tiles
        :returns: the bbox of all tiles
        """
        ll_bbox = self.tile_bbox(tiles[0])
        ur_bbox = self.tile_bbox(tiles[-1])
        return merge_bbox(ll_bbox, ur_bbox)
    
    def tile_bbox(self, tile_coord, limit=False):
        """
        Returns the bbox of the given tile.
        
        >>> grid = TileGrid(SRS(900913))
        >>> [round(x, 2) for x in grid.tile_bbox((0, 0, 0))]
        [-20037508.34, -20037508.34, 20037508.34, 20037508.34]
        >>> [round(x, 2) for x in grid.tile_bbox((1, 1, 1))]
        [0.0, 0.0, 20037508.34, 20037508.34]
        """
        x, y, z = tile_coord
        res = self.resolution(z)
        
        x0 = self.bbox[0] + round(x * res * self.tile_size[0], 12)
        x1 = x0 + round(res * self.tile_size[0], 12)
        
        if self.flipped_y_axis:
            y1 = self.bbox[3] - round(y * res * self.tile_size[1], 12)
            y0 = y1 - round(res * self.tile_size[1], 12)
        else:
            y0 = self.bbox[1] + round(y * res * self.tile_size[1], 12)
            y1 = y0 + round(res * self.tile_size[1], 12)
        
        if limit:
            return (
                max(x0, self.bbox[0]),
                max(y0, self.bbox[1]),
                min(x1, self.bbox[2]),
                min(y1, self.bbox[3])
            )

        return x0, y0, x1, y1
    
    def limit_tile(self, tile_coord):
        """
        Check if the `tile_coord` is in the grid.
        
        :returns: the `tile_coord` if it is within the ``grid``,
                  otherwise ``None``.
        
        >>> grid = TileGrid(SRS(900913))
        >>> grid.limit_tile((-1, 0, 2)) == None
        True
        >>> grid.limit_tile((1, 2, 1)) == None
        True
        >>> grid.limit_tile((1, 2, 2))
        (1, 2, 2)
        """
        x, y, z = tile_coord
        if isinstance(z, basestring):
            if z not in self.grid_sizes:
                return None
        elif z < 0 or z >= self.levels:
            return None
        grid = self.grid_sizes[z]
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
    >>> map(lambda x: round(x, 4),
    ...     pyramid_res_level(10000, factor=1/0.75, levels=5))
    [10000.0, 7500.0, 5625.0, 4218.75, 3164.0625]
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
        self.meta_size = meta_size or 0
        self.meta_buffer = meta_buffer
    
    def _meta_bbox(self, tile_coord=None, tiles=None, limit_to_bbox=True):
        """
        Returns the bbox of the metatile that contains `tile_coord`.
        
        :type tile_coord: ``(x, y, z)``
        
        >>> mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2))
        >>> [round(x, 2) for x in mgrid._meta_bbox((0, 0, 2))[0]]
        [-20037508.34, -20037508.34, 0.0, 0.0]
        >>> mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2))
        >>> [round(x, 2) for x in mgrid._meta_bbox((0, 0, 0))[0]]
        [-20037508.34, -20037508.34, 20037508.34, 20037508.34]
        """
        if tiles:
            assert tile_coord is None
            level = tiles[0][2]
            bbox = self.grid._tiles_bbox(tiles)
        else:
            level = tile_coord[2]
            bbox = self.unbuffered_meta_bbox(tile_coord)
        return self._buffered_bbox(bbox, level, limit_to_bbox)
    
    
    def unbuffered_meta_bbox(self, tile_coord):
        x, y, z = tile_coord
        
        meta_size = self._meta_size(z)

        return self.grid._tiles_bbox([(tile_coord), 
            (x+meta_size[0]-1, y+meta_size[1]-1, z)])
    
    def _buffered_bbox(self, bbox, level, limit_to_grid_bbox=True):
        minx, miny, maxx, maxy = bbox
        
        buffers = (0, 0, 0, 0)
        if self.meta_buffer > 0:
            res = self.grid.resolution(level)
            minx -= self.meta_buffer * res
            miny -= self.meta_buffer * res
            maxx += self.meta_buffer * res
            maxy += self.meta_buffer * res
            buffers = [self.meta_buffer, self.meta_buffer, self.meta_buffer, self.meta_buffer]
            
            if limit_to_grid_bbox:
                if self.grid.bbox[0] > minx:
                    delta = self.grid.bbox[0] - minx
                    buffers[0] = buffers[0] - int(round(delta / res, 5))
                    minx = self.grid.bbox[0]
                if self.grid.bbox[1] > miny:
                    delta = self.grid.bbox[1] - miny
                    buffers[1] = buffers[1] - int(round(delta / res, 5))
                    miny = self.grid.bbox[1]
                if self.grid.bbox[2] < maxx:
                    delta = maxx - self.grid.bbox[2]
                    buffers[2] = buffers[2] - int(round(delta / res, 5))
                    maxx = self.grid.bbox[2]
                if self.grid.bbox[3] < maxy:
                    delta = maxy - self.grid.bbox[3]
                    buffers[3] = buffers[3] - int(round(delta / res, 5))
                    maxy = self.grid.bbox[3]
        return (minx, miny, maxx, maxy), tuple(buffers)
    
    def meta_tile(self, tile_coord):
        """
        Returns the meta tile for `tile_coord`.
        """
        tile_coord = self.main_tile(tile_coord)
        level = tile_coord[2]
        bbox, buffers = self._meta_bbox(tile_coord)
        grid_size = self._meta_size(level)
        size = self._size_from_buffered_bbox(bbox, level)
        
        tile_patterns = self._tiles_pattern(tile=tile_coord, grid_size=grid_size, buffers=buffers)
        
        return MetaTile(bbox=bbox, size=size, tile_patterns=tile_patterns,
            grid_size=grid_size
        )
    
    def minimal_meta_tile(self, tiles):
        """
        Returns a MetaTile that contains all `tiles` plus ``meta_buffer``,
        but nothing more.
        """
        
        tiles, grid_size, bounds = self._full_tile_list(tiles)
        tiles = list(tiles)
        bbox, buffers = self._meta_bbox(tiles=bounds)
        
        level = tiles[0][2]
        size = self._size_from_buffered_bbox(bbox, level)
        
        tile_pattern = self._tiles_pattern(tiles=tiles, grid_size=grid_size, buffers=buffers)

        return MetaTile(
            bbox=bbox,
            size=size,
            tile_patterns=tile_pattern,
            grid_size=grid_size,
        )

    def _size_from_buffered_bbox(self, bbox, level):
        # meta_size * tile_size + 2*buffer does not work,
        # since the buffer can get truncated at the grid border
        res = self.grid.resolution(level)
        width = int(round((bbox[2] - bbox[0]) / res))
        height = int(round((bbox[3] - bbox[1]) / res))
        return width, height
    
    def _full_tile_list(self, tiles):
        """
        Return a complete list of all tiles that a minimal meta tile with `tiles` contains.
        
        >>> mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2))
        >>> mgrid._full_tile_list([(0, 0, 2), (1, 1, 2)])
        ([(0, 1, 2), (1, 1, 2), (0, 0, 2), (1, 0, 2)], (2, 2), ((0, 0, 2), (1, 1, 2)))
        """
        tile = tiles.pop()
        z = tile[2]
        minx = maxx = tile[0]
        miny = maxy = tile[1]
        
        for tile in tiles:
            x, y = tile[:2]
            minx = min(minx, x)
            maxx = max(maxx, x)
            miny = min(miny, y)
            maxy = max(maxy, y)
        
        grid_size = 1+maxx-minx, 1+maxy-miny
        
        if self.grid.flipped_y_axis:
            ys = xrange(miny, maxy+1)
        else:
            ys = xrange(maxy, miny-1, -1)
        xs = xrange(minx, maxx+1)
        
        bounds = (minx, miny, z), (maxx, maxy, z)
        
        return list(_create_tile_list(xs, ys, z, (maxx+1, maxy+1))), grid_size, bounds

    def main_tile(self, tile_coord):
        x, y, z = tile_coord
        
        meta_size = self._meta_size(z)
        
        x0 = x//meta_size[0] * meta_size[0]
        y0 = y//meta_size[1] * meta_size[1]
        
        return x0, y0, z
    
    def tile_list(self, main_tile):
        tile_grid = self._meta_size(main_tile[2])
        return self._meta_tile_list(main_tile, tile_grid)
    
    def _meta_tile_list(self, main_tile, tile_grid):
        """
        >>> mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2))
        >>> mgrid._meta_tile_list((0, 1, 3), (2, 2))
        [(0, 1, 3), (1, 1, 3), (0, 0, 3), (1, 0, 3)]
        """
        minx, miny, z = self.main_tile(main_tile)
        maxx = minx + tile_grid[0] - 1
        maxy = miny + tile_grid[1] - 1
        if self.grid.flipped_y_axis:
            ys = xrange(miny, maxy+1)
        else:
            ys = xrange(maxy, miny-1, -1)
        xs = xrange(minx, maxx+1)
        
        return list(_create_tile_list(xs, ys, z, self.grid.grid_sizes[z]))
        
    def _tiles_pattern(self, grid_size, buffers, tile=None, tiles=None):
        """
        Returns the tile pattern for the given list of tiles.
        The result contains for each tile the ``tile_coord`` and the upper-left
        pixel coordinate of the tile in the meta tile image.
        
        >>> mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2))
        >>> tiles = list(mgrid._tiles_pattern(tiles=[(0, 1, 2), (1, 1, 2)],
        ...                                   grid_size=(2, 1),
        ...                                   buffers=(0, 0, 10, 10)))
        >>> tiles[0], tiles[-1]
        (((0, 1, 2), (0, 10)), ((1, 1, 2), (256, 10)))

        >>> tiles = list(mgrid._tiles_pattern(tile=(1, 1, 2),
        ...                                   grid_size=(2, 2),
        ...                                   buffers=(10, 20, 30, 40)))
        >>> tiles[0], tiles[-1]
        (((0, 1, 2), (10, 40)), ((1, 0, 2), (266, 296)))

        """
        if tile:
            tiles = self._meta_tile_list(tile, grid_size)

        for i in range(grid_size[1]):
            for j in range(grid_size[0]):
                yield tiles[j+i*grid_size[0]], (
                            j*self.grid.tile_size[0] + buffers[0],
                            i*self.grid.tile_size[1] + buffers[3])
    
    def _meta_size(self, level):
        grid_size = self.grid.grid_sizes[level]
        return min(self.meta_size[0], grid_size[0]), min(self.meta_size[1], grid_size[1])
    
    def get_affected_level_tiles(self, bbox, level):
        """
        Get a list with all affected tiles for a `bbox` in the given `level`.
        
        :returns: the bbox, the size and a list with tile coordinates, sorted row-wise
        :rtype: ``bbox, (xs, yz), [(x, y, z), ...]``
        
        >>> grid = MetaGrid(TileGrid(), (2, 2))
        >>> bbox = (-20037508.34, -20037508.34, 20037508.34, 20037508.34)
        >>> grid.get_affected_level_tiles(bbox, 0)
        ... #doctest: +NORMALIZE_WHITESPACE +ELLIPSIS
        ((-20037508.342789244, -20037508.342789244,\
          20037508.342789244, 20037508.342789244), (1, 1),\
          <generator object ...>)
        """
        
        # remove 1/10 of a pixel so we don't get a tiles we only touch
        delta = self.grid.resolutions[level] / 10.0
        x0, y0, _ = self.grid.tile(bbox[0]+delta, bbox[1]+delta, level)
        x1, y1, _ = self.grid.tile(bbox[2]-delta, bbox[3]-delta, level)
        
        meta_size = self._meta_size(level)
        
        x0 = x0//meta_size[0] * meta_size[0]
        x1 = x1//meta_size[0] * meta_size[0]
        y0 = y0//meta_size[1] * meta_size[1]
        y1 = y1//meta_size[1] * meta_size[1]
        
        try:
            return self._tile_iter(x0, y0, x1, y1, level)
        except IndexError:
            raise GridError('Invalid BBOX')
        
    def _tile_iter(self, x0, y0, x1, y1, level):
        meta_size = self._meta_size(level)
        
        xs = range(x0, x1+1, meta_size[0])
        if self.grid.flipped_y_axis:
            y0, y1 = y1, y0
            ys = range(y0, y1+1, meta_size[1])
        else:
            ys = range(y1, y0-1, -meta_size[1])
            
        ll = (xs[0], ys[-1], level)
        ur = (xs[-1], ys[0], level)
        # add meta_size to get full affected bbox
        ur = ur[0]+meta_size[0]-1, ur[1]+meta_size[1]-1, ur[2]
        abbox = self.grid._tiles_bbox([ll, ur])
        return (abbox, (len(xs), len(ys)),
                _create_tile_list(xs, ys, level, self.grid.grid_sizes[level]))


class MetaTile(object):
    def __init__(self, bbox, size, tile_patterns, grid_size):
        self.bbox = bbox
        self.size = size
        self.tile_patterns = list(tile_patterns)
        self.grid_size = grid_size
    
    @property
    def tiles(self):
        return [t[0] for t in self.tile_patterns]
    
    @property
    def main_tile_coord(self):
        """
        Returns the "main" tile of the meta tile. This tile(coord) can be used
        for locking.
        
        >>> t = MetaTile(None, None, [((0, 0, 0), (0, 0)), ((1, 0, 0), (100, 0))], (2, 1))
        >>> t.main_tile_coord
        (0, 0, 0)
        >>> t = MetaTile(None, None, [(None, None), ((1, 0, 0), (100, 0))], (2, 1))
        >>> t.main_tile_coord
        (1, 0, 0)
        """
        for t in self.tiles:
            if t is not None:
                return t
    
    def __repr__(self):
        return "MetaTile(%r, %r, %r, %r)" % (self.bbox, self.size, self.grid_size,
                                             self.tile_patterns)
    
def bbox_intersects(one, two):
    a_x0, a_y0, a_x1, a_y1 = one
    b_x0, b_y0, b_x1, b_y1 = two
    
    if (
        a_x0 < b_x1 and
        a_x1 > b_x0 and
        a_y0 < b_y1 and
        a_y1 > b_y0
        ): return True
    
    return False

def bbox_contains(one, two):
    a_x0, a_y0, a_x1, a_y1 = one
    b_x0, b_y0, b_x1, b_y1 = two
    
    if (
        a_x0 < b_x0 and
        a_x1 > b_x1 and
        a_y0 < b_y0 and
        a_y1 > b_y1
        ): return True
    
    return False

def deg_to_m(deg):
    return deg * (6378137 * 2 * math.pi) / 360

OGC_PIXLE_SIZE = 0.00028 #m/px

def ogc_scale_to_res(scale):
    return scale * OGC_PIXLE_SIZE
def res_to_ogc_scale(res):
    return res / OGC_PIXLE_SIZE

def resolution_range(min_res=None, max_res=None, max_scale=None, min_scale=None):
    if min_scale == max_scale == min_res == max_res == None:
        return ResolutionRange(None, None)
    if min_res or max_res:
        if not max_scale and not min_scale:
            return ResolutionRange(min_res, max_res)
    elif max_scale or min_scale:
        if not min_res and not max_res:
            min_res = ogc_scale_to_res(max_scale)
            max_res = ogc_scale_to_res(min_scale)
            return ResolutionRange(min_res, max_res)
            
    raise ValueError('requires either min_res/max_res or max_scale/min_scale')

class ResolutionRange(object):
    def __init__(self, min_res, max_res):
        self.min_res = min_res
        self.max_res = max_res
        
        if min_res and max_res:
            assert min_res > max_res
    
    def scale_denominator(self):
        min_scale = res_to_ogc_scale(self.max_res) if self.max_res else None
        max_scale = res_to_ogc_scale(self.min_res) if self.min_res else None
        return min_scale, max_scale
    
    def scale_hint(self):
        """
        Returns the min and max diagonal resolution.
        """
        min_res = self.min_res
        max_res = self.max_res
        if min_res:
            min_res = math.sqrt(2*min_res**2)
        if max_res:
            max_res = math.sqrt(2*max_res**2)
        return min_res, max_res
    
    def contains(self, bbox, size, srs):
        width, height = bbox_size(bbox)
        if srs.is_latlong:
            width = deg_to_m(width)
            height = deg_to_m(height)
        
        x_res = width/size[0]
        y_res = height/size[1]
        
        if self.min_res:
            min_res = self.min_res + 1e-6
            if min_res <= x_res or min_res <= y_res:
                return False
        if self.max_res:
            max_res = self.max_res - 1e-6
            if max_res > x_res or max_res > y_res:
                return False
        
        return True
    
    def __eq__(self, other):
        if not isinstance(other, ResolutionRange):
            return NotImplemented
        
        return (self.min_res == other.min_res
            and self.max_res == other.max_res)

    def __ne__(self, other):
        if not isinstance(other, ResolutionRange):
            return NotImplemented
        return not self == other

    def __repr__(self):
        return '<ResolutionRange(min_res=%.3f, max_res=%.3f)>' % (
            self.min_res, self.max_res)
    

def max_with_none(a, b):
    if a is None or b is None:
        return None
    else:
        return max(a, b)

def merge_resolution_range(a, b):
    if a and b:
        return ResolutionRange(max_with_none(a.min_res, b.min_res), min(a.max_res, b.max_res))
    return None
