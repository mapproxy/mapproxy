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

from __future__ import print_function
import logging

import os
import time
import operator
from functools import reduce

from mapproxy.cache.dummy import DummyCache
from mapproxy.config import abspath
from mapproxy.config.coverage import load_coverage
from mapproxy.config.loader import ConfigurationError
from mapproxy.seed.util import bidict
from mapproxy.seed.seeder import SeedTask, CleanupTask
from mapproxy.seed.spec import validate_seed_conf
from mapproxy.util.bbox import TransformationError
from mapproxy.util.coverage import MultiCoverage, BBOXCoverage
from mapproxy.util.geom import GeometryError, EmptyGeometryError, CoverageReadError
from mapproxy.util.py import memoize
from mapproxy.util.times import timestamp_from_isodate, timestamp_before
from mapproxy.util.yaml import load_yaml_file, YAMLError


class SeedConfigurationError(ConfigurationError):
    pass


class EmptyCoverageError(Exception):
    pass


log = logging.getLogger('mapproxy.seed.config')


def load_seed_tasks_conf(seed_conf_filename, mapproxy_conf):
    try:
        conf = load_yaml_file(seed_conf_filename)
    except YAMLError as ex:
        raise SeedConfigurationError(ex)

    if 'views' in conf:
        raise Exception('The old seeding config style is no longer supported. Please refer to the documentation.')
    else:
        errors, informal_only = validate_seed_conf(conf)
        for error in errors:
            log.warning(error)
        if not informal_only:
            raise SeedConfigurationError('invalid configuration')
        seed_conf = SeedingConfiguration(conf, mapproxy_conf=mapproxy_conf)
    return seed_conf


class SeedingConfiguration(object):
    def __init__(self, seed_conf, mapproxy_conf):
        self.conf = seed_conf
        self.mapproxy_conf = mapproxy_conf
        self.grids = bidict((name, grid_conf.tile_grid()) for name, grid_conf in self.mapproxy_conf.grids.items())

    @memoize
    def coverage(self, name):
        coverage_conf = (self.conf.get('coverages') or {}).get(name)
        if coverage_conf is None:
            raise SeedConfigurationError('coverage %s not found. available coverages: %s' % (
                name, ','.join((self.conf.get('coverages') or {}).keys())))

        try:
            coverage = load_coverage(coverage_conf)
        except CoverageReadError as ex:
            raise SeedConfigurationError("can't load coverage '%s'. %s" % (name, ex))
        except GeometryError as ex:
            raise SeedConfigurationError("invalid geometry in coverage '%s'. %s" % (name, ex))
        except EmptyGeometryError as ex:
            raise EmptyCoverageError("coverage '%s' contains no geometries. %s" % (name, ex))
        except Exception:
            raise Exception(f"can't load coverage '{name}'")

        # without extend we have an empty coverage
        if not coverage.extent.llbbox:
            raise EmptyCoverageError("coverage '%s' contains no geometries." % name)
        return coverage

    def cache(self, cache_name):
        cache = {}
        if cache_name not in self.mapproxy_conf.caches:
            raise SeedConfigurationError('cache %s not found. available caches: %s' % (
                cache_name, ','.join(self.mapproxy_conf.caches.keys())))
        for tile_grid, extent, tile_mgr in self.mapproxy_conf.caches[cache_name].caches():
            if isinstance(tile_mgr.cache, DummyCache):
                raise SeedConfigurationError('can\'t seed cache %s (disable_storage: true)' %
                                             cache_name)
            grid_name = self.grids[tile_grid]
            cache[grid_name] = tile_mgr
        return cache

    def seed_tasks_names(self):
        seeds = self.conf.get('seeds') or {}
        return list(seeds.keys())

    def cleanup_tasks_names(self):
        cleanups = self.conf.get('cleanups') or {}
        return list(cleanups.keys())

    def seeds(self, names=None):
        """
        Return seed tasks.
        """
        tasks = []
        if names is None:
            names = (self.conf.get('seeds') or {}).keys()

        for seed_name in names:
            seed_conf = self.conf['seeds'][seed_name]
            seed_conf = SeedConfiguration(seed_name, seed_conf, self)
            for task in seed_conf.seed_tasks():
                tasks.append(task)
        return tasks

    def cleanups(self, names=None):
        """
        Return cleanup tasks.
        """
        tasks = []
        if names is None:
            names = (self.conf.get('cleanups') or {}).keys()

        for cleanup_name in names:
            cleanup_conf = self.conf['cleanups'][cleanup_name]
            cleanup_conf = CleanupConfiguration(cleanup_name, cleanup_conf, self)
            for task in cleanup_conf.cleanup_tasks():
                tasks.append(task)
        return tasks


