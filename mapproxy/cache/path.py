# This file is part of the MapProxy project.
# Copyright (C) 2010-2016 Omniscale <http://omniscale.de>
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
from mapproxy.util.fs import ensure_directory
from mapproxy.request.base import NoCaseMultiDict


def location_funcs(layout):
    if layout == 'tc':
        return tile_location_tc, level_location
    elif layout == 'mp':
        return tile_location_mp, level_location
    elif layout == 'tms':
        return tile_location_tms, level_location
    elif layout == 'reverse_tms':
        return tile_location_reverse_tms, None
    elif layout == 'quadkey':
        return tile_location_quadkey, no_level_location
    elif layout == 'arcgis':
        return tile_location_arcgiscache, level_location_arcgiscache
    else:
        raise ValueError('unknown directory_layout "%s"' % layout)


def level_location(level, cache_dir, dimensions=None):
    """
    Return the path where all tiles for `level` will be stored.

    >>> os.path.abspath(level_location(2, '/tmp/cache')) == os.path.abspath('/tmp/cache/02')
    True
    """
    dim_path = dimensions_part(dimensions)

    if isinstance(level, str):
        return os.path.join(cache_dir, dim_path, level)
    else:
        return os.path.join(cache_dir, dim_path, "%02d" % level)


def dimensions_part(dimensions):
    """
    Return the subpath where all tiles for `dimensions` will be stored.
    Dimensions prefixed with "dim_" are sorted after the predefined elevation and time dimensions
    >>> dimensions_part({'time': '2020-08-25T00:00:00Z'})
    'time-2020-08-25T00:00:00Z'
    >>> dimensions_part({'time': '2020-08-25T00:00:00Z', 'dim_reference_time': '2020-08-25T00:00:00Z', 'dim_level': '700'})  # noqa
    'time-2020-08-25T00:00:00Z/dim_level-700/dim_reference_time-2020-08-25T00:00:00Z'

    """
    if dimensions:
        dims = NoCaseMultiDict(dimensions)
        predefined_dims, custom_dims = [], []
        for dim in dims.keys():
            (custom_dims if dim.startswith('dim_') else predefined_dims).append(dim)
        dim_keys = sorted(predefined_dims) + sorted(custom_dims)
        return os.path.join(*(map(lambda k: k + "-" + str(dims.get(k, 'default')), dim_keys)))
    else:
        return ""


def level_part(level):
    """
    Return the path where all tiles for `level` will be stored.

    >>> level_part(2)
    '02'
    >>> level_part('2')
    '2'
    """
    if isinstance(level, str):
        return level
    else:
        return "%02d" % level


def tile_location_tc(tile, cache_dir, file_ext, create_dir=False, dimensions=None,
                     directory_permissions=None):
    """
    Return the location of the `tile`. Caches the result as ``location``
    property of the `tile`.

    :param tile: the tile object
    :param create_dir: if True, create all necessary directories
    :return: the full filename of the tile

    >>> from mapproxy.cache.tile import Tile
    >>> tile_location_tc(Tile((3, 4, 2)), '/tmp/cache', 'png').replace('\\\\', '/')
    '/tmp/cache/02/000/000/003/000/000/004.png'
    """
    if tile.location is None:
        x, y, z = tile.coord

        parts = (cache_dir,
                 dimensions_part(dimensions),
                 level_part(z),
                 "%03d" % int(x / 1000000),
                 "%03d" % (int(x / 1000) % 1000),
                 "%03d" % (int(x) % 1000),
                 "%03d" % int(y / 1000000),
                 "%03d" % (int(y / 1000) % 1000),
                 "%03d.%s" % (int(y) % 1000, file_ext))
        tile.location = os.path.join(*parts)
    if create_dir:
        ensure_directory(tile.location, directory_permissions)
    return tile.location


def tile_location_mp(tile, cache_dir, file_ext, create_dir=False, dimensions=None,
                     directory_permissions=None):
    """
    Return the location of the `tile`. Caches the result as ``location``
    property of the `tile`.

    :param tile: the tile object
    :param create_dir: if True, create all necessary directories
    :return: the full filename of the tile

    >>> from mapproxy.cache.tile import Tile
    >>> tile_location_mp(Tile((3, 4, 2)), '/tmp/cache', 'png').replace('\\\\', '/')
    '/tmp/cache/02/0000/0003/0000/0004.png'
    >>> tile_location_mp(Tile((12345678, 98765432, 22)), '/tmp/cache', 'png').replace('\\\\', '/')
    '/tmp/cache/22/1234/5678/9876/5432.png'
    """
    if tile.location is None:
        x, y, z = tile.coord
        parts = (cache_dir,
                 dimensions_part(dimensions),
                 level_part(z),
                 "%04d" % int(x / 10000),
                 "%04d" % (int(x) % 10000),
                 "%04d" % int(y / 10000),
                 "%04d.%s" % (int(y) % 10000, file_ext))
        tile.location = os.path.join(*parts)
    if create_dir:
        ensure_directory(tile.location, directory_permissions)
    return tile.location


