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

from __future__ import with_statement, division
import sys
import os
import math
import time
import datetime

import yaml

from mapproxy.config import base_config
from mapproxy.config.coverage import load_coverage
from mapproxy.config.loader import ProxyConfiguration
from mapproxy.srs import SRS
from mapproxy.grid import MetaGrid, bbox_intersects, bbox_contains
from mapproxy.source import SourceError
from mapproxy.util import (
    cleanup_directory,
    timestamp_before,
    timestamp_from_isodate,
    local_base_config,
)

try:
    from mapproxy.util.geom import (
        transform_geometry,
        bbox_polygon,
    )
except ImportError:
    shapely_present = False
else:
    shapely_present = True


NONE = 0
CONTAINS = -1
INTERSECTS = 1

# do not use multiprocessing on windows, it blows
# no lambdas, no anonymous functions/classes, no base_config(), etc.
if sys.platform == 'win32':
    import Queue
    import threading
    proc_class = threading.Thread
    queue_class = Queue.Queue
else:
    import multiprocessing
    proc_class = multiprocessing.Process
    queue_class = multiprocessing.Queue


class SeedPool(object):
    """
    Manages multiple SeedWorker.
    """
    def __init__(self, cache, size=2, dry_run=False):
        self.tiles_queue = queue_class(32)
        self.cache = cache
        self.dry_run = dry_run
        self.procs = []
        conf = base_config()
        for _ in xrange(size):
            worker = SeedWorker(cache, self.tiles_queue, conf, dry_run=dry_run)
            worker.start()
            self.procs.append(worker)
    
    def seed(self, tiles, progress):
        self.tiles_queue.put((tiles, progress))
    
    def stop(self):
        for _ in xrange(len(self.procs)):
            self.tiles_queue.put((None, None))
        
        for proc in self.procs:
            proc.join()


class SeedWorker(proc_class):
    def __init__(self, tile_mgr, tiles_queue, conf, dry_run=False):
        proc_class.__init__(self)
        proc_class.daemon = True
        self.tile_mgr = tile_mgr
        self.tiles_queue = tiles_queue
        self.conf = conf
        self.dry_run = dry_run
    def run(self):
        with local_base_config(self.conf):
            while True:
                tiles, progress = self.tiles_queue.get()
                if tiles is None:
                    return
                print '[%s] %6.2f%% %s \tETA: %s\r' % (
                    timestamp(), progress[1]*100, progress[0],
                    progress[2]
                ),
                sys.stdout.flush()
                if not self.dry_run:
                    exp_backoff(self.tile_mgr.load_tile_coords, args=(tiles,),
                                exceptions=(SourceError, IOError))

class ETA(object):
    def __init__(self):
        self.avgs = []
        self.start_time = time.time()
        self.progress = 0.0
        self.ticks = 1000

    def update(self, progress):
        self.progress = progress
        if (self.progress*self.ticks-1) > len(self.avgs):
            self.avgs.append((time.time()-self.start_time))
            self.start_time = time.time()

    def eta_string(self):
        timestamp = self.eta()
        if timestamp is None:
            return 'N/A'
        return time.strftime('%Y-%m-%d-%H:%M:%S', time.localtime(timestamp))

    def eta(self):
        if not self.avgs: return
        count = 0
        avg_sum = 0
        for i, avg in enumerate(self.avgs):
            multiplicator = (i+1)**1.2
            count += multiplicator
            avg_sum += avg*multiplicator
        return time.time() + (1-self.progress) * (avg_sum/count)*self.ticks

    def __str__(self):
        return self.eta_string()


