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

from __future__ import division, with_statement
import os
import sys
import time
from collections import defaultdict
from itertools import islice, chain
from contextlib import contextmanager 
from mapproxy.core.srs import SRS
from mapproxy.core.cache import TileSourceError
from mapproxy.core.utils import (
    swap_dir,
    cleanup_directory,
    timestamp_before,
    timestamp_from_isodate,
)

import yaml #pylint: disable-msg=F0401

import math

def exp_backoff(func, max_repeat=10, start_backoff_sec=2, 
        exceptions=(Exception,)):
    n = 0
    while True:
        try:
            result = func()
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

class TileSeeder(object):
    operating = True
    
    @classmethod
    def stop_all(cls):
        cls.operating = False
    
    def __init__(self, vlayer, progress_meter, rebuild_inplace=True, remove_before=None):
        self.progress_meter = progress_meter
        self.caches = []
        self.seeds = defaultdict(list)
        self.rebuild_inplace = rebuild_inplace
        self.remove_before = remove_before
        if hasattr(vlayer, 'layers'): # MultiLayer
            vlayer = vlayer.layers
        else:
            vlayer = [vlayer]
        for layer in vlayer:
            if hasattr(layer, 'sources'): # VLayer
                self.caches.extend([source.cache for source in layer.sources
                                    if hasattr(source, 'cache')])
            else:
                self.caches.append(layer.cache)
    def add_seed_location(self, point_bbox, res=None, level=None, srs=None,
                          cache_srs=None, px_buffer=1000):
        for cache in self.caches:
            if not cache_srs or cache.grid.srs in cache_srs:
                self._add_seed_location(cache, point_bbox, res=res, level=level,
                                        srs=srs, px_buffer=px_buffer)
    def _add_seed_location(self, cache, point_bbox, res=None, level=None,
                           srs=None, px_buffer=1000):
        assert px_buffer >= 0
        if len(point_bbox) == 2 and px_buffer == 0:
            px_buffer = 1 # prevent divzero later
        assert res is not None or level is not None
        
        bbox = make_bbox(point_bbox)
        
        if srs is None:
            srs = cache.grid.srs
            
        grid = cache.grid
        
        if level is None:
            if srs != grid.srs: # convert res to native srs
                res = transform_res((bbox[0], bbox[1]), res, srs, grid.srs)
            level = grid.closest_level(res)
        if isinstance(level, (int, long)):
            levels = range(level+1)
        else:
            levels = range(level[0], level[1]+1)
        
        if srs != grid.srs:
            bbox = srs.transform_bbox_to(grid.srs, bbox)
        
        for level in levels:
            res = grid.resolutions[level]
            buf = px_buffer * res
            seed_bbox = (bbox[0] - buf, bbox[1] - buf,
                         bbox[2] + buf, bbox[3] + buf)
            self._add_seed_level(cache, seed_bbox, level)
    
    @staticmethod
    def _create_tile_iterator(grid, bbox, level):
        """
        Return all tiles that intersect the `bbox` on `level`.
        
        :returns: estimated number of tiles, tile iterator
        """
        res = grid.resolutions[level]
        w, h = bbox_pixel_size(bbox, res)
        bbox, _grid, tiles = grid.get_affected_tiles(bbox, (w, h))
        
        est_number_of_tiles = int(math.ceil(w/grid.tile_size[0] * 
                                            h/grid.tile_size[1]))
        return est_number_of_tiles, tiles
     
    def _add_seed_level(self, cache, bbox, level):        
        est_number_of_tiles, tiles = self._create_tile_iterator(cache.grid, bbox, level)
        self.seeds[(cache, level)].append((est_number_of_tiles, tiles))
    
    def _seed_tiles(self, cache, tiles, progress, dry_run=False):
        """
        Seed the given `tiles` form `cache`.
        """
        tiles_per_loop = 128
        for chunk in take_n(tiles, tiles_per_loop):
            if not self.operating: return
            if not dry_run:
                load_tiles = lambda: cache.cache_mgr.load_tile_coords(chunk)
                exp_backoff(load_tiles, exceptions=(TileSourceError, IOError))
            progress.advance(len(chunk))
    
    def seed(self, dry_run=False):
        for seed in self._sorted_seeds():
            if not self.operating: return
            level, cache, tiles = seed['level'], seed['cache'], seed['tiles']
            
            progress = self.progress_meter(total=seed['est_number_of_tiles'],
                                           opts={'level': level})
            progress.print_msg('start seeding #%d: %r' % (level, cache))
            if (not self.rebuild_inplace and 
                level_needs_rebuild(cache, level, self.remove_before)):
                with self._tmp_rebuild_location(cache, level, dry_run=dry_run):
                    self._seed_tiles(cache, tiles, progress, dry_run=dry_run)
                    if not dry_run:
                        update_level_timestamp(cache, level)
            else:
                cache.cache_mgr.expire_timestamp = lambda tile: self.remove_before
                self._seed_tiles(cache, tiles, progress, dry_run=dry_run)
            
        self.cleanup(progress, dry_run)
    
    def cleanup(self, progress, dry_run):
        if self.remove_before is None:
            return
        caches = self._caches_with_seeded_levels()
        for cache, seeded_levels in caches.iteritems():
            for i in range(cache.grid.levels):
                if not self.rebuild_inplace and i in seeded_levels:
                    continue # fresh level
                level_dir = cache.cache_mgr.cache.level_location(i)
                if dry_run:
                    def file_handler(filename):
                        progress.print_msg('removing ' + filename)
                else:
                    file_handler = None
                progress.print_msg('removing oldfiles in ' + level_dir)
                cleanup_directory(level_dir, self.remove_before,
                                  file_handler=file_handler)
    
    def _sorted_seeds(self):
        seeds = []
        keys = self.seeds.keys()
        keys.sort(lambda a, b: cmp(a[1], b[1]) or cmp(a[0], b[0]))
        for key in keys:
            num = sum(task[0] for task in self.seeds[key])
            tiles = chain(*[task[1] for task in self.seeds[key]])
            seeds.append(dict(cache=key[0], level=key[1], est_number_of_tiles=num,
                              tiles=tiles))
        return seeds
    
    def _caches_with_seeded_levels(self):
        caches = defaultdict(set)
        for cache, level in self.seeds.iterkeys():
            caches[cache].add(level)
        return caches
    
    @contextmanager
    def _tmp_rebuild_location(self, cache, level, dry_run=False):
        old_level_location = cache.cache_mgr.cache.level_location
        def level_location(level):
            return old_level_location(level) + '.new'
        cache.cache_mgr.cache.level_location = level_location
        
        yield
        
        self.progress_meter().print_msg('rotating new tiles')
        if not dry_run:
            swap_dir(level_location(level), old_level_location(level))
        cache.cache_mgr.cache.level_location = old_level_location
    
