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

from __future__ import print_function, division

import os
import sys
import stat
import math
import time
from datetime import datetime

try:
    import cPickle as pickle
except ImportError:
    import pickle

from mapproxy.layer import map_extent_from_grid
from mapproxy.util.fs import write_atomic

import logging
log = logging.getLogger(__name__)

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
        self.last_tick_start = time.time()
        self.progress = 0.0
        self.ticks = 10000
        self.tick_duration_sums = 0.0
        self.tick_duration_divisor = 0.0
        self.tick_count = 0

    def update(self, progress):
        self.progress = progress
        missing_ticks = (self.progress * self.ticks) - self.tick_count
        if missing_ticks:
            tick_duration = (time.time() - self.last_tick_start) / missing_ticks

            while missing_ticks > 0:

                # reduce the influence of older messurements
                self.tick_duration_sums *= 0.999
                self.tick_duration_divisor *= 0.999

                self.tick_count += 1

                self.tick_duration_sums += tick_duration
                self.tick_duration_divisor += 1

                missing_ticks -= 1

            self.last_tick_start = time.time()

    def eta_string(self):
        timestamp = self.eta()
        if timestamp is None:
            return 'N/A'
        try:
            return time.strftime('%Y-%m-%d-%H:%M:%S', time.localtime(timestamp))
        except (ValueError, OSError): # OSError since Py 3.3
            # raised when time is out of range (e.g. year >2038)
            return 'N/A'

    def eta(self):
        if not self.tick_count: return
        return (self.last_tick_start +
                ((self.tick_duration_sums/self.tick_duration_divisor)
                 * (self.ticks - self.tick_count)))

    def __str__(self):
        return self.eta_string()

class ProgressStore(object):
    """
    Reads and stores seed progresses to a file.
    """
    def __init__(self, filename=None, continue_seed=True):
        self.filename = filename
        if continue_seed:
            self.status = self.load()
        else:
            self.status = {}

    def load(self):
        if not os.path.exists(self.filename):
            pass
        elif os.stat(self.filename).st_mode & stat.S_IWOTH:
            log.error('progress file (%s) is world writable, ignoring file',
                self.filename)
        else:
            with open(self.filename, 'rb') as f:
                try:
                    return pickle.load(f)
                except (pickle.UnpicklingError, AttributeError,
                    EOFError, ImportError, IndexError):
                    log.error('unable to read progress file (%s), ignoring file',
                        self.filename)

        return {}

    def write(self):
        try:
            write_atomic(self.filename, pickle.dumps(self.status))
        except (IOError, OSError) as ex:
            log.error('unable to write seed progress: %s', ex)

    def remove(self):
        self.status = {}
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def get(self, task_identifier):
        return self.status.get(task_identifier, None)

    def add(self, task_identifier, progress_identifier):
        self.status[task_identifier] = progress_identifier

class ProgressLog(object):
    def __init__(self, out=None, silent=False, verbose=True, progress_store=None):
        if not out:
            out = sys.stdout
        self.out = out
        self.lastlog = time.time()
        self.verbose = verbose
        self.silent = silent
        self.current_task_id = None
        self.progress_store = progress_store

    def log_message(self, msg):
        self.out.write('[%s] %s\n' % (
            timestamp(), msg,
        ))
        self.out.flush()

    def log_step(self, progress):
        if not self.verbose:
            return
        if (self.lastlog + .1) < time.time():
            # log progress at most every 100ms
            self.out.write('[%s] %6.2f%%\t%-20s ETA: %s\r' % (
                timestamp(), progress.progress*100, progress.progress_str,
                progress.eta
            ))
            self.out.flush()
            self.lastlog = time.time()

    def log_progress(self, progress, level, bbox, tiles):
        if self.progress_store and self.current_task_id:
            self.progress_store.add(self.current_task_id,
                progress.current_progress_identifier())
            self.progress_store.write()

        if self.silent:
            return
        self.out.write('[%s] %2s %6.2f%% %s (%d tiles) ETA: %s\n' % (
            timestamp(), level, progress.progress*100,
            format_bbox(bbox), tiles, progress.eta))
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

class BackoffError(Exception):
    pass

def exp_backoff(func, args=(), kw={}, max_repeat=10, start_backoff_sec=2,
        exceptions=(Exception,), ignore_exceptions=tuple(), max_backoff=60):
    n = 0
    while True:
        try:
            result = func(*args, **kw)
        except ignore_exceptions:
            time.sleep(0.01)
        except exceptions as ex:
            if n >= max_repeat:
                print >>sys.stderr, "An error occured. Giving up"
                raise BackoffError
            wait_for = start_backoff_sec * 2**n
            if wait_for > max_backoff:
                wait_for = max_backoff
            print("An error occured. Retry in %d seconds: %r. Retries left: %d" %
                (wait_for, ex, (max_repeat - n)), file=sys.stderr)
            time.sleep(wait_for)
            n += 1
        else:
            return result

def format_seed_task(task):
    info = []
    info.append('  %s:' % (task.md['name'], ))
    if task.coverage is False:
        info.append("    Empty coverage given for this task")
        info.append("    Skipped")
        return '\n'.join(info)

    info.append("    Seeding cache '%s' with grid '%s' in %s" % (
                 task.md['cache_name'], task.md['grid_name'], task.grid.srs.srs_code))
    if task.coverage:
        info.append('    Limited to coverage in: %s (EPSG:4326)' % (format_bbox(task.coverage.extent.llbbox), ))
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
    if task.coverage is False:
        info.append("    Empty coverage given for this task")
        info.append("    Skipped")
        return '\n'.join(info)

    info.append("    Cleaning up cache '%s' with grid '%s' in %s" % (
                 task.md['cache_name'], task.md['grid_name'], task.grid.srs.srs_code))
    if task.coverage:
        info.append('    Limited to coverage in: %s (EPSG:4326)' % (format_bbox(task.coverage.extent.llbbox), ))
    else:
        info.append('    Complete grid: %s (EPSG:4326)' % (format_bbox(map_extent_from_grid(task.grid).llbbox), ))
    info.append('    Levels: %s' % (task.levels, ))

    if task.remove_timestamp:
        info.append('    Remove: tiles older than %s' %
                    datetime.fromtimestamp(task.remove_timestamp))
    else:
        info.append('    Remove: all tiles')

    return '\n'.join(info)
