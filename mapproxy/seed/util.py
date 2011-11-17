# This file is part of the MapProxy project.
# Copyright (C) 2010, 2011 Omniscale <http://omniscale.de>
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

from __future__ import with_statement, division

import sys
import math
import time
from datetime import datetime

from mapproxy.layer import map_extent_from_grid

class bidict(dict):
    """
    Simplest bi-directional dictionary.
    """
    def __init__(self, iterator):
        for key, val in iterator:
            dict.__setitem__(self, key, val)
            dict.__setitem__(self, val, key)

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

class ProgressLog(object):
    def __init__(self, out=None, silent=False, verbose=True):
        if not out:
            out = sys.stdout
        self.out = out
        self.lastlog = time.time()
        self.verbose = verbose
        self.silent = silent
        
    def log_step(self, progress):
        if not self.verbose:
            return
        if (self.lastlog + .1) < time.time():
            # log progress at most every 100ms
            self.out.write('[%s] %6.2f%% %s \tETA: %s\r' % (
                timestamp(), progress[1]*100, progress[0],
                progress[2]
            ))
            self.out.flush()
            self.lastlog = time.time()
    
    def log_progress(self, progress, level, bbox, tiles, eta):
        if self.silent:
            return
        self.out.write('[%s] %2s %6.2f%% %s (%d tiles) ETA: %s\n' % (
            timestamp(), level, progress*100,
            format_bbox(bbox), tiles, eta))
        self.out.flush()

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
    return datetime.now().strftime('%H:%M:%S')

def format_bbox(bbox):
    return ('%.5f, %.5f, %.5f, %.5f') % tuple(bbox)

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

def format_seed_task(task):
    info = []
    info.append('  %s:' % (task.md['name'], ))
    info.append("    Seeding cache '%s' with grid '%s' in %s" % (
                 task.md['cache_name'], task.md['grid_name'], task.grid.srs.srs_code))
    if task.coverage:
        info.append('    Limited to: %s (EPSG:4326)' % (format_bbox(task.coverage.extent.llbbox), ))
    else:
        info.append('   Complete grid: %s (EPSG:4326)' % (format_bbox(map_extent_from_grid(task.grid).llbbox), ))
    info.append('    Levels: %s' % (task.levels, ))
        
    if task.refresh_timestamp:
        info.append('    Overwriting: tiles older than %s' %
                    datetime.fromtimestamp(task.refresh_timestamp))
    elif task.refresh_timestamp == 0:
        info.append('    Overwriting: all tiles')
    else:
        info.append('    Overwriting: no tiles')
    
    return '\n'.join(info)

def format_cleanup_task(task):
    info = []
    info.append('  %s:' % (task.md['name'], ))
    info.append("    Cleaning up cache '%s' with grid '%s' in %s" % (
                 task.md['cache_name'], task.md['grid_name'], task.grid.srs.srs_code))
    if task.coverage:
        info.append('    Limited to: %s (EPSG:4326)' % (format_bbox(task.coverage.extent.llbbox), ))
    else:
        info.append('    Complete grid: %s (EPSG:4326)' % (format_bbox(map_extent_from_grid(task.grid).llbbox), ))
    info.append('    Levels: %s' % (task.levels, ))
        
    if task.remove_timestamp:
        info.append('    Remove: tiles older than %s' %
                    datetime.fromtimestamp(task.remove_timestamp))
    else:
        info.append('    Remove: all tiles')
    
    return '\n'.join(info)