class Seeder(object):
    def __init__(self, tile_mgr, task, seed_pool, skip_geoms_for_last_levels=0):
        self.tile_mgr = tile_mgr
        self.task = task
        self.seed_pool = seed_pool
        self.skip_geoms_for_last_levels = skip_geoms_for_last_levels
        
        num_seed_levels = task.max_level - task.start_level + 1
        self.report_till_level = task.start_level + int(num_seed_levels * 0.7)
        meta_size = tile_mgr.meta_grid.meta_size if tile_mgr.meta_grid else (1, 1)
        self.grid = MetaGrid(tile_mgr.grid, meta_size=meta_size, meta_buffer=0)
        self.progress = 0.0
        self.eta = ETA()
        self.count = 0
        

    def seed(self):
        self._seed(self.task.bbox, self.task.start_level)
        self.report_progress(self.task.start_level, self.task.bbox)

    def _seed(self, cur_bbox, level, progess_str='', progress=1.0, all_subtiles=False):
        """
        :param cur_bbox: the bbox to seed in this call
        :param level: the current seed level
        :param all_subtiles: seed all subtiles and do not check for
                             intersections with bbox/geom
        """
        bbox_, tiles_, subtiles = self.grid.get_affected_level_tiles(cur_bbox, level)
        
        if level == self.task.max_level-self.skip_geoms_for_last_levels:
            # do not filter in last levels
            all_subtiles = True
        sub_seeds, total_sub_seeds = self._filter_subtiles(subtiles, all_subtiles)
        
        if level <= self.report_till_level:
            self.report_progress(level, cur_bbox)
        
        if level < self.task.max_level:
            if sub_seeds:
                progress = progress / len(sub_seeds)
                for i, (subtile_, sub_bbox, intersection) in enumerate(sub_seeds):
                    sub_bbox = limit_sub_bbox(cur_bbox, sub_bbox)
                    cur_progess_str = progess_str + status_symbol(i, total_sub_seeds)
                    all_subtiles = True if intersection == CONTAINS else False
                    self._seed(sub_bbox, level+1, cur_progess_str,
                               all_subtiles=all_subtiles, progress=progress)
        else:
            self.progress += progress
        
        self.eta.update(self.progress)
        
        not_cached_tiles = self.not_cached(sub_seeds)
        if not_cached_tiles:
            self.count += len(not_cached_tiles)
            self.seed_pool.seed(not_cached_tiles,
                (progess_str, self.progress, self.eta))
        
        return sub_seeds
    
    def not_cached(self, tiles):
        return [tile for tile, _bbox, _intersection in tiles
                    if tile is not None and
                        not self.tile_mgr.is_cached(tile)]
    
    def report_progress(self, level, bbox):
        print '[%s] %2s %6.2f%% %s (#%d) ETA: %s' % (
            timestamp(), level, self.progress*100,
            format_bbox(bbox), self.count, self.eta)
        sys.stdout.flush()
    
    def _filter_subtiles(self, subtiles, all_subtiles):
        """
        Return all sub tiles that intersect the 
        """
        sub_seeds = []
        total_sub_seeds = 0
        for subtile in subtiles:
            total_sub_seeds += 1
            if subtile is None: continue
            sub_bbox = self.grid.meta_tile(subtile).bbox
            intersection = CONTAINS if all_subtiles else self.task.intersects(sub_bbox)
            if intersection:
                sub_seeds.append((subtile, sub_bbox, intersection))
        return sub_seeds, total_sub_seeds


class CacheSeeder(object):
    """
    Seed multiple caches with the same option set.
    """
    def __init__(self, caches, remove_before, dry_run=False, concurrency=2,
                 skip_geoms_for_last_levels=0):
        self.remove_before = remove_before
        self.dry_run = dry_run
        self.caches = caches
        self.concurrency = concurrency
        self.seeded_caches = []
        self.skip_geoms_for_last_levels = skip_geoms_for_last_levels
    
    def seed_view(self, bbox, level, bbox_srs, cache_srs, geom=None):
        for srs, tile_mgr in self.caches.iteritems():
            if not cache_srs or srs in cache_srs:
                print "[%s] ... srs '%s'" % (timestamp(), srs.srs_code)
                self.seeded_caches.append(tile_mgr)
                if self.remove_before:
                    tile_mgr._expire_timestamp = self.remove_before
                tile_mgr.minimize_meta_requests = False
                seed_pool = SeedPool(tile_mgr, dry_run=self.dry_run, size=self.concurrency)
                seed_task = SeedTask(bbox, level, bbox_srs, srs, geom)
                seeder = Seeder(tile_mgr, seed_task, seed_pool, self.skip_geoms_for_last_levels)
                seeder.seed()
                seed_pool.stop()
    
    def cleanup(self):
        for tile_mgr in self.seeded_caches:
            for i in range(tile_mgr.grid.levels):
                level_dir = tile_mgr.cache.level_location(i)
                if self.dry_run:
                    def file_handler(filename):
                        print 'removing ' + filename
                else:
                    file_handler = None
                print 'removing oldfiles in ' + level_dir
                cleanup_directory(level_dir, self.remove_before,
                    file_handler=file_handler)

class SeedTask(object):
    def __init__(self, bbox, level, bbox_srs, seed_srs, geom=None):
        self.start_level = level[0]
        self.max_level = level[1]
        self.bbox_srs = bbox_srs
        self.seed_srs = seed_srs
    
        if bbox_srs != seed_srs:
            if geom is not None:
                geom = transform_geometry(bbox_srs, seed_srs, geom)
                bbox = geom.bounds
            else:
                bbox = bbox_srs.transform_bbox_to(seed_srs, bbox)
        
        self.bbox = bbox
        self.geom = geom
        
        if geom is not None:
            self.intersects = self._geom_intersects
        else:
            self.intersects = self._bbox_intersects
    
    def _geom_intersects(self, bbox):
        bbox_poly = bbox_polygon(bbox)
        if self.geom.contains(bbox_poly): return CONTAINS
        if self.geom.intersects(bbox_poly): return INTERSECTS
        return NONE
    
    def _bbox_intersects(self, bbox):
        if bbox_contains(self.bbox, bbox): return CONTAINS
        if bbox_intersects(self.bbox, bbox): return INTERSECTS
        return NONE


