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

import sys
import optparse

from mapproxy.config.loader import load_configuration

def format_conf_value(value):
    if isinstance(value, tuple):
        # YAMl only supports lists, convert for clarity
        value = list(value)
    return repr(value)

def display_grid(grid_conf):
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

    for key in sorted(conf_dict):
        if key == 'name':
            continue
        print '        %s: %s' % (key, format_conf_value(conf_dict[key]))
    print '    Levels: Resolutions, # Tiles x * Tiles y = total tiles:' 
    max_digits = max([len("%r" % (res,)) for level, res in enumerate(tile_grid.resolutions)])
    for level, res in enumerate(tile_grid.resolutions):
        tiles_in_x, tiles_in_y = tile_grid.grid_sizes[level]
        total_tiles = tiles_in_x * tiles_in_y
        spaces = max_digits - len("%r" % (res,)) + 1
        print "        %.2d:  %r,%s# %d * %d = %d" % (level, res, ' '*spaces, tiles_in_x, tiles_in_y, total_tiles)

def display_grids_list(grids):
    for grid_name in sorted(grids.keys()):
        print grid_name

def display_grids(grids, detailed_grid=None):
    for i, grid_name in enumerate(sorted(grids.keys())):
        if i != 0:
            print
        display_grid(grids[grid_name])

def grids_command(args=None):
    parser = optparse.OptionParser("%prog grids [options] mapproxy_conf")
    parser.add_option("-f", "--mapproxy-conf", dest="mapproxy_conf",
        help="MapProxy configuration.")
    parser.add_option("-g", "--grid", dest="grid_name",
        help="Display only information about the specified grid.")
    parser.add_option("-l", "--list", dest="list_grids", action="store_true", default=False, help="List names of configured grids")

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
        grids = proxy_configuration.grids
    except IOError, e:
        print >>sys.stderr, 'ERROR: ', "%s: '%s'" % (e.strerror, e.filename)
        sys.exit(2)

    if options.grid_name:
        options.grid_name = options.grid_name.lower()
        # ignore case for keys
        grids = dict((key.lower(), value) for (key, value) in grids.items())
        if not grids.get(options.grid_name, False):
            print 'grid not found: %s' % (options.grid_name,)
            sys.exit(1)

    if options.list_grids:
        display_grids_list(grids)
    elif options.grid_name:
        display_grids({options.grid_name: grids[options.grid_name]})
    else:
        display_grids(grids)
    


