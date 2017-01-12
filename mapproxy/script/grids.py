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

from __future__ import print_function, division

import math
import sys
import optparse

from mapproxy.compat import iteritems
from mapproxy.config import local_base_config
from mapproxy.config.loader import load_configuration, ConfigurationError
from mapproxy.seed.config import (
    load_seed_tasks_conf, SeedConfigurationError, SeedingConfiguration
)

def format_conf_value(value):
    if isinstance(value, tuple):
        # YAMl only supports lists, convert for clarity
        value = list(value)
    return repr(value)

def _area_from_bbox(bbox):
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    return width * height

def grid_coverage_ratio(bbox, srs, coverage):
    coverage = coverage.transform_to(srs)
    grid_area = _area_from_bbox(bbox)

    if coverage.geom:
        coverage_area = coverage.geom.area
    else:
        coverage_area = _area_from_bbox(coverage.bbox)

    return coverage_area / grid_area

def display_grid(grid_conf, coverage=None):
    print('%s:' % (grid_conf.conf['name'],))
    print('    Configuration:')
    conf_dict = grid_conf.conf.copy()

    tile_grid = grid_conf.tile_grid()
    if 'tile_size' not in conf_dict:
        conf_dict['tile_size*'] = tile_grid.tile_size
    if 'bbox' not in conf_dict:
        conf_dict['bbox*'] = tile_grid.bbox
    if 'origin' not in conf_dict:
        conf_dict['origin*'] = tile_grid.origin or 'sw'
    area_ratio = None
    if coverage:
        bbox = tile_grid.bbox
        area_ratio = grid_coverage_ratio(bbox, tile_grid.srs, coverage)

    for key in sorted(conf_dict):
        if key == 'name':
            continue
        print('        %s: %s' % (key, format_conf_value(conf_dict[key])))
    if coverage:
        print('    Coverage: %s covers approx. %.4f%% of the grid BBOX' % (coverage.name, area_ratio * 100))
        print('    Levels: Resolutions, # x * y = total tiles (approx. tiles within coverage)')
    else:
        print('    Levels: Resolutions, # x * y = total tiles')
    max_digits = max([len("%r" % (res,)) for level, res in enumerate(tile_grid.resolutions)])
    for level, res in enumerate(tile_grid.resolutions):
        tiles_in_x, tiles_in_y = tile_grid.grid_sizes[level]
        total_tiles = tiles_in_x * tiles_in_y
        spaces = max_digits - len("%r" % (res,)) + 1

        if coverage:
            coverage_tiles = total_tiles * area_ratio
            print("        %.2d:  %r,%s# %6d * %-6d = %10s (%s)" % (level, res, ' '*spaces, tiles_in_x, tiles_in_y, human_readable_number(total_tiles), human_readable_number(coverage_tiles)))
        else:
            print("        %.2d:  %r,%s# %6d * %-6d = %10s" % (level, res, ' '*spaces, tiles_in_x, tiles_in_y, human_readable_number(total_tiles)))

def human_readable_number(num):
    if num > 10**6:
        return '%7.2fM' % (num/10**6)
    if math.isnan(num):
        return '?'
    return '%d' % int(num)

def display_grids_list(grids):
    for grid_name in sorted(grids.keys()):
        print(grid_name)

def display_grids(grids, coverage=None):
    for i, grid_name in enumerate(sorted(grids.keys())):
        if i != 0:
            print()
        display_grid(grids[grid_name], coverage=coverage)

def grids_command(args=None):
    parser = optparse.OptionParser("%prog grids [options] mapproxy_conf")
    parser.add_option("-f", "--mapproxy-conf", dest="mapproxy_conf",
        help="MapProxy configuration.")
    parser.add_option("-g", "--grid", dest="grid_name",
        help="Display only information about the specified grid.")
    parser.add_option("--all", dest="show_all", action="store_true", default=False,
        help="Show also grids that are not referenced by any cache.")
    parser.add_option("-l", "--list", dest="list_grids", action="store_true", default=False, help="List names of configured grids, which are used by any cache")
    coverage_group = parser.add_option_group("Approximate the number of tiles within a given coverage")
    coverage_group.add_option("-s", "--seed-conf", dest="seed_config", help="Seed configuration, where the coverage is defined")
    coverage_group.add_option("-c", "--coverage-name", dest="coverage", help="Calculate number of tiles when a coverage is given")

    from mapproxy.script.util import setup_logging
    import logging
    setup_logging(logging.WARN)

    if args:
        args = args[1:] # remove script name

    (options, args) = parser.parse_args(args)
    if not options.mapproxy_conf:
        if len(args) != 1:
            parser.print_help()
            sys.exit(1)
        else:
            options.mapproxy_conf = args[0]
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
        if options.show_all or options.grid_name:
            grids = proxy_configuration.grids
        else:
            caches = proxy_configuration.caches
            grids = {}
            for cache in caches.values():
                grids.update(cache.grid_confs())
            grids = dict(grids)

        if options.grid_name:
            options.grid_name = options.grid_name.lower()
            # ignore case for keys
            grids = dict((key.lower(), value) for (key, value) in iteritems(grids))
            if not grids.get(options.grid_name, False):
                print('grid not found: %s' % (options.grid_name,))
                sys.exit(1)

        coverage = None
        if options.coverage and options.seed_config:
            try:
                seed_conf = load_seed_tasks_conf(options.seed_config, proxy_configuration)
            except SeedConfigurationError as e:
                print('ERROR: invalid configuration (see above)', file=sys.stderr)
                sys.exit(2)

            if not isinstance(seed_conf, SeedingConfiguration):
                print('Old seed configuration format not supported')
                sys.exit(1)

            coverage = seed_conf.coverage(options.coverage)
            coverage.name = options.coverage

        elif (options.coverage and not options.seed_config) or (not options.coverage and options.seed_config):
            print('--coverage and --seed-conf can only be used together')
            sys.exit(1)

        if options.list_grids:
            display_grids_list(grids)
        elif options.grid_name:
            display_grids({options.grid_name: grids[options.grid_name]}, coverage=coverage)
        else:
            display_grids(grids, coverage=coverage)



