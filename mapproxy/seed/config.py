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

from __future__ import with_statement

import sys
import time
import operator

from mapproxy.config.loader import ConfigurationError
from mapproxy.config.coverage import load_coverage
from mapproxy.srs import SRS
from mapproxy.util import memoize, timestamp_from_isodate, timestamp_before
from mapproxy.util.geom import MultiCoverage, BBOXCoverage
from mapproxy.util.yaml import load_yaml_file, YAMLError
from mapproxy.seed.util import bidict
from mapproxy.seed.seeder import SeedTask, CleanupTask
from mapproxy.seed.spec import validate_seed_conf


class SeedConfigurationError(ConfigurationError):
    pass


# TODO
# def check_shapely():
#     if not shapely_present:
#         raise ImportError('could not import shapley.'
#             ' required for polygon/ogr seed areas')


import logging
log = logging.getLogger('mapproxy.seed.config')

def load_seed_tasks_conf(seed_conf_filename, mapproxy_conf):
    try:
        conf = load_yaml_file(seed_conf_filename)
    except YAMLError, ex:
        raise SeedConfigurationError(ex)
    
    if 'views' in conf:
        # TODO: deprecate old config
        seed_conf = LegacySeedingConfiguration(conf, mapproxy_conf=mapproxy_conf)
    else:
        errors, informal_only = validate_seed_conf(conf)
        for error in errors:
            log.warn(error)
        if not informal_only:
            raise SeedConfigurationError('invalid configuration')
        seed_conf = SeedingConfiguration(conf, mapproxy_conf=mapproxy_conf)
    return seed_conf

class LegacySeedingConfiguration(object):
    """
    Read old seed.yaml configuration (with seed and views).
    """
    def __init__(self, seed_conf, mapproxy_conf):
        self.conf = seed_conf
        self.mapproxy_conf = mapproxy_conf
        self.grids = bidict((name, grid_conf.tile_grid()) for name, grid_conf in self.mapproxy_conf.grids.iteritems())
        self.seed_tasks = []
        self.cleanup_tasks = []
        self._init_tasks()
        
    def _init_tasks(self):
        for cache_name, options in self.conf['seeds'].iteritems():
            remove_before = None
            if 'remove_before' in options:
                remove_before = before_timestamp_from_options(options['remove_before'])
            try:
                caches = self.mapproxy_conf.caches[cache_name].caches()
            except KeyError:
                print >>sys.stderr, 'error: cache %s not found. available caches: %s' % (
                    cache_name, ','.join(self.mapproxy_conf.caches.keys()))
                return
            caches = dict((grid, tile_mgr) for grid, extent, tile_mgr in caches)
            for view in options['views']:
                view_conf = self.conf['views'][view]
                coverage = load_coverage(view_conf)

                cache_srs = view_conf.get('srs', None)
                if cache_srs is not None:
                    cache_srs = [SRS(s) for s in cache_srs]
            
                level = view_conf.get('level', None)
                assert len(level) == 2
                
                for grid, tile_mgr in caches.iteritems():
                    if cache_srs and grid.srs not in cache_srs: continue
                    md = dict(name=view, cache_name=cache_name, grid_name=self.grids[grid])
                    levels = range(level[0], level[1]+1)
                    if coverage:
                        seed_coverage = coverage.transform_to(grid.srs)
                    else:
                        seed_coverage = BBOXCoverage(grid.bbox, grid.srs)
                    
                    self.seed_tasks.append(SeedTask(md, tile_mgr, levels, remove_before, seed_coverage))
            
                    if remove_before:
                        levels = range(grid.levels)
                        complete_extent = bool(coverage)
                        self.cleanup_tasks.append(CleanupTask(md, tile_mgr, levels, remove_before,
                            seed_coverage, complete_extent=complete_extent))
                        
    def seed_tasks_names(self):
        return self.conf['seeds'].keys()
    
    def cleanup_tasks_names(self):
        return self.conf['seeds'].keys()

    def seeds(self, names=None):
        if names is None:
            return self.seed_tasks
        else:
            return [t for t in self.seed_tasks if t.md['name'] in names]
    
    def cleanups(self, names=None):
        if names is None:
            return self.cleanup_tasks
        else:
            return [t for t in self.cleanup_tasks if t.md['name'] in names]

