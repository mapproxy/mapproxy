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

from mapproxy.config.loader import load_configuration, ConfigurationError

def wrap_with_single_quotation(value):
    if isinstance(value, basestring):
        value = "'%s'" % (value,)
    return value

def default_origin(origin):
    if origin is None:
        origin = 'sw'
    return wrap_with_single_quotation(origin)

def format(grid_conf):
    print '%s:' % (grid_conf.conf['name'],)
    print '    Configuration:'
    for key, value in grid_conf.conf.items():
        if key == 'name':
            continue
        print '        %s: %s' % (key, wrap_with_single_quotation(value))
    tile_grid = grid_conf.tile_grid()
    print '        tile_size: [%d, %d]' % (tile_grid.tile_size[0], tile_grid.tile_size[1])
    print '        origin: %s' % (default_origin(tile_grid.origin),)
    print '    Levels/Resolutions:'
    for level, res in enumerate(tile_grid.resolutions):
        print "        %.2d:  %r" % (level, res)

def display(grids, detailed_grid=None, list_grids=False):
    print '========== Configured Grids =========='
    if list_grids:
        for grid_name in grids.keys():
            print grid_name
    else:
        for grid_name, grid_conf in grids.items():
            if detailed_grid is not None:
                if grid_name == detailed_grid:
                    format(grid_conf)
            else:
                format(grid_conf)

def grids_command(args=None):
    parser = optparse.OptionParser("%prog grids [options] mapproxy_conf")
    parser.add_option("-f", "--mapproxy-conf", dest="mapproxy_conf",
        help="Existing MapProxy configuration.")
    parser.add_option("-g", "--grid", dest="grid_name",
        help="Display only informations about the specific grid.")
    parser.add_option("-l", "--list", dest="list_grids", action="store_true", default=False, help="List names of configured grids")
    if args:
        args = args[1:] # remove script name
    (options, args) = parser.parse_args(args)
    if not options.mapproxy_conf:
        if len(args) != 1:
            parser.print_help()
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

    display(grids, detailed_grid=options.grid_name, list_grids=options.list_grids)
    