def limit_sub_bbox(bbox, sub_bbox):
    """
    >>> limit_sub_bbox((0, 1, 10, 11), (-1, -1, 9, 8))
    (0, 1, 9, 8)
    >>> limit_sub_bbox((0, 0, 10, 10), (5, 2, 18, 18))
    (5, 2, 10, 10)
    """
    minx = max(bbox[0], sub_bbox[0])
    miny = max(bbox[1], sub_bbox[1])
    maxx = min(bbox[2], sub_bbox[2])
    maxy = min(bbox[3], sub_bbox[3])
    return minx, miny, maxx, maxy
    
def timestamp():
    return datetime.datetime.now().strftime('%H:%M:%S')

def format_bbox(bbox):
    return ('(%.5f, %.5f, %.5f, %.5f)') % tuple(bbox)

def status_symbol(i, total):
    """
    >>> status_symbol(0, 1)
    '0'
    >>> [status_symbol(i, 4) for i in range(5)]
    ['.', 'o', 'O', '0', 'X']
    >>> [status_symbol(i, 10) for i in range(11)]
    ['.', '.', 'o', 'o', 'o', 'O', 'O', '0', '0', '0', 'X']
    """
    symbols = list(' .oO0')
    i += 1
    if 0 < i > total:
        return 'X'
    else:
        return symbols[int(math.ceil(i/(total/4)))]

def seed_from_yaml_conf(seed_conf_file, mapproxy_conf_file, verbose=True, dry_run=False,
    concurrency=2, skip_geoms_for_last_levels=0):
    
    if hasattr(seed_conf_file, 'read'):
        seed_conf = yaml.load(seed_conf_file)
    else:
        with open(seed_conf_file) as seed_conf:
            seed_conf = yaml.load(seed_conf)
    
    base_dir = os.path.abspath(os.path.dirname(mapproxy_conf_file))
    conf = ProxyConfiguration(yaml.load(open(mapproxy_conf_file)), base_dir, seed=True)
    with local_base_config(conf.base_config):
        for layer, options in seed_conf['seeds'].iteritems():
            remove_before = before_timestamp_from_options(options)
            try:
                caches = conf.caches[layer].caches()
            except KeyError:
                print >>sys.stderr, 'error: cache %s not found. available caches: %s' % (
                    layer, ','.join(conf.caches.keys()))
                return
            caches = dict((grid.srs, tile_mgr) for grid, extent, tile_mgr in caches)
            seeder = CacheSeeder(caches, remove_before=remove_before, dry_run=dry_run,
                                concurrency=concurrency,
                                skip_geoms_for_last_levels=skip_geoms_for_last_levels)
            for view in options['views']:
                view_conf = seed_conf['views'][view]
                coverage = load_coverage(view_conf)
                bbox = coverage.bbox
                srs = coverage.srs
                geom = coverage.geom

                cache_srs = view_conf.get('srs', None)
                if cache_srs is not None:
                    cache_srs = [SRS(s) for s in cache_srs]
                
                level = view_conf.get('level', None)
                assert len(level) == 2
                print "[%s] seeding cache '%s' with view '%s'" % (timestamp(), layer, view)
                seeder.seed_view(bbox=bbox, level=level, bbox_srs=srs, 
                                 cache_srs=cache_srs, geom=geom)
        
            if remove_before:
                seeder.cleanup()

def before_timestamp_from_options(options):
    """
    >>> import time
    >>> t = before_timestamp_from_options(dict(remove_before={'hours': 4}))
    >>> time.time() - t - 4 * 60 * 60 < 1
    True
    """
    if 'remove_before' not in options:
        return None
    remove_before = options['remove_before']
    if 'time' in remove_before:
        try:
            return timestamp_from_isodate(remove_before['time'])
        except ValueError:
            return None
    deltas = {}
    for delta_type in ('weeks', 'days', 'hours', 'minutes'):
        deltas[delta_type] = remove_before.get(delta_type, 0)
    return timestamp_before(**deltas)

def exp_backoff(func, args=(), kw={}, max_repeat=10, start_backoff_sec=2, 
        exceptions=(Exception,)):
    n = 0
    while True:
        try:
            result = func(*args, **kw)
        except exceptions, ex:
            if (n+1) >= max_repeat:
                raise
            wait_for = start_backoff_sec * 2**n
            print >>sys.stderr, ("An error occured. Retry in %d seconds: %r" % 
                (wait_for, ex))
            time.sleep(wait_for)
            n += 1
        else:
            return result

def check_shapely():
    if not shapely_present:
        raise ImportError('could not import shapley.'
            ' required for polygon/ogr seed areas')

def caches_from_layer(layer):
    caches = []
    if hasattr(layer, 'layers'): # MultiLayer
        layers = layer.layers
    else:
        layers = [layer]
    for layer in layers:
        if hasattr(layer, 'sources'): # VLayer
            caches.extend([source.cache for source in layer.sources
                                if hasattr(source, 'cache')])
        else:
            caches.append(layer.cache)
    return caches