def tile_location_tms(tile, cache_dir, file_ext, create_dir=False, dimensions=None,
                      directory_permissions=None):
    """
    Return the location of the `tile`. Caches the result as ``location``
    property of the `tile`.

    :param tile: the tile object
    :param create_dir: if True, create all necessary directories
    :return: the full filename of the tile

    >>> from mapproxy.cache.tile import Tile
    >>> tile_location_tms(Tile((3, 4, 2)), '/tmp/cache', 'png').replace('\\\\', '/')
    '/tmp/cache/2/3/4.png'
    """
    if tile.location is None:
        x, y, z = tile.coord
        tile.location = os.path.join(
            cache_dir, dimensions_part(dimensions), level_part(str(z)),
            str(x), str(y) + '.' + file_ext
        )
    if create_dir:
        ensure_directory(tile.location, directory_permissions)
    return tile.location


def tile_location_reverse_tms(tile, cache_dir, file_ext, create_dir=False, dimensions=None,
                              directory_permissions=None):
    """
    Return the location of the `tile`. Caches the result as ``location``
    property of the `tile`.

    :param tile: the tile object
    :param create_dir: if True, create all necessary directories
    :return: the full filename of the tile

    >>> from mapproxy.cache.tile import Tile
    >>> tile_location_reverse_tms(Tile((3, 4, 2)), '/tmp/cache', 'png').replace('\\\\', '/')
    '/tmp/cache/4/3/2.png'
    """
    if tile.location is None:
        x, y, z = tile.coord
        tile.location = os.path.join(
            cache_dir, dimensions_part(dimensions), str(y), str(x), str(z) + '.' + file_ext
        )
    if create_dir:
        ensure_directory(tile.location, directory_permissions)
    return tile.location


def level_location_tms(level, cache_dir, dimensions=None):
    return level_location(str(level), cache_dir=cache_dir)


def tile_location_quadkey(tile, cache_dir, file_ext, create_dir=False, dimensions=None,
                          directory_permissions=None):
    """
    Return the location of the `tile`. Caches the result as ``location``
    property of the `tile`.

    :param tile: the tile object
    :param create_dir: if True, create all necessary directories
    :return: the full filename of the tile

    >>> from mapproxy.cache.tile import Tile
    >>> tile_location_quadkey(Tile((3, 4, 2)), '/tmp/cache', 'png').replace('\\\\', '/')
    '/tmp/cache/11.png'
    """
    if tile.location is None:
        x, y, z = tile.coord
        quadKey = ""
        for i in range(z, 0, -1):
            digit = 0
            mask = 1 << (i-1)
            if (x & mask) != 0:
                digit += 1
            if (y & mask) != 0:
                digit += 2
            quadKey += str(digit)
        tile.location = os.path.join(
            cache_dir, quadKey + '.' + file_ext
        )
    if create_dir:
        ensure_directory(tile.location, directory_permissions)
    return tile.location


def no_level_location(level, cache_dir, dimensions=None):
    # dummy for quadkey cache which stores all tiles in one directory
    raise NotImplementedError('cache does not have any level location')


def tile_location_arcgiscache(tile, cache_dir, file_ext, create_dir=False, dimensions=None,
                              directory_permissions=None):
    """
    Return the location of the `tile`. Caches the result as ``location``
    property of the `tile`.

    :param tile: the tile object
    :param create_dir: if True, create all necessary directories
    :return: the full filename of the tile

    >>> from mapproxy.cache.tile import Tile
    >>> tile_location_arcgiscache(Tile((1234567, 87654321, 9)), '/tmp/cache', 'png').replace('\\\\', '/')
    '/tmp/cache/L09/R05397fb1/C0012d687.png'
    """
    if tile.location is None:
        x, y, z = tile.coord
        parts = (cache_dir, 'L%02d' % z, 'R%08x' % y, 'C%08x.%s' % (x, file_ext))
        tile.location = os.path.join(*parts)
    if create_dir:
        ensure_directory(tile.location, directory_permissions)
    return tile.location


def level_location_arcgiscache(z, cache_dir, dimensions=None):
    return level_location('L%02d' % z, cache_dir=cache_dir, dimensions=dimensions)
