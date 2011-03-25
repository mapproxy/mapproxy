import os
import re
import optparse
import sys

def serve_develop_command(args):
    parser = optparse.OptionParser("usage: %prog serve-develop [options] mapproxy.yaml",
        add_help_option=False)
    parser.add_option('--help', dest='help', action='store_true',
        default=False, help='show this help message and exit')
    
    parser.add_option("-b", "--bind",
                      dest="address", default='127.0.0.1:8080',
                      help="Server socket [127.0.0.1:8080]")
    parser.add_option("--debug", default=False, action='store_true',
                      dest="debug",
                      help="Enable debug mode")
    options, args = parser.parse_args(args)
    
    if options.help:
        parser.print_help()
        sys.exit(1)
        
    if len(args) != 2:
        parser.print_help()
        print "\nERROR: MapProxy configuration required."
        sys.exit(1)
        
    mapproxy_conf = args[1]
    
    host, port = parse_bind_address(options.address)
    
    if options.debug and host != 'localhost':
        import textwrap
        print textwrap.dedent("""\
        ################# WARNING! ##################
        Running debug mode with non-localhost address
        is a serious security vulnerability.
        #############################################\
        """)
    
    from mapproxy.wsgiapp import make_wsgi_app
    from mapproxy.util.ext.serving import run_simple
    app = make_wsgi_app(mapproxy_conf, debug=options.debug)
    
    if options.debug:
        processes = 1
        threaded = False
    else:
        processes = 4
        threaded = False
    run_simple(host, port, app, use_reloader=True, processes=processes,
        threaded=threaded, passthrough_errors=True)


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
    elif re.match('^\d+$', address):
        host = default[0]
        port = int(address)
    else:
        host = address
        port = default[1]
    return host, port


commands = {
    'serve-develop': {
        'func': serve_develop_command,
        'help': 'run MapProxy development server'
    },
}
def print_help():
    prog = os.path.basename(sys.argv[0])
    print >>sys.stdout, 'Usage: %s COMMAND\n' % (prog, )
    print >>sys.stdout, 'Commands:'
    for cmd, cmd_dict in commands.iteritems():
        help = cmd_dict.get('help', '')
        if help:
            help = ': ' + help
        print >>sys.stdout, '  %s%s' % (cmd, help)

def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)
        
    command = sys.argv[1]
    if command not in commands:
        print_help()
        print >>sys.stdout, '\nERROR: unknown command %s' % (command,)
        sys.exit(1)
    
    args = sys.argv[0:1] + sys.argv[2:]
    commands[command]['func'](args)
    
if __name__ == '__main__':
    main()