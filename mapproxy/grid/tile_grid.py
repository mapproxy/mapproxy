import math

from mapproxy.grid import NoTiles, GridError, _create_tile_list, default_bboxs, grid_bbox, origin_from_string
from mapproxy.grid.resolutions import aligned_resolutions, resolutions, pyramid_res_level, get_resolution
from mapproxy.srs import get_epsg_num, SRS
from mapproxy.util.bbox import bbox_equals, bbox_intersects, merge_bbox
from mapproxy.util.collections import ImmutableDictList

geodetic_epsg_codes = [4326]


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


def tile_grid(srs=None, bbox=None, bbox_srs=None, tile_size=(256, 256),
              res=None, res_factor=2.0, threshold_res=None,
              num_levels=None, min_res=None, max_res=None,
              stretch_factor=1.15, max_shrink_factor=4.0,
              align_with=None, origin='ll', name=None
              ):
    """
    This function creates a new TileGrid.
    """
    if srs is None:
        srs = 'EPSG:900913'
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

    origin = origin_from_string(origin)

    return TileGrid(srs, bbox=bbox, tile_size=tile_size, res=res, threshold_res=threshold_res,
                    stretch_factor=stretch_factor, max_shrink_factor=max_shrink_factor,
                    origin=origin, name=name)


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

    spheroid_a = 6378137.0  # for 900913
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
        if isinstance(srs, (int, str)):
            srs = SRS(srs)
        self.srs = srs
        self.tile_size = tile_size
        self.origin = origin_from_string(origin)
        self.name = name

        if self.origin == 'ul':
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

        self.threshold_res = None
        if threshold_res:
            self.threshold_res = sorted(threshold_res)

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
            thresholds = self.threshold_res[:]
            threshold = thresholds.pop()
            # skip thresholds above first res
            while threshold > prev_l_res and thresholds:
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
                # Use previous level that was within stretch_factor,
                # but only if this level res is smaller then res.
                # This fixes selection for resolutions that are closer together then stretch_factor.
                #
                if l_res < res:
                    return threshold_result

            if l_res <= res*self.stretch_factor:
                # l_res within stretch_factor
                # remember this level, check for thresholds or better res in next loop
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

    def flip_tile_coord(self, tile_coord):
        """
        Flip the tile coord on the y-axis. (Switch between bottom-left and top-left
        origin.)

        >>> grid = TileGrid(SRS(900913))
        >>> grid.flip_tile_coord((0, 1, 1))
        (0, 0, 1)
        >>> grid.flip_tile_coord((1, 3, 2))
        (1, 0, 2)
        """
        (x, y, z) = tile_coord
        return (x, self.grid_sizes[z][1]-1-y, z)

    def supports_access_with_origin(self, origin):
        if origin_from_string(origin) == self.origin:
            return True

        # check for each level if the top and bottom coordinates of the tiles
        # match the bbox of the grid. only in this case we can flip y-axis
        # without any issues

        # allow for some rounding errors in the _tiles_bbox calculations
        delta = max(abs(self.bbox[1]), abs(self.bbox[3])) / 1e12

        for level, grid_size in enumerate(self.grid_sizes):
            level_bbox = self._tiles_bbox([(0, 0, level),
                                           (grid_size[0] - 1, grid_size[1] - 1, level)])

            if abs(self.bbox[1] - level_bbox[1]) > delta or abs(self.bbox[3] - level_bbox[3]) > delta:
                return False
        return True

    def origin_tile(self, level, origin):
        assert self.supports_access_with_origin(origin), 'tile origins are incompatible'
        tile = (0, 0, level)

        if origin_from_string(origin) == self.origin:
            return tile

        return self.flip_tile_coord(tile)

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
        xs = list(range(x0, x1+1))
        if self.flipped_y_axis:
            y0, y1 = y1, y0
            ys = list(range(y0, y1+1))
        else:
            ys = list(range(y1, y0-1, -1))

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
        >>> grid.limit_tile((-1, 0, 2)) is None
        True
        >>> grid.limit_tile((1, 2, 1)) is None
        True
        >>> grid.limit_tile((1, 2, 2))
        (1, 2, 2)
        """
        x, y, z = tile_coord
        if isinstance(z, str):
            if z not in self.grid_sizes:
                return None
        elif z < 0 or z >= self.levels:
            return None
        grid = self.grid_sizes[z]
        if x < 0 or y < 0 or x >= grid[0] or y >= grid[1]:
            return None
        return x, y, z

    def __repr__(self):
        return '%s(%r, (%.4f, %.4f, %.4f, %.4f),...)' % (
            self.__class__.__name__, self.srs, self.bbox[0], self.bbox[1], self.bbox[2], self.bbox[3])

    def is_subset_of(self, other):
        """
        Returns ``True`` if every tile in `self` is present in `other`.
        Tile coordinates might differ and `other` may contain more
        tiles (more levels, larger bbox).
        """
        if self.srs != other.srs:
            return False

        if self.tile_size != other.tile_size:
            return False

        # check if all level tiles from self align with (affected)
        # tiles from other
        for self_level, self_level_res in self.resolutions.iteritems():
            level_size = (
                self.grid_sizes[self_level][0] * self.tile_size[0],
                self.grid_sizes[self_level][1] * self.tile_size[1]
            )
            level_bbox = self._tiles_bbox([
                (0, 0, self_level),
                (self.grid_sizes[self_level][0] - 1, self.grid_sizes[self_level][1] - 1, self_level)
            ])

            try:
                bbox, level = other.get_affected_bbox_and_level(level_bbox, level_size)
            except NoTiles:
                return False
            try:
                bbox, grid_size, tiles = other.get_affected_level_tiles(level_bbox, level)
            except GridError:
                return False

            if other.resolution(level) != self_level_res:
                return False
            if not bbox_equals(bbox, level_bbox):
                return False

        return True


def is_float(x):
    try:
        float(x)
        return True
    except TypeError:
        return False