class ConfigurationBase(object):
    def __init__(self, name, conf, seeding_conf):
        self.name = name
        self.conf = conf
        self.seeding_conf = seeding_conf

        self.coverage = self._coverages()
        self.caches = self._caches()
        self.grids = self._grids(self.caches)
        self.levels = levels_from_options(conf)

    def _coverages(self):
        coverage = None
        if 'coverages' in self.conf:
            try:
                coverages = [self.seeding_conf.coverage(c) for c in self.conf.get('coverages', {})]
            except EmptyCoverageError:
                return False
            if len(coverages) == 1:
                coverage = coverages[0]
            else:
                coverage = MultiCoverage(coverages)
        return coverage

    def _grids(self, caches):
        grids = []

        if 'grids' in self.conf:
            # grids available for all caches
            available_grids = reduce(operator.and_, (set(cache) for cache in caches.values()))
            for grid_name in self.conf['grids']:
                if grid_name not in available_grids:
                    raise SeedConfigurationError('%s not defined for caches' % grid_name)
                grids.append(grid_name)
        else:
            # check that all caches have the same grids configured
            last = []
            for cache_grids in [cache.keys() for cache in caches.values()]:
                if not last:
                    last = cache_grids
                else:
                    if last != cache_grids:
                        raise SeedConfigurationError('caches in same seed task require identical grids')
            grids = list(last or [])
        return grids

    def _caches(self):
        """
        Returns a dictionary with all caches for this seed.

        e.g.: {'seed1': {'grid1': tilemanager1, 'grid2': tilemanager2}}
        """
        caches = {}
        for cache_name in self.conf.get('caches', []):
            caches[cache_name] = self.seeding_conf.cache(cache_name)
        return caches


class SeedConfiguration(ConfigurationBase):
    def __init__(self, name, conf, seeding_conf):
        ConfigurationBase.__init__(self, name, conf, seeding_conf)

        self.refresh_all = False
        self.refresh_timestamp = None
        if 'refresh_before' in self.conf:
            self.refresh_timestamp = before_timestamp_from_options(self.conf['refresh_before'])
        else:
            self.refresh_all = True

    def seed_tasks(self):
        for grid_name in self.grids:
            for cache_name, cache in self.caches.items():
                tile_manager = cache[grid_name]
                grid = self.seeding_conf.grids[grid_name]
                if self.coverage is False:
                    coverage = False
                elif self.coverage:
                    coverage = self.coverage.transform_to(grid.srs)
                else:
                    coverage = BBOXCoverage(grid.bbox, grid.srs)

                try:
                    if coverage is not False:
                        coverage.extent.llbbox
                except TransformationError:
                    raise SeedConfigurationError('%s: coverage transformation error' % self.name)

                if self.levels:
                    levels = self.levels.for_grid(grid)
                else:
                    levels = list(range(0, grid.levels))

                if not tile_manager.cache.supports_timestamp:
                    self.refresh_all = True

                md = dict(name=self.name, cache_name=cache_name, grid_name=grid_name)

                if tile_manager.rescale_tiles:
                    if tile_manager.rescale_tiles > 0:
                        levels = levels[::-1]
                    for level in levels:
                        yield SeedTask(md, tile_manager, [level], self.refresh_timestamp, self.refresh_all, coverage)
                else:
                    yield SeedTask(md, tile_manager, levels, self.refresh_timestamp, self.refresh_all, coverage)


