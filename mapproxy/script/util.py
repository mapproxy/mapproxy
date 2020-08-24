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

from __future__ import print_function

import io
import os
import optparse
import re
import shutil
import sys
import textwrap
import logging

from mapproxy.compat import iteritems
from mapproxy.script.conf.app import config_command
from mapproxy.script.defrag import defrag_command
from mapproxy.script.export import export_command
from mapproxy.script.grids import grids_command
from mapproxy.script.scales import scales_command
from mapproxy.script.wms_capabilities import wms_capabilities_command
from mapproxy.version import version


def setup_logging(level=logging.INFO, format=None):
    mapproxy_log = logging.getLogger('mapproxy')
    mapproxy_log.setLevel(level)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    if not format:
        format = "[%(asctime)s] %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(format)
    ch.setFormatter(formatter)
    mapproxy_log.addHandler(ch)

def serve_develop_command(args):
    parser = optparse.OptionParser("usage: %prog serve-develop [options] mapproxy.yaml")
    parser.add_option("-b", "--bind",
                      dest="address", default='127.0.0.1:8080',
                      help="Server socket [127.0.0.1:8080]. Use 0.0.0.0 for external access. :1234 to change port.")
    parser.add_option("--debug", default=False, action='store_true',
                      dest="debug",
                      help="Enable debug mode")
    options, args = parser.parse_args(args)

    if len(args) != 2:
        parser.print_help()
        print("\nERROR: MapProxy configuration required.")
        sys.exit(1)

    mapproxy_conf = args[1]

    host, port = parse_bind_address(options.address)

    if options.debug and host not in ('localhost', '127.0.0.1'):
        print(textwrap.dedent("""\
        ################# WARNING! ##################
        Running debug mode with non-localhost address
        is a serious security vulnerability.
        #############################################\
        """))


    if options.debug:
        setup_logging(level=logging.DEBUG)
    else:
        setup_logging()
    from mapproxy.wsgiapp import make_wsgi_app
    from mapproxy.config.loader import ConfigurationError
    from mapproxy.util.ext.serving import run_simple
    try:
        app = make_wsgi_app(mapproxy_conf, debug=options.debug)
    except ConfigurationError:
        sys.exit(2)

    extra_files = app.config_files.keys()

    if options.debug:
        try:
            from repoze.profile import ProfileMiddleware
            app = ProfileMiddleware(
               app,
               log_filename='/tmp/mapproxy_profile.log',
               discard_first_request=True,
               flush_at_shutdown=True,
               path='/__profile__',
               unwind=False,
            )
            print('Installed profiler at /__profile__')
        except ImportError:
            pass

    run_simple(host, port, app, use_reloader=True, processes=1,
        threaded=True, passthrough_errors=True,
        extra_files=extra_files)

def serve_multiapp_develop_command(args):
    parser = optparse.OptionParser("usage: %prog serve-multiapp-develop [options] projects/")
    parser.add_option("-b", "--bind",
                      dest="address", default='127.0.0.1:8080',
                      help="Server socket [127.0.0.1:8080]")
    parser.add_option("--debug", default=False, action='store_true',
                      dest="debug",
                      help="Enable debug mode")
    options, args = parser.parse_args(args)

    if len(args) != 2:
        parser.print_help()
        print("\nERROR: MapProxy projects directory required.")
        sys.exit(1)

    mapproxy_conf_dir = args[1]

    host, port = parse_bind_address(options.address)

    if options.debug and host not in ('localhost', '127.0.0.1'):
        print(textwrap.dedent("""\
        ################# WARNING! ##################
        Running debug mode with non-localhost address
        is a serious security vulnerability.
        #############################################\
        """))

    setup_logging()
    from mapproxy.multiapp import make_wsgi_app
    from mapproxy.util.ext.serving import run_simple
    app = make_wsgi_app(mapproxy_conf_dir, debug=options.debug)

    run_simple(host, port, app, use_reloader=True, processes=1,
        threaded=True, passthrough_errors=True)


def parse_bind_address(address, default=('localhost', 8080)):
    """
    >>> parse_bind_address('80')
    ('localhost', 80)
    >>> parse_bind_address('0.0.0.0')
    ('0.0.0.0', 8080)
    >>> parse_bind_address('0.0.0.0:8081')
    ('0.0.0.0', 8081)
    """
    if ':' in address:
        host, port = address.split(':', 1)
        port = int(port)
    elif re.match(r'^\d+$', address):
        host = default[0]
        port = int(address)
    else:
        host = address
        port = default[1]
    return host, port


def create_command(args):
    cmd = CreateCommand(args)
    cmd.run()

class CreateCommand(object):
    templates = {
        'base-config': {},
        'wsgi-app': {},
        'log-ini': {},
    }

    def __init__(self, args):
        parser = optparse.OptionParser("usage: %prog create [options] [destination]")
        parser.add_option("-t", "--template", dest="template",
            help="Create a configuration from this template.")
        parser.add_option("-l", "--list-templates", dest="list_templates",
            action="store_true", default=False,
            help="List all available configuration templates.")
        parser.add_option("-f", "--mapproxy-conf", dest="mapproxy_conf",
            help="Existing MapProxy configuration (required for some templates).")
        parser.add_option("--force", dest="force", action="store_true",
            default=False, help="Force operation (e.g. overwrite existing files).")

        self.options, self.args = parser.parse_args(args)
        self.parser = parser

    def log_error(self, msg, *args):
        print('ERROR:', msg % args, file=sys.stderr)

    def run(self):

        if self.options.list_templates:
            print_items(self.templates, title="Available templates")
            sys.exit(1)
        elif self.options.template:
            if self.options.template not in self.templates:
                self.log_error("unknown template " + self.options.template)
                sys.exit(1)

            if len(self.args) != 2:
                self.log_error("template requires destination argument")
                sys.exit(1)

            sys.exit(
                getattr(self, 'template_' + self.options.template.replace('-', '_'))()
            )
        else:
            self.parser.print_help()
            sys.exit(1)

    @property
    def mapproxy_conf(self):
        if not self.options.mapproxy_conf:
            self.parser.print_help()
            self.log_error("template requires --mapproxy-conf option")
            sys.exit(1)
        return os.path.abspath(self.options.mapproxy_conf)

    def template_dir(self):
        import mapproxy.config_template
        template_dir = os.path.join(
            os.path.dirname(mapproxy.config_template.__file__),
            'base_config')
        return template_dir

    def template_wsgi_app(self):
        app_filename = self.args[1]
        if '.' not in os.path.basename(app_filename):
            app_filename += '.py'
        mapproxy_conf = self.mapproxy_conf
        if os.path.exists(app_filename) and not self.options.force:
            self.log_error("%s already exists, use --force", app_filename)
            return 1

        print("writing MapProxy app to %s" % (app_filename, ))

        template_dir = self.template_dir()
        app_template = io.open(os.path.join(template_dir, 'config.wsgi'), encoding='utf-8').read()
        with io.open(app_filename, 'w', encoding='utf-8') as f:
            f.write(app_template % {'mapproxy_conf': mapproxy_conf,
                'here': os.path.dirname(mapproxy_conf)})

        return 0

    def template_base_config(self):
        outdir = self.args[1]
        if not os.path.exists(outdir):
            os.makedirs(outdir)

        template_dir = self.template_dir()

        for filename in ('mapproxy.yaml', 'seed.yaml',
            'full_example.yaml', 'full_seed_example.yaml'):
            to = os.path.join(outdir, filename)
            from_ = os.path.join(template_dir, filename)
            if os.path.exists(to) and not self.options.force:
                self.log_error("%s already exists, use --force", to)
                return 1
            print("writing %s" % (to, ))
            shutil.copy(from_, to)

        return 0

    def template_log_ini(self):
        log_filename = self.args[1]

        if os.path.exists(log_filename) and not self.options.force:
            self.log_error("%s already exists, use --force", log_filename)
            return 1

        template_dir = self.template_dir()
        log_template = io.open(os.path.join(template_dir, 'log.ini'), encoding='utf-8').read()
        with io.open(log_filename, 'w', encoding='utf-8') as f:
            f.write(log_template)

        return 0

commands = {
    'serve-develop': {
        'func': serve_develop_command,
        'help': 'Run MapProxy development server.'
    },
    'serve-multiapp-develop': {
        'func': serve_multiapp_develop_command,
        'help': 'Run MultiMapProxy development server.'
    },
    'create': {
        'func': create_command,
        'help': 'Create example configurations.'
    },
    'scales': {
        'func': scales_command,
        'help': 'Convert between scales and resolutions.'
    },
    'wms-capabilities': {
        'func': wms_capabilities_command,
        'help': 'Display WMS capabilites.',
    },
    'grids': {
        'func': grids_command,
        'help': 'Display detailed informations for configured grids.'
    },
    'export': {
        'func': export_command,
        'help': 'Export existing caches.'
    },
    'autoconfig': {
        'func': config_command,
        'help': 'Create config from WMS capabilities.'
    },
    'defrag-compact-cache': {
        'func': defrag_command,
        'help': 'De-fragmentate compact caches.'
    }
}


class NonStrictOptionParser(optparse.OptionParser):
    def _process_args(self, largs, rargs, values):
        while rargs:
            arg = rargs[0]
            # We handle bare "--" explicitly, and bare "-" is handled by the
            # standard arg handler since the short arg case ensures that the
            # len of the opt string is greater than 1.
            try:
                if arg == "--":
                    del rargs[0]
                    return
                elif arg[0:2] == "--":
                    # process a single long option (possibly with value(s))
                    self._process_long_opt(rargs, values)
                elif arg[:1] == "-" and len(arg) > 1:
                    # process a cluster of short options (possibly with
                    # value(s) for the last one only)
                    self._process_short_opts(rargs, values)
                elif self.allow_interspersed_args:
                    largs.append(arg)
                    del rargs[0]
                else:
                    return
            except optparse.BadOptionError:
                largs.append(arg)


def print_items(data, title='Commands'):
    name_len = max(len(name) for name in data)

    if title:
        print('%s:' % (title, ), file=sys.stdout)
    for name, item in iteritems(data):
        help = item.get('help', '')
        name = ('%%-%ds' % name_len) % name
        if help:
            help = '  ' + help
        print('  %s%s' % (name, help), file=sys.stdout)

def main():
    parser = NonStrictOptionParser("usage: %prog COMMAND [options]",
        add_help_option=False)
    options, args = parser.parse_args()

    if len(args) < 1 or args[0] in ('--help', '-h'):
        parser.print_help()
        print()
        print_items(commands)
        sys.exit(1)

    if len(args) == 1 and args[0] == '--version':
        print('MapProxy ' + version)
        sys.exit(1)

    command = args[0]
    if command not in commands:
        parser.print_help()
        print()
        print_items(commands)
        print('\nERROR: unknown command %s' % (command,), file=sys.stdout)
        sys.exit(1)

    args = sys.argv[0:1] + sys.argv[2:]
    commands[command]['func'](args)

if __name__ == '__main__':
    main()
