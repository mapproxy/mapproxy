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

from __future__ import division, with_statement
import sys
import optparse
import itertools

DEFAULT_DPIS = {
    'OGC': 2.54/(0.00028 * 100),
}

def values_from_stdin():
    values = []
    for line in sys.stdin:
        line = line.split('#', 1)[0]
        if not line.strip():
            break
        values.append(float(line))
    return values

def scale_to_res(scale_denom, dpi, unit_factor):
    m_per_px = 2.54 / (dpi * 100)
    return scale_denom * m_per_px / unit_factor

def res_to_scale(res, dpi, unit_factor):
    m_per_px = 2.54 / (dpi * 100)
    return res / m_per_px * unit_factor

def format_simple(i, scale, res):
    return '%20.10f # %2d %20.8f' % (res, i, scale)

def format_list(i, scale, res):
    return '    %20.10f, # %2d %20.8f' % (res, i, scale)

def repeated_values(values, n):
    current_factor = 1
    step_factor = 10
    result = []
    for i, value in enumerate(itertools.islice(itertools.cycle(values), n)):
        if i != 0 and i % len(values) == 0:
            current_factor *= step_factor
        result.append(value/current_factor)
    return result

def fill_values(values, n):
    return values + [values[-1]/(2**x) for x in range(1, n)]


def scales_command(args=None):
    parser = optparse.OptionParser("%prog scales [options] scale/resolution[, ...]")
    parser.add_option("-l", "--levels", default=1, type=int, metavar='1',
        help="number of resolutions/scales to calculate")
    parser.add_option("-d", "--dpi", default='OGC',
        help="DPI to convert scales (use OGC for .28mm based DPI)")
    parser.add_option("--unit", default='m', metavar='m',
        help="use resolutions in meter (m) or degrees (d)")
    parser.add_option("--eval", default=False, action='store_true',
        help="evaluate args as Python expression. For example: 360/256")
    parser.add_option("--repeat", default=False, action='store_true',
        help="repeat all values, each time /10. For example: 1000 500 250 results in 1000 500 250 100 50 25 10...")
    parser.add_option("--res-to-scale", default=False, action='store_true',
        help="convert resolutions to scale")
    parser.add_option("--as-res-config", default=False, action='store_true',
        help="output as resulution list for MapProxy grid configuration")
    
    if args:
        args = args[1:] # remove script name
    (options, args) = parser.parse_args(args)
    options.levels = max(options.levels, len(args))
    
    dpi = float(DEFAULT_DPIS.get(options.dpi, options.dpi))
    
    if not args:
        parser.print_help()
        sys.exit(1)
    
    if args[0] == '-':
        values = values_from_stdin()
    elif options.eval:
        values = map(eval, args)
    else:
        values = map(float, args)
    
    if options.repeat:
        values = repeated_values(values, options.levels)
    
    if len(values) < options.levels:
        values = fill_values(values, options.levels)
    
    unit_factor = 1
    if options.unit == 'd':
        # calculated from well-known scale set GoogleCRS84Quad
        unit_factor = 111319.4907932736
    
    calc = scale_to_res
    if options.res_to_scale:
        calc = res_to_scale
    
    if options.as_res_config:
        print '    res: ['
        print '         #  res            level        scale'
        format = format_list
    else:
        format = format_simple
    
    for i, value in enumerate(values):
        print format(i, value, calc(value, dpi, unit_factor))
    
    if options.as_res_config:
        print '    ]'