class CleanupConfiguration(ConfigurationBase):
    def __init__(self, name, conf, seeding_conf):
        ConfigurationBase.__init__(self, name, conf, seeding_conf)
        self.init_time = time.time()

        self.remove_all = False
        self.remove_timestamp = self.init_time  # this should not remove
        # fresh seeded tiles, since this should be configured before seeding

        if self.conf.get('remove_all') is True:
            self.remove_all = True
        elif 'remove_before' in self.conf:
            self.remove_timestamp = before_timestamp_from_options(self.conf['remove_before'])

    def cleanup_tasks(self):
        for grid_name in self.grids:
            for cache_name, cache in self.caches.items():
                tile_manager = cache[grid_name]
                grid = self.seeding_conf.grids[grid_name]
                if self.coverage is False:
                    coverage = False
                    complete_extent = False
                elif self.coverage:
                    coverage = self.coverage.transform_to(grid.srs)
                    complete_extent = False
                else:
                    coverage = BBOXCoverage(grid.bbox, grid.srs)
                    complete_extent = True

                try:
                    if coverage is not False:
                        coverage.extent.llbbox
                except TransformationError:
                    raise SeedConfigurationError('%s: coverage transformation error' % self.name)

                if self.levels:
                    levels = self.levels.for_grid(grid)
                else:
                    levels = list(range(0, grid.levels))

                if not tile_manager.cache.supports_timestamp:
                    # for caches without timestamp support (like MBTiles)
                    if self.remove_timestamp is self.init_time:
                        # remove everything
                        self.remove_all = True
                    else:
                        raise SeedConfigurationError(
                            "cleanup does not support remove_before for '%s'"
                            " because cache '%s' does not support timestamps" % (self.name, cache_name))
                md = dict(name=self.name, cache_name=cache_name, grid_name=grid_name)
                yield CleanupTask(md, tile_manager, levels, self.remove_timestamp, remove_all=self.remove_all,
                                  coverage=coverage, complete_extent=complete_extent)


def levels_from_options(conf):
    levels = conf.get('levels')
    if levels:
        if isinstance(levels, list):
            return LevelsList(levels)
        from_level = levels.get('from')
        to_level = levels.get('to')
        return LevelsRange((from_level, to_level))
    resolutions = conf.get('resolutions')
    if resolutions:
        if isinstance(resolutions, list):
            return LevelsResolutionList(resolutions)
        from_res = resolutions.get('from')
        to_res = resolutions.get('to')
        return LevelsResolutionRange((from_res, to_res))
    return None


def before_timestamp_from_options(conf):
    """
    >>> import time
    >>> t = before_timestamp_from_options({'hours': 4})
    >>> time.time() - t - 4 * 60 * 60 < 1
    True
    """
    if 'time' in conf:
        try:
            return timestamp_from_isodate(conf['time'])
        except ValueError:
            raise SeedConfigurationError(
                "can't parse time '%s'. should be ISO time string" % (conf["time"], ))
    if 'mtime' in conf:
        datasource = abspath(conf['mtime'])
        try:
            return os.path.getmtime(datasource)
        except OSError as ex:
            raise SeedConfigurationError(
                "can't parse last modified time from file '%s'." % (datasource, ), ex)
    deltas = {}
    for delta_type in ('weeks', 'days', 'hours', 'minutes', 'seconds'):
        deltas[delta_type] = conf.get(delta_type, 0)
    return timestamp_before(**deltas)


class LevelsList(object):
    def __init__(self, levels=None):
        self.levels = levels

    def for_grid(self, grid):
        uniqe_valid_levels = set(x for x in self.levels if 0 <= x <= (grid.levels-1))
        return sorted(uniqe_valid_levels)


class LevelsRange(object):
    def __init__(self, level_range=None):
        self.level_range = level_range

    def for_grid(self, grid):
        start, stop = self.level_range
        if start is None:
            start = 0
        if stop is None:
            stop = 999

        stop = min(stop, grid.levels-1)

        return list(range(start, stop+1))


class LevelsResolutionRange(object):
    def __init__(self, res_range=None):
        self.res_range = res_range

    def for_grid(self, grid):
        start, stop = self.res_range
        if start is None:
            start = 0
        else:
            start = grid.closest_level(start)

        if stop is None:
            stop = grid.levels-1
        else:
            stop = grid.closest_level(stop)

        return list(range(start, stop+1))


class LevelsResolutionList(object):
    def __init__(self, resolutions=None):
        self.resolutions = resolutions

    def for_grid(self, grid):
        levels = set(grid.closest_level(res) for res in self.resolutions)
        return sorted(levels)
