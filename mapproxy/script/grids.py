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
from __future__ import division

import sys
import optparse

from mapproxy.util import local_base_config
from mapproxy.config.loader import load_configuration, ConfigurationError
from mapproxy.seed.config import (
    load_seed_tasks_conf, SeedConfigurationError, SeedingConfiguration
)
from mapproxy.layer import MapExtent

def format_conf_value(value):
    if isinstance(value, tuple):
        # YAMl only supports lists, convert for clarity
        value = list(value)
    return repr(value)

def _area_from_bbox(bbox):
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    return width * height

def grid_coverage_ratio(grid_extent, coverage_extent):
    coverage_bbox = coverage_extent.bbox_for(grid_extent.srs)
    grid_bbox = grid_extent.bbox

    coverage_area = _area_from_bbox(coverage_bbox)
    grid_area = _area_from_bbox(grid_bbox)
    return coverage_area / grid_area

def display_grid(grid_conf, coverage=None):
    print '%s:' % (grid_conf.conf['name'],)
    print '    Configuration:'
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
        bbox = conf_dict.get('bbox', tile_grid.bbox)
        area_ratio = grid_coverage_ratio(MapExtent(bbox, tile_grid.srs), MapExtent(coverage.bbox, coverage.srs))

    for key in sorted(conf_dict):
        if key == 'name':
            continue
        print '        %s: %s' % (key, format_conf_value(conf_dict[key]))
    if coverage:
        print '    Levels: Resolutions, # Tiles x * Tiles y = total tiles # Approximation of tiles within coverage:'
    else:
        print '    Levels: Resolutions, # Tiles x * Tiles y = total tiles:' 
    max_digits = max([len("%r" % (res,)) for level, res in enumerate(tile_grid.resolutions)])
    for level, res in enumerate(tile_grid.resolutions):
        tiles_in_x, tiles_in_y = tile_grid.grid_sizes[level]
        total_tiles = tiles_in_x * tiles_in_y
        spaces = max_digits - len("%r" % (res,)) + 1

        if coverage:
            coverage_tiles = total_tiles * area_ratio
            print "        %.2d:  %r,%s# %d * %d = %d # %d" % (level, res, ' '*spaces, tiles_in_x, tiles_in_y, total_tiles, coverage_tiles)
        else:
            print "        %.2d:  %r,%s# %d * %d = %d" % (level, res, ' '*spaces, tiles_in_x, tiles_in_y, total_tiles)

def display_grids_list(grids):
    for grid_name in sorted(grids.keys()):
        print grid_name

def display_grids(grids, coverage=None):
    for i, grid_name in enumerate(sorted(grids.keys())):
        if i != 0:
            print
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
    except IOError, e:
        print >>sys.stderr, 'ERROR: ', "%s: '%s'" % (e.strerror, e.filename)
        sys.exit(2)
    except ConfigurationError, e:
        print >>sys.stderr, 'ERROR: invalid configuration (see above)'
        sys.exit(2)

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
        grids = dict((key.lower(), value) for (key, value) in grids.iteritems())
        if not grids.get(options.grid_name, False):
            print 'grid not found: %s' % (options.grid_name,)
            sys.exit(1)

    coverage = None
    if options.coverage and options.seed_config:
        with local_base_config(proxy_configuration.base_config):
            try:
                seed_conf = load_seed_tasks_conf(options.seed_config, proxy_configuration)
            except SeedConfigurationError, e:
                print >>sys.stderr, 'ERROR: invalid configuration (see above)'
                sys.exit(2)

            if not isinstance(seed_conf, SeedingConfiguration):
                print 'Old seed configuration format not supported'
                sys.exit(1)

            coverage = seed_conf.coverage(options.coverage)

    elif (options.coverage and not options.seed_config) or (not options.coverage and options.seed_config):
        print '--coverage and --seed-conf can only be used together'
        sys.exit(1)

    if options.list_grids:
        display_grids_list(grids)
    elif options.grid_name:
        display_grids({options.grid_name: grids[options.grid_name]}, coverage=coverage)
    else:
        display_grids(grids, coverage=coverage)
    


