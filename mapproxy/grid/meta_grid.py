from mapproxy.grid import _create_tile_list, GridError


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

        >>> from mapproxy.grid.tile_grid import TileGrid
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

        >>> from mapproxy.grid.tile_grid import TileGrid
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
            ys = range(miny, maxy+1)
        else:
            ys = range(maxy, miny-1, -1)
        xs = range(minx, maxx+1)

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
        >>> from mapproxy.grid.tile_grid import TileGrid
        >>> mgrid = MetaGrid(grid=TileGrid(), meta_size=(2, 2))
        >>> mgrid._meta_tile_list((0, 1, 3), (2, 2))
        [(0, 1, 3), (1, 1, 3), (0, 0, 3), (1, 0, 3)]
        """
        minx, miny, z = self.main_tile(main_tile)
        maxx = minx + tile_grid[0] - 1
        maxy = miny + tile_grid[1] - 1
        if self.grid.flipped_y_axis:
            ys = range(miny, maxy+1)
        else:
            ys = range(maxy, miny-1, -1)
        xs = range(minx, maxx+1)

        return list(_create_tile_list(xs, ys, z, self.grid.grid_sizes[z]))

    def _tiles_pattern(self, grid_size, buffers, tile=None, tiles=None):
        """
        Returns the tile pattern for the given list of tiles.
        The result contains for each tile the ``tile_coord`` and the upper-left
        pixel coordinate of the tile in the meta tile image.

        >>> from mapproxy.grid.tile_grid import TileGrid
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

        >>> from mapproxy.grid.tile_grid import TileGrid
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

        xs = list(range(x0, x1+1, meta_size[0]))
        if self.grid.flipped_y_axis:
            y0, y1 = y1, y0
            ys = list(range(y0, y1+1, meta_size[1]))
        else:
            ys = list(range(y1, y0-1, -meta_size[1]))

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
