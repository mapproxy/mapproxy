# This file is part of the MapProxy project.
# Copyright (C) 2017 Omniscale <http://omniscale.de>
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

import glob
import optparse
import os.path
import re
import sys
from collections import OrderedDict

from mapproxy.cache.compact import CompactCacheV1, CompactCacheV2
from mapproxy.cache.tile import Tile
from mapproxy.config import local_base_config
from mapproxy.config.loader import load_configuration, ConfigurationError

import logging
log = logging.getLogger('mapproxy.defrag')

def defrag_command(args=None):
    parser = optparse.OptionParser("%prog defrag-compact [options] -f mapproxy_conf")
    parser.add_option("-f", "--mapproxy-conf", dest="mapproxy_conf",
        help="MapProxy configuration.")

    parser.add_option("--min-percent", type=float, default=10.0,
        help="Only defrag if fragmentation is larger (10 means at least 10% of the file does not have to be used)")

    parser.add_option("--min-mb", type=float, default=1.0,
        help="Only defrag if fragmentation is larger (2 means at least 2MB the file does not have to be used)")

    parser.add_option("--dry-run", "-n", action="store_true",
        help="Do not de-fragment, only print output")

    parser.add_option("--caches", dest="cache_names", metavar='cache1,cache2,...',
        help="only defragment the named caches")


    from mapproxy.script.util import setup_logging
    import logging
    setup_logging(logging.INFO, format="[%(asctime)s] %(msg)s")

    if args:
        args = args[1:] # remove script name

    (options, args) = parser.parse_args(args)
    if not options.mapproxy_conf:
        parser.print_help()
        sys.exit(1)

    try:
        proxy_configuration = load_configuration(options.mapproxy_conf)
    except IOError as e:
        print('ERROR: ', "%s: '%s'" % (e.strerror, e.filename), file=sys.stderr)
        sys.exit(2)
    except ConfigurationError as e:
        print(e, file=sys.stderr)
        print('ERROR: invalid configuration (see above)', file=sys.stderr)
        sys.exit(2)


    with local_base_config(proxy_configuration.base_config):
        available_caches = OrderedDict()
        for name, cache_conf in proxy_configuration.caches.items():
            for grid, extent, tile_mgr in cache_conf.caches():
                if isinstance(tile_mgr.cache, (CompactCacheV1, CompactCacheV2)):
                    available_caches.setdefault(name, []).append(tile_mgr.cache)

        if options.cache_names:
            defrag_caches = options.cache_names.split(',')
            missing = set(defrag_caches).difference(available_caches.keys())
            if missing:
                print('unknown caches: %s' % (', '.join(missing), ))
                print('available compact caches: %s' %
                      (', '.join(available_caches.keys()), ))
                sys.exit(1)
        else:
            defrag_caches = None

        for name, caches in available_caches.items():
            if defrag_caches and name not in defrag_caches:
                continue
            for cache in caches:
                logger = DefragLog(name)
                defrag_compact_cache(cache,
                    min_percent=options.min_percent/100,
                    min_bytes=options.min_mb*1024*1024,
                    dry_run=options.dry_run,
                    log_progress=logger,
                )

def bundle_offset(fname):
    """
    >>> bundle_offset("path/to/R0000C0000.bundle")
    (0, 0)
    >>> bundle_offset("path/to/R0380C1380.bundle")
    (4992, 896)
    """
    match = re.search(r'R([A-F0-9]{4,})C([A-F0-9]{4,}).bundle$', fname, re.IGNORECASE)
    if match:
        r = int(match.group(1), 16)
        c = int(match.group(2), 16)
        return c, r

class DefragLog(object):
    def __init__(self, cache_name):
        self.cache_name = cache_name
    def log(self, fname, fragmentation, fragmentation_bytes, num, total, defrag):
        msg = "%s: %3d/%d (%s) fragmentation is %.1f%% (%dkb)" % (
            self.cache_name, num, total, fname, fragmentation, fragmentation_bytes/1024
        )
        if defrag:
            msg += " - defragmenting"
        else:
            msg += " - skipping"
        log.info(msg)

def defrag_compact_cache(cache, min_percent=0.1, min_bytes=1024*1024, log_progress=None, dry_run=False):
    bundles = glob.glob(os.path.join(cache.cache_dir, 'L??', 'R????C????.bundle'))

    for i, bundle_file in enumerate(bundles):
        offset = bundle_offset(bundle_file)
        b = cache.bundle_class(bundle_file.rstrip('.bundle'), offset)
        size, file_size = b.size()

        defrag = 1 - float(size) / file_size
        defrag_bytes = file_size - size


        skip = False
        if defrag < min_percent or defrag_bytes < min_bytes:
            skip = True

        if log_progress:
            log_progress.log(
                fname=bundle_file,
                fragmentation=defrag * 100,
                fragmentation_bytes=defrag_bytes,
                num=i+1, total=len(bundles),
                defrag=not skip,
            )

        if skip or dry_run:
            continue

        tmp_bundle = os.path.join(cache.cache_dir, 'tmp_defrag')
        defb = cache.bundle_class(tmp_bundle, offset)
        stored_tiles = False

        for y in range(128):
            tiles = [Tile((x, y, 0)) for x in range(128)]
            b.load_tiles(tiles)
            tiles = [t for t in tiles if t.source]
            if tiles:
                stored_tiles = True
                defb.store_tiles(tiles)

        # remove first
        # - in case bundle is empty
        # - windows does not support rename to existing files
        if os.path.exists(bundle_file):
            os.remove(bundle_file)
        if os.path.exists(bundle_file[:-1] + 'x'):
            os.remove(bundle_file[:-1] + 'x')

        if stored_tiles:
            os.rename(tmp_bundle + '.bundle', bundle_file)
            if os.path.exists(tmp_bundle + '.bundlx'):
                os.rename(tmp_bundle + '.bundlx', bundle_file[:-1] + 'x')
            if os.path.exists(tmp_bundle + '.lck'):
                os.unlink(tmp_bundle + '.lck')