def level_needs_rebuild(cache, level, remove_before):
    if remove_before is None:
        return True
    cache_dir = cache.cache_mgr.cache.level_location(level)
    level_timestamp = os.path.join(cache_dir, 'last_seed')
    if os.path.exists(level_timestamp):
        return os.stat(level_timestamp).st_mtime < remove_before
    else:
        return True

def update_level_timestamp(cache, level):
    cache_dir = cache.cache_mgr.cache.level_location(level)
    level_timestamp = os.path.join(cache_dir, 'last_seed')
    if os.path.exists(level_timestamp):
        os.utime(level_timestamp, None)
    else:
        if os.path.exists(os.path.dirname(level_timestamp)):
            open(level_timestamp, 'w').close()
    

class ProgressMeter(object):
    def __init__(self, start=0, total=None, opts=None, out=None):
        self.start = start
        self.current = start
        self.total = total
        if out is None:
            import sys
            out = sys.stdout
        self.out = out
        if opts is None:
            opts = {}
        self.opts = opts
    @property
    def percent(self):
        if self.total is None:
            return ''
        return '%.2f%%' % (self.current/self.total*100,)
    @property
    def progress(self):
        if self.total is None:
            return str(self.current)
        else:
            return '%d/%d' % (self.current, self.total)
    def advance(self, steps):
        self.current += steps
        if self.current > self.total:
            self.total = self.current
        self.print_progress()
    def print_progress(self):
        pass
    
    def print_msg(self, msg):
        pass
    

class NullProgressMeter(ProgressMeter):
    pass

class TileProgressMeter(ProgressMeter):
    def print_progress(self):
        level = ''
        if 'level' in self.opts:
            level = 'for level ' + str(self.opts['level']) + ' '
        print >>self.out, "created %s tiles %s(%s)" % (self.progress, level, self.percent)
    def print_msg(self, msg):
        print >>self.out, msg


def make_bbox(point_bbox):
    """
    >>> make_bbox((8, 53))
    (8, 53, 8, 53)
    >>> make_bbox((5, 46,15, 55))
    (5, 46, 15, 55)
    """
    if len(point_bbox) == 2:
        return (point_bbox[0], point_bbox[1],
                point_bbox[0], point_bbox[1])
    else:
        return point_bbox

def transform_res(point, res, src_srs, dst_srs):
    """
    Transform the resolution from one `src_srs` to `dst_srs` at `point`.
    Eg. from m/px resolution to deg/pix.
    """
    res_point = point[0] + res, point[1] + res
    point = src_srs.transform_to(dst_srs, point)
    res_point = src_srs.transform_to(dst_srs, res_point)
    res = res_point[0] - point[0]
    
def take_n(values, n):
    iterator = iter(values)
    while True:
        chunk = list(islice(iterator, n+1))
        if chunk: 
            yield chunk
        else:
            break

def bbox_pixel_size(bbox, res):
    """
    Return the size of the `bbox` in pixel at the given `res`.
    """
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return (w/res, h/res)

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

def seed_from_yaml_conf(conf_file, verbose=True, rebuild_inplace=True, dry_run=False):
    from mapproxy.core.conf_loader import load_services
    
    
    if hasattr(conf_file, 'read'):
        seed_conf = yaml.load(conf_file)
    else:
        with open(conf_file) as conf_file:
            seed_conf = yaml.load(conf_file)
    
    if verbose:
        progress_meter = TileProgressMeter
    else:
        progress_meter = NullProgressMeter
    
    services = load_services()
    if 'wms' in services:
        server  = services['wms']
    elif 'tms' in services:
        server  = services['tms']
    else:
        print 'no wms or tms server configured. add one to your proxy.yaml'
        return
    for layer, options in seed_conf['seeds'].iteritems():
        remove_before = before_timestamp_from_options(options)
        seeder = TileSeeder(server.layers[layer], remove_before=remove_before,
                            progress_meter=progress_meter,
                            rebuild_inplace=rebuild_inplace)
        for view in options['views']:
            view_conf = seed_conf['views'][view]
            srs = view_conf.get('bbox_srs', None)
            bbox = view_conf['bbox']
            cache_srs = view_conf.get('srs', None)
            if cache_srs is not None:
                cache_srs = [SRS(s) for s in cache_srs]
            if srs is not None:
                srs = SRS(srs)
            level = view_conf.get('level', None)
            res = view_conf.get('res', None)
            seeder.add_seed_location(bbox, res=res, level=level, srs=srs, 
                                     cache_srs=cache_srs)
        seeder.seed(dry_run=dry_run)
    