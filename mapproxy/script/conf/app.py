# -:- encoding: utf-8 -:-
# This file is part of the MapProxy project.
# Copyright (C) 2013 Omniscale <http://omniscale.de>
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
import os
import optparse
import logging
import textwrap
import datetime
import xml.etree.ElementTree
import yaml

from contextlib import contextmanager
from cStringIO import StringIO

from .sources import sources
from .layers import layers
from .caches import caches
from .seeds import seeds
from .utils import update_config, MapProxyYAMLDumper, download_capabilities

from mapproxy.config.loader import load_configuration
from mapproxy.util.ext.wmsparse import parse_capabilities

def setup_logging(level=logging.INFO):
    mapproxy_log = logging.getLogger('mapproxy')
    mapproxy_log.setLevel(level)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "[%(asctime)s] %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    mapproxy_log.addHandler(ch)

def write_header(f, capabilities):
    print >>f, '# MapProxy configuration automatically generated from:'
    print >>f, '#   %s' % capabilities
    print >>f, '#'
    print >>f, '# NOTE: The generated configuration can be highly inefficient,'
    print >>f, '#       especially when multiple layers and caches are requested at once.'
    print >>f, '#       Make sure you understand the generated configuration!'
    print >>f, '#'
    print >>f, '# Created on %s with:' % datetime.datetime.now()
    print >>f, ' \\\n'.join(textwrap.wrap(' '.join(sys.argv), initial_indent='# ', subsequent_indent='#    '))
    print >>f, ''


@contextmanager
def file_or_stdout(name):
    if name == '-':
        yield sys.stdout
    else:
        with open(name, 'wb') as f:
            yield f

def config_command(args):
    parser = optparse.OptionParser("usage: %prog autoconfig [options]")

    parser.add_option('--capabilities',
        help="URL or filename of WMS 1.1.1/1.3.0 capabilities document")
    parser.add_option('--output', help="filename for created MapProxy config [default: -]", default="-")
    parser.add_option('--output-seed', help="filename for created seeding config")

    parser.add_option('--base', help='base config to include in created MapProxy config')

    parser.add_option('--overwrite',
        help='YAML file with overwrites for the created MapProxy config')
    parser.add_option('--overwrite-seed',
        help='YAML file with overwrites for the created seeding config')

    parser.add_option('--force', default=False, action='store_true',
        help="overwrite existing files")

    options, args = parser.parse_args(args)

    if not options.capabilities:
        parser.print_help()
        print >>sys.stderr, "\nERROR: --capabilities required"
        return 2

    if not options.output and not options.output_seed:
        parser.print_help()
        print >>sys.stderr, "\nERROR: --output and/or --output-seed required"
        return 2

    if not options.force:
        if options.output and options.output != '-' and os.path.exists(options.output):
            print >>sys.stderr, "\nERROR: %s already exists, use --force to overwrite" % options.output
            return 2
        if options.output_seed and options.output_seed != '-' and os.path.exists(options.output_seed):
            print >>sys.stderr, "\nERROR: %s already exists, use --force to overwrite" % options.output_seed
            return 2

    log = logging.getLogger('mapproxy_conf_cmd')
    log.addHandler(logging.StreamHandler())

    setup_logging(logging.WARNING)

    srs_grids = {}
    if options.base:
        base = load_configuration(options.base)
        for name, grid_conf in base.grids.iteritems():
            if name.startswith('GLOBAL_'):
                continue
            srs_grids[grid_conf.tile_grid().srs.srs_code] = name

    cap_doc = options.capabilities
    if cap_doc.startswith(('http://', 'https://')):
        cap_doc = download_capabilities(options.capabilities).read()
    else:
        cap_doc = open(cap_doc, 'rb').read()

    try:
        cap = parse_capabilities(StringIO(cap_doc))
    except (xml.etree.ElementTree.ParseError, ValueError), ex:
        print >>sys.stderr, ex
        print >>sys.stderr, cap_doc[:1000] + ('...' if len(cap_doc) > 1000 else '')
        return 3

    overwrite = None
    if options.overwrite:
        with open(options.overwrite, 'rb') as f:
            overwrite = yaml.load(f)

    overwrite_seed = None
    if options.overwrite_seed:
        with open(options.overwrite_seed, 'rb') as f:
            overwrite_seed = yaml.load(f)

    conf = {}
    if options.base:
        conf['base'] = os.path.abspath(options.base)

    conf['services'] = {'wms': {'md': {'title': cap.metadata()['title']}}}
    if overwrite:
        conf['services'] = update_config(conf['services'], overwrite.pop('service', {}))

    conf['sources'] = sources(cap)
    if overwrite:
        conf['sources'] = update_config(conf['sources'], overwrite.pop('sources', {}))

    conf['caches'] = caches(cap, conf['sources'], srs_grids=srs_grids)
    if overwrite:
        conf['caches'] = update_config(conf['caches'], overwrite.pop('caches', {}))

    conf['layers'] = layers(cap, conf['caches'])
    if overwrite:
        conf['layers'] = update_config(conf['layers'], overwrite.pop('layers', {}))

    if overwrite:
        conf = update_config(conf, overwrite)


    seed_conf = {}
    seed_conf['seeds'], seed_conf['cleanups'] = seeds(cap, conf['caches'])
    if overwrite_seed:
        seed_conf = update_config(seed_conf, overwrite_seed)


    if options.output:
        with file_or_stdout(options.output) as f:
            write_header(f, options.capabilities)
            yaml.dump(conf, f, default_flow_style=False, Dumper=MapProxyYAMLDumper)
    if options.output_seed:
        with file_or_stdout(options.output_seed) as f:
            write_header(f, options.capabilities)
            yaml.dump(seed_conf, f, default_flow_style=False, Dumper=MapProxyYAMLDumper)

    return 0