# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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

from __future__ import with_statement

import sys
import logging

from optparse import OptionParser
from mapproxy.util import local_base_config
from mapproxy.config.loader import load_configuration, ConfigurationError
from mapproxy.seed.config import load_seed_tasks_conf
from mapproxy.seed.seeder import seed
from mapproxy.seed.cleanup import cleanup
from mapproxy.seed.util import format_seed_task, format_cleanup_task, ProgressLog


def setup_logging():
    mapproxy_log = logging.getLogger('mapproxy')
    mapproxy_log.setLevel(logging.WARN)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "[%(asctime)s] %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    mapproxy_log.addHandler(ch)

class SeedScript(object):
    usage = "usage: %prog [options] seed_conf"
    parser = OptionParser(usage)
    parser.add_option("-q", "--quiet",
                      action="count", dest="quiet", default=0,
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

        setup_logging()
        
        try:
            mapproxy_conf = load_configuration(options.conf_file, seed=True)
        except ConfigurationError, ex:
            print "ERROR: " + '\n\t'.join(str(ex).split('\n'))
            sys.exit(2)

        with local_base_config(mapproxy_conf.base_config):
            try:
                seed_conf = load_seed_tasks_conf(options.seed_file, mapproxy_conf)
                seed_names, cleanup_names = self.task_names(seed_conf, options)
                seed_tasks = seed_conf.seeds(seed_names)
                cleanup_tasks = seed_conf.cleanups(cleanup_names)
            except ConfigurationError, ex:
                print "error in configuration: " + '\n\t'.join(str(ex).split('\n'))
                sys.exit(2)

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
                    logger = ProgressLog(verbose=options.quiet==0, silent=options.quiet>=2)
                    seed(seed_tasks, progress_logger=logger, dry_run=options.dry_run,
                         concurrency=options.concurrency,
                         skip_geoms_for_last_levels=options.geom_levels)
                if cleanup_tasks:
                    print '========== Cleanup tasks =========='
                    print 'Start cleanup process (%d task%s)' % (
                        len(cleanup_tasks), 's' if len(cleanup_tasks) > 1 else '')
                    logger = ProgressLog(verbose=options.quiet==0, silent=options.quiet>=2)
                    cleanup(cleanup_tasks, verbose=options.quiet==0, dry_run=options.dry_run,
                            concurrency=options.concurrency, progress_logger=logger,
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

if __name__ == '__main__':
    main()
