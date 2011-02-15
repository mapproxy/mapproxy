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

from __future__ import with_statement

import os
import sys
import shutil

from optparse import OptionParser
from textwrap import dedent
from mapproxy.util import local_base_config
from mapproxy.config.loader import load_configuration
from mapproxy.seed.config import load_seed_tasks_conf
from mapproxy.seed.seeder import seed
from mapproxy.seed.cleanup import cleanup
from mapproxy.seed.util import format_seed_task, format_cleanup_task


class SeedScript(object):
    usage = "usage: %prog [options] seed_conf"
    parser = OptionParser(usage)
    parser.add_option("-q", "--quiet",
                      action="store_false", dest="verbose", default=True,
                      help="don't print status messages to stdout")
    parser.add_option("-s", "--seed-conf",
                      dest="seed_file", default=None,
                      help="seed configuration")
    parser.add_option("-f", "--proxy-conf",
                      dest="conf_file", default=None,
                      help="proxy configuration")
    parser.add_option("-c", "--concurrency", type="int",
                      dest="concurrency", default=2,
                      help="number of parallel seed processes")
    parser.add_option("-n", "--dry-run",
                      action="store_true", dest="dry_run", default=False,
                      help="do not seed, just print output")    
    parser.add_option("-l", "--skip-geoms-for-last-levels",
                      type="int", dest="geom_levels", default=0,
                      metavar="N",
                      help="do not check for intersections between tiles"
                           " and seed geometries on the last N levels")
    parser.add_option("--summary",
                      action="store_true", dest="summary", default=False,
                      help="print summary with all seeding tasks and exit."
                           " does not seed anything.")
    parser.add_option("-i", "--interactive",
                      action="store_true", dest="interactive", default=False,
                      help="print each task description and ask if it should be seeded")
    
    parser.add_option("--seed",
                      action="append", dest="seed_names", metavar='task1,task2,...',
                      help="seed only the named tasks. cleanup is disabled unless "
                      "--cleanup is used. use ALL to select all tasks")

    parser.add_option("--cleanup",
                      action="append", dest="cleanup_names", metavar='task1,task2,...',
                      help="cleanup only the named tasks. seeding is disabled unless "
                      "--seed is used. use ALL to select all tasks")

    def __call__(self):
        (options, args) = self.parser.parse_args()
        if not options.seed_file:
            if len(args) != 1:
                self.parser.error('missing seed_conf file as last argument or --seed-conf option')
            else:
                options.seed_file = args[0]
    
        if not options.conf_file:
            self.parser.error('missing mapproxy configuration -f/--proxy-conf')
    
        mapproxy_conf = load_configuration(options.conf_file, seed=True)

        with local_base_config(mapproxy_conf.base_config):
            seed_conf = load_seed_tasks_conf(options.seed_file, mapproxy_conf)
            seed_names, cleanup_names = self.task_names(seed_conf, options)
            seed_tasks = seed_conf.seeds(seed_names)
            cleanup_tasks = seed_conf.cleanups(cleanup_names)

            if options.summary:
                print '========== Seeding tasks =========='
                for task in seed_tasks:
                    print format_seed_task(task)
                print '========== Cleanup tasks =========='
                for task in cleanup_tasks:
                    print format_cleanup_task(task)
                return 0

            try:
                if options.interactive:
                    seed_tasks, cleanup_tasks = self.interactive(seed_tasks, cleanup_tasks)

                if seed_tasks:
                    print '========== Seeding tasks =========='
                    print 'Start seeding process (%d task%s)' % (
                        len(seed_tasks), 's' if len(seed_tasks) > 1 else '')
                    seed(seed_tasks, verbose=options.verbose, dry_run=options.dry_run,
                         concurrency=options.concurrency,
                         skip_geoms_for_last_levels=options.geom_levels)
                if cleanup_tasks:
                    print '========== Cleanup tasks =========='
                    print 'Start cleanup process (%d task%s)' % (
                        len(cleanup_tasks), 's' if len(cleanup_tasks) > 1 else '')
                    cleanup(cleanup_tasks, verbose=options.verbose, dry_run=options.dry_run,
                            concurrency=options.concurrency,
                            skip_geoms_for_last_levels=options.geom_levels)
            except KeyboardInterrupt:
                print '\nexiting...'
                return 2
    
    def task_names(self, seed_conf, options):
        seed_names = cleanup_names = []
    
        if options.seed_names:
            seed_names = split_comma_seperated_option(options.seed_names)
            if seed_names == ['ALL']:
                seed_names = None
            else:
                avail_seed_names = seed_conf.seed_tasks_names()
                missing = set(seed_names).difference(avail_seed_names)
                if missing:
                    print 'unknown seed tasks: %s' % (', '.join(missing), )
                    print 'available seed tasks: %s' % (', '.join(avail_seed_names), )
                    sys.exit(1)
        elif not options.cleanup_names:
            seed_names = None # seed all

        if options.cleanup_names:
            cleanup_names = split_comma_seperated_option(options.cleanup_names)
            if cleanup_names == ['ALL']:
                cleanup_names = None
            else:
                avail_cleanup_names = seed_conf.cleanup_tasks_names()
                missing = set(cleanup_names).difference(avail_cleanup_names)
                if missing:
                    print 'unknown cleanup tasks: %s' % (', '.join(missing), )
                    print 'available cleanup tasks: %s' % (', '.join(avail_cleanup_names), )
                    sys.exit(1)
        elif not options.seed_names:
            cleanup_names = None # cleanup all
    
        return seed_names, cleanup_names

    def interactive(self, seed_tasks, cleanup_tasks):
        selected_seed_tasks = []
        print '========== Select seeding tasks =========='
        for task in seed_tasks:
            print format_seed_task(task)
            if ask_yes_no_question('    Seed this task (y/n)? '):
                selected_seed_tasks.append(task)
        seed_tasks = selected_seed_tasks

        selected_cleanup_tasks = []
        print '========== Select cleanup tasks =========='
        for task in cleanup_tasks:
            print format_cleanup_task(task)
            if ask_yes_no_question('    Cleanup this task (y/n)? '):
                selected_cleanup_tasks.append(task)
        cleanup_tasks = selected_cleanup_tasks
        return seed_tasks, cleanup_tasks

def main():
    return SeedScript()()

def ask_yes_no_question(question):
    while True:
        resp = raw_input(question).lower()
        if resp in ('y', 'yes'): return True
        elif resp in ('n', 'no'): return False

def split_comma_seperated_option(option):
    """
    >>> split_comma_seperated_option(['foo,bar', 'baz'])
    ['foo', 'bar', 'baz']
    """
    result = []
    if option:
        for args in option:
            result.extend(args.split(','))
    return result

def cleanup_main():
    print "#" *65
    print "# Warning: This script is deprecated."
    print "# Please use the mapproxy-seed tool with the cleanup options."
    print "#" *65
    
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