class SeedingConfiguration(object):
    def __init__(self, seed_conf, mapproxy_conf):
        self.conf = seed_conf
        self.mapproxy_conf = mapproxy_conf
        self.grids = bidict((name, grid_conf.tile_grid()) for name, grid_conf in self.mapproxy_conf.grids.iteritems())

    @memoize
    def coverage(self, name):
        coverage_conf = self.conf['coverages'].get(name)
        if coverage_conf is None:
            raise ValueError('no coverage %s configured' % name)
        
        return load_coverage(coverage_conf)
    
    def cache(self, cache_name):
        cache = {}
        if cache_name not in self.mapproxy_conf.caches:
            raise SeedConfigurationError('cache %s not found. available caches: %s' % (
                cache_name, ','.join(self.mapproxy_conf.caches.keys())))
        for tile_grid, extent, tile_mgr in self.mapproxy_conf.caches[cache_name].caches():
            grid_name = self.grids[tile_grid]
            cache[grid_name] = tile_mgr
        return cache
    
    def seed_tasks_names(self):
        return self.conf.get('seeds', {}).keys()
    
    def cleanup_tasks_names(self):
        return self.conf.get('cleanups', {}).keys()
    
    def seeds(self, names=None):
        """
        Return seed tasks.
        """
        tasks = []
        for seed_name, seed_conf in self.conf.get('seeds', {}).iteritems():
            if names is not None and seed_name not in names: continue
            seed_conf = SeedConfiguration(seed_name, seed_conf, self)
            for task in seed_conf.seed_tasks():
                tasks.append(task)
        return tasks
        
    def cleanups(self, names=None):
        """
        Return cleanup tasks.
        """
        tasks = []
        for cleanup_name, cleanup_conf in self.conf.get('cleanups', {}).iteritems():
            if names is not None and cleanup_name not in names: continue
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
            coverages = [self.seeding_conf.coverage(c) for c in self.conf['coverages']]
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
            for cache_grids in (set(cache.iterkeys()) for cache in caches.itervalues()):
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
        
        self.refresh_timestamp = None
        if 'refresh_before' in self.conf:
            self.refresh_timestamp = before_timestamp_from_options(self.conf['refresh_before'])
    
    def seed_tasks(self):
        for grid_name in self.grids:
            for cache_name, cache in self.caches.iteritems():
                tile_manager = cache[grid_name]
                grid = self.seeding_conf.grids[grid_name]
                if self.coverage:
                    coverage = self.coverage.transform_to(grid.srs)
                else:
                    coverage = BBOXCoverage(grid.bbox, grid.srs)
                if self.levels:
                    levels = self.levels.for_grid(grid)
                else:
                    levels = list(xrange(0, grid.levels))
                
                if not tile_manager.cache.supports_timestamp:
                    if self.refresh_timestamp:
                        # remove everything
                        self.refresh_timestamp = 0
                
                md = dict(name=self.name, cache_name=cache_name, grid_name=grid_name)
                yield SeedTask(md, tile_manager, levels, self.refresh_timestamp, coverage)

class CleanupConfiguration(ConfigurationBase):
    def __init__(self, name, conf, seeding_conf):
        ConfigurationBase.__init__(self, name, conf, seeding_conf)
        self.init_time = time.time()
        
        if 'remove_before' in self.conf:
            self.remove_timestamp = before_timestamp_from_options(self.conf['remove_before'])
        else:
            # use now as remove_before date. this should not remove
            # fresh seeded tiles, since this should be configured before seeding
            self.remove_timestamp = self.init_time
    
    def cleanup_tasks(self):
        for grid_name in self.grids:
            for cache_name, cache in self.caches.iteritems():
                tile_manager = cache[grid_name]
                grid = self.seeding_conf.grids[grid_name]
                if self.coverage:
                    coverage = self.coverage.transform_to(grid.srs)
                    complete_extent = False
                else:
                    coverage = BBOXCoverage(grid.bbox, grid.srs)
                    complete_extent = True
                if self.levels:
                    levels = self.levels.for_grid(grid)
                else:
                    levels = list(xrange(0, grid.levels))
                
                if not tile_manager.cache.supports_timestamp:
                    # for caches without timestamp support (like MBTiles)
                    if self.remove_timestamp is self.init_time:
                        # remove everything
                        self.remove_timestamp = 0
                    else:
                        raise SeedConfigurationError("cleanup does not support remove_before for '%s'"
                            " because cache '%s' does not support timestamps" % (self.name, cache_name))
                md = dict(name=self.name, cache_name=cache_name, grid_name=grid_name)
                yield CleanupTask(md, tile_manager, levels, self.remove_timestamp, 
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
    deltas = {}
    for delta_type in ('weeks', 'days', 'hours', 'minutes'):
        deltas[delta_type] = conf.get(delta_type, 0)
    return timestamp_before(**deltas)


class LevelsList(object):
    def __init__(self, levels=None):
        self.levels = levels
    
    def for_grid(self, grid):
        uniqe_valid_levels = set(l for l in self.levels if 0 <= l <= (grid.levels-1))
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
        
        return list(xrange(start, stop+1))

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
        
        return list(xrange(start, stop+1))
        
class LevelsResolutionList(object):
    def __init__(self, resolutions=None):
        self.resolutions = resolutions
    
    def for_grid(self, grid):
        levels = set(grid.closest_level(res) for res in self.resolutions)
        return sorted(levels)

