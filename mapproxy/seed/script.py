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

from __future__ import print_function

import errno
import os
import re
import signal
import sys
import time
import logging
from logging.config import fileConfig

from subprocess import Popen
from optparse import OptionParser, OptionValueError

from mapproxy.config.loader import load_configuration, ConfigurationError
from mapproxy.seed.config import load_seed_tasks_conf
from mapproxy.seed.seeder import seed, SeedInterrupted
from mapproxy.seed.cleanup import cleanup
from mapproxy.seed.util import (format_seed_task, format_cleanup_task,
    ProgressLog, ProgressStore)
from mapproxy.seed.cachelock import CacheLocker

SECONDS_PER_DAY = 60 * 60 * 24
SECONDS_PER_MINUTE = 60

def setup_logging(logging_conf=None):
    if logging_conf is not None:
        fileConfig(logging_conf, {'here': './'})

    mapproxy_log = logging.getLogger('mapproxy')
    mapproxy_log.setLevel(logging.WARN)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "[%(asctime)s] %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    mapproxy_log.addHandler(ch)


def check_duration(option, opt, value, parser):
    try:
        setattr(parser.values, option.dest, parse_duration(value))
    except ValueError:
        raise OptionValueError(
            "option %s: invalid duration value: %r, expected (10s, 15m, 0.5h, 3d, etc)"
            % (opt, value),
        )


def parse_duration(string):
    match = re.match(r'^(\d*.?\d+)(s|m|h|d)', string)
    if not match:
        raise ValueError('invalid duration, not in format: 10s, 0.5h, etc.')
    duration = float(match.group(1))
    unit = match.group(2)
    if unit == 's':
        return duration
    duration *= 60
    if unit == 'm':
        return duration
    duration *= 60
    if unit == 'h':
        return duration
    duration *= 24
    return duration


