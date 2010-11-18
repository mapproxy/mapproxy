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

import os
import shutil

from optparse import OptionParser
from textwrap import dedent

def main():
    usage  = "usage: %prog [options] caches"
    usage += dedent("""\n
     Removes cached data from one or more caches.
     
     Examples
       Remove level 10 and above (11, 12, 13, ...)
         $ %prog cache_EPSG4326 --from 10
       Remove level 8 - 10
         $ %prog cache_EPSG4326 --from 8 --to 10
       Remove all levels
         $ %prog cache_EPSG4326 --all

     Note: You need to point %prog directly to one (or more)
           cache directories (e.g. var/cache_data/cache_*).
           TODO: Support for mapproxy.yaml.""")
    
    parser = OptionParser(usage)
    parser.add_option("--from", type="int", metavar='n',
                      dest="from_level", default=None,
                      help="remove from this level (inclusive)")
    parser.add_option("--to", type="int", metavar='n',
                      dest="to_level", default=None,
                      help="remove to this level (inclusive)")
    parser.add_option("-n", "--dry-run",
                      action="store_true", dest="dry_run", default=False,
                      help="do not remove anything, just print output what"
                      " would be removed")
    parser.add_option("-a", "--all",
                      action="store_true", dest="remove_all", default=False,
                      help="remove all levels")
    
    (options, args) = parser.parse_args()
    if len(args) == 0:
        parser.error('need one cache directory (see --help)')
    
    if not options.from_level and not options.to_level and not options.remove_all:
        parser.error('need --from or/and --to (use --all to remove all levels)')

    for cache_dir in args:
        remove_levels(cache_dir, options.from_level, options.to_level, options.dry_run)

def remove_levels(cache_dir, from_level, to_level, dry_run=True):
    if from_level is None:
        from_level = 0
    if to_level is None:
        to_level = 1e99
    
    for filename in os.listdir(cache_dir):
        level_dir = os.path.join(cache_dir, filename)
        if os.path.isdir(level_dir) and filename.isdigit():
            level = int(filename, 10)
            if from_level <= level <= to_level:
                print 'rm -r %s' % os.path.join(cache_dir, filename)
                if not dry_run:
                    shutil.rmtree(level_dir)

if __name__ == '__main__':
    main()