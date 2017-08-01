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

from mapproxy.cache.compact import CompactCacheV1, CompactCacheV2
from mapproxy.cache.tile import Tile
from mapproxy.compat import iteritems
from mapproxy.config import local_base_config
from mapproxy.config.loader import load_configuration, ConfigurationError
from mapproxy.seed.config import (load_seed_tasks_conf, SeedConfigurationError,
                                  SeedingConfiguration)


def defrag_command(args=None):
    parser = optparse.OptionParser("%prog defrag-compact [options] -f mapproxy_conf")
    parser.add_option("-f", "--mapproxy-conf", dest="mapproxy_conf",
        help="MapProxy configuration.")

    parser.add_option("--min-percent", type=float, default=10.0,
        help="Only defrag if fragmentation is larger (10 means at least 10% of the file needs to be wasted)")

    parser.add_option("--min-mb", type=float, default=1.0,
        help="Only defrag if fragmentation is larger (2 means at least 2MB needs to be wasted)")

    from mapproxy.script.util import setup_logging
    import logging
    setup_logging(logging.INFO)

    log = logging.getLogger('mapproxy.defrag-compact')

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
        for name, cache_conf in proxy_configuration.caches.items():
            for grid, extent, tile_mgr in cache_conf.caches():
                if isinstance(tile_mgr.cache, (CompactCacheV1, CompactCacheV2)):
                    log.info('de-fragmenting %s', name)
                    defrag_compact_cache(tile_mgr.cache,
                        min_percent=options.min_percent/100,
                        min_bytes=options.min_mb*1024*1024,
                    )

def bundle_offset(fname):
    match = re.search('R([A-F0-9]{4,})C([A-F0-9]{4,}).bundle$', fname, re.IGNORECASE)
    if match:
        r = int(match.group(1), 16)
        c = int(match.group(2), 16)
        return c, r

def defrag_compact_cache(cache, min_percent=0.1, min_bytes=1024*1024):
    for level_dir in glob.glob(os.path.join(cache.cache_dir, 'L??')):
        for bundle_file in glob.glob(os.path.join(level_dir, 'R????C????.bundle')):
            offset = bundle_offset(bundle_file)
            b = cache.bundle_class(bundle_file.rstrip('.bundle'), offset)
            size, file_size = b.size()

            defrag = 1 - float(size) / file_size
            defrag_bytes = file_size - size

            print('%s fragmentation: %4.1f%% %dkB' % (bundle_file, defrag*100, defrag_bytes/1024))
            if defrag < min_percent or defrag_bytes < min_bytes:
                continue

            print('rewriting %s' % (bundle_file, ))
            tmp_bundle = os.path.join(level_dir, 'tmp_defrag')
            defb = cache.bundle_class(tmp_bundle, offset)

            for y in range(128):
                tiles = [Tile((x, y, 0)) for x in range(128)]
                b.load_tiles(tiles)
                tiles = [t for t in tiles if t.source]
                if tiles:
                    defb.store_tiles(tiles)

            os.rename(tmp_bundle + '.bundle', bundle_file)
            if os.path.exists(tmp_bundle + '.bundlx'):
                os.rename(tmp_bundle + '.bundlx', bundle_file[:-1] + 'x')
            os.unlink(tmp_bundle + '.lck')