class SeedScript(object):
    usage = "usage: %prog [options] seed_conf"
    parser = OptionParser(usage)
    parser.add_option("-q", "--quiet",
                      action="count", dest="quiet", default=0,
                      help="reduce number of messages to stdout, repeat to disable progress output")
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

    parser.add_option("--use-cache-lock",
                      action="store_true", default=False,
                      help="use locking to prevent multiple mapproxy-seed calls "
                      "to seed the same cache")

    parser.add_option("--continue", dest='continue_seed',
                      action="store_true", default=False,
                      help="continue an aborted seed progress")

    parser.add_option("--progress-file", dest='progress_file',
                      default=None,
                      help="filename for storing the seed progress (for --continue option)")

    parser.add_option("--duration", dest="duration",
                      help="stop seeding after (120s, 15m, 4h, 0.5d, etc)",
                      type=str, action="callback", callback=check_duration)

    parser.add_option("--reseed-file", dest="reseed_file",
                      help="start of last re-seed", metavar="FILE",
                      default=None)
    parser.add_option("--reseed-interval", dest="reseed_interval",
                      help="only start seeding if --reseed-file is older then --reseed-interval",
                      metavar="DURATION",
                      type=str, action="callback", callback=check_duration,
                      default=None)

    parser.add_option("--log-config", dest='logging_conf', default=None,
                      help="logging configuration")

    def __call__(self):
        (options, args) = self.parser.parse_args()

        if len(args) != 1 and not options.seed_file:
            self.parser.print_help()
            sys.exit(1)

        if not options.seed_file:
            if len(args) != 1:
                self.parser.error('missing seed_conf file as last argument or --seed-conf option')
            else:
                options.seed_file = args[0]

        if not options.conf_file:
            self.parser.error('missing mapproxy configuration -f/--proxy-conf')

        setup_logging(options.logging_conf)

        if options.duration:
            # calls with --duration are handled in call_with_duration
            sys.exit(self.call_with_duration(options, args))

        try:
            mapproxy_conf = load_configuration(options.conf_file, seed=True)
        except ConfigurationError as ex:
            print("ERROR: " + '\n\t'.join(str(ex).split('\n')))
            sys.exit(2)

        if options.use_cache_lock:
            cache_locker = CacheLocker('.mapproxy_seed.lck')
        else:
            cache_locker = None

        if not sys.stdout.isatty() and options.quiet == 0:
            # disable verbose output for non-ttys
            options.quiet = 1

        progress = None
        if options.continue_seed or options.progress_file:
            if not options.progress_file:
                options.progress_file = '.mapproxy_seed_progress'
            progress = ProgressStore(options.progress_file,
                                     continue_seed=options.continue_seed)

        if options.reseed_file:
            if not os.path.exists(options.reseed_file):
                # create --reseed-file if missing
                with open(options.reseed_file, 'w'):
                    pass
            else:
                if progress and not os.path.exists(options.progress_file):
                    # we have an existing --reseed-file but no --progress-file
                    # meaning the last seed call was completed
                    if options.reseed_interval and (
                        os.path.getmtime(options.reseed_file) > (time.time() - options.reseed_interval)
                    ):
                        print("no need for re-seeding")
                        sys.exit(1)
                    os.utime(options.reseed_file, (time.time(), time.time()))

        with mapproxy_conf:
            try:
                seed_conf = load_seed_tasks_conf(options.seed_file, mapproxy_conf)
                seed_names, cleanup_names = self.task_names(seed_conf, options)
                seed_tasks = seed_conf.seeds(seed_names)
                cleanup_tasks = seed_conf.cleanups(cleanup_names)
            except ConfigurationError as ex:
                print("error in configuration: " + '\n\t'.join(str(ex).split('\n')))
                sys.exit(2)

            if options.summary:
                print('========== Seeding tasks ==========')
                for task in seed_tasks:
                    print(format_seed_task(task))
                print('========== Cleanup tasks ==========')
                for task in cleanup_tasks:
                    print(format_cleanup_task(task))
                return 0

            try:
                if options.interactive:
                    seed_tasks, cleanup_tasks = self.interactive(seed_tasks, cleanup_tasks)

                if seed_tasks:
                    print('========== Seeding tasks ==========')
                    print('Start seeding process (%d task%s)' % (
                        len(seed_tasks), 's' if len(seed_tasks) > 1 else ''))
                    logger = ProgressLog(verbose=options.quiet==0, silent=options.quiet>=2,
                        progress_store=progress)
                    seed(seed_tasks, progress_logger=logger, dry_run=options.dry_run,
                         concurrency=options.concurrency, cache_locker=cache_locker,
                         skip_geoms_for_last_levels=options.geom_levels)
                if cleanup_tasks:
                    print('========== Cleanup tasks ==========')
                    print('Start cleanup process (%d task%s)' % (
                        len(cleanup_tasks), 's' if len(cleanup_tasks) > 1 else ''))
                    logger = ProgressLog(verbose=options.quiet==0, silent=options.quiet>=2,
                        progress_store=progress)
                    cleanup(cleanup_tasks, verbose=options.quiet==0, dry_run=options.dry_run,
                            concurrency=options.concurrency, progress_logger=logger,
                            skip_geoms_for_last_levels=options.geom_levels)
            except SeedInterrupted:
                print('\ninterrupted...')
                return 3
            except KeyboardInterrupt:
                print('\nexiting...')
                return 2

            if progress:
                progress.remove()

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
                    print('unknown seed tasks: %s' % (', '.join(missing), ))
                    print('available seed tasks: %s' % (', '.join(avail_seed_names), ))
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
                    print('unknown cleanup tasks: %s' % (', '.join(missing), ))
                    print('available cleanup tasks: %s' % (', '.join(avail_cleanup_names), ))
                    sys.exit(1)
        elif not options.seed_names:
            cleanup_names = None # cleanup all

        return seed_names, cleanup_names

    def call_with_duration(self, options, args):
        # --duration is implemented by calling mapproxy-seed again in a separate
        # process (but without --duration) and terminating that process
        # after --duration

        argv = sys.argv[:]
        for i, arg in enumerate(sys.argv):
            if arg == '--duration':
                argv = sys.argv[:i] + sys.argv[i+2:]
                break
            elif arg.startswith('--duration='):
                argv = sys.argv[:i] + sys.argv[i+1:]
                break

        # call mapproxy-seed again, poll status, terminate after --duration
        cmd = Popen(args=argv)
        start = time.time()
        while True:
            if (time.time() - start) > options.duration:
                try:
                    cmd.send_signal(signal.SIGINT)
                    # try to stop with sigint
                    # send sigterm after 10 seconds
                    for _ in range(10):
                        time.sleep(1)
                        if cmd.poll() is not None:
                            break
                    else:
                        cmd.terminate()
                except OSError as ex:
                    if ex.errno != errno.ESRCH:  # no such process
                        raise
                return 0
            if cmd.poll() is not None:
                return cmd.returncode
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                # force termination
                start = 0


    def interactive(self, seed_tasks, cleanup_tasks):
        selected_seed_tasks = []
        print('========== Select seeding tasks ==========')
        for task in seed_tasks:
            print(format_seed_task(task))
            if ask_yes_no_question('    Seed this task (y/n)? '):
                selected_seed_tasks.append(task)
        seed_tasks = selected_seed_tasks

        selected_cleanup_tasks = []
        print('========== Select cleanup tasks ==========')
        for task in cleanup_tasks:
            print(format_cleanup_task(task))
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
