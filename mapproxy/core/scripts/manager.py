#!/usr/bin/env python
from __future__ import with_statement
import sys
from werkzeug import script

import pkg_resources

import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.INFO)
logging.getLogger('mapproxy.core.client').setLevel(logging.DEBUG)
# logging.getLogger('mapproxy.core.cache_sql').setLevel(logging.DEBUG)

def load_config(conf_file=None):
    if conf_file is not None:
        from mapproxy.core.config import load_base_config
        load_base_config(conf_file)

def make_app(conf_file=None):
    from mapproxy.core.app import make_wsgi_app
    load_config(conf_file)
    return make_wsgi_app()

include_modules = ['osc']
def module_filter(_call_stack, module_name, _class_name, _func_name, _full_name):
    return any([module in module_name for module in include_modules])


def make_runserver(app_factory, host='localhost', port=5000,
                   use_reloader=False, use_debugger=False, use_evalex=True,
                   threaded=False, processes=1, **kw):
    """Returns an action callback that spawns a new wsgiref server."""
    def action(hostname=('h', host), port=('p', port),
               callgraph=False, dot_filename=('f', 'callgraph.dot'),
               reloader=use_reloader, debugger=use_debugger,
               evalex=use_evalex, threaded=threaded, processes=processes):
        """Start a new development server."""
        app = app_factory()
        from werkzeug.serving import run_simple
        try:
            import pycallgraph
            pycallgraph.start_trace(filter_func=module_filter)
            run_simple(hostname, port, app, reloader, debugger, evalex,
                       reloader_interval=1, threaded=threaded, processes=processes, **kw)
        except:
            with open(dot_filename, 'w') as f:
                f.write(pycallgraph.get_dot(stop=True))
    return action

def make_fcgi(app_factory):
    def action_fcgi(mode=('m', 'fork')):
        """
        Start fcgi service. Supports fork and threaded mode.
        """
        if mode == 'threaded':
            from flup.server.fcgi import WSGIServer
            WSGIServer(app_factory(), bindAddress=('127.0.0.1', 5050)).run()
        else:
            if mode != 'fork':
                print >>sys.stderr, "unknown fcgi mode '%s'," % mode,
                print >>sys.stderr, 'using fork mode (avail. fork or threaded)'
            from flup.server.fcgi_fork import WSGIServer
            WSGIServer(app_factory()).run()
    return action_fcgi

def make_profile_app():
    from repoze.profile.profiler import AccumulatingProfileMiddleware
    return AccumulatingProfileMiddleware(
                    make_app(),
                    log_filename='/tmp/proxy.log',
                    discard_first_request=True,
                    flush_at_shutdown=True,
                    path='/__profile__'
                   )

include_modules = ['osc']
def wrap_callgraph(func, dot_filename):
    def module_filter(_call_stack, module_name, _class_name, _func_name, _full_name):
        return any([module in module_name for module in include_modules])
    def _callgraph(*args, **kw):
        import pycallgraph
        pycallgraph.start_trace(filter_func=module_filter)
        for _ in range(10):
            result = func(*args, **kw)
        with open(dot_filename, 'w') as f:
            f.write(pycallgraph.get_dot(stop=True))
        return result
    return _callgraph

def make_server(app_factory):
    def action_server():
        from mapproxy.core.httpserver import CherryPyWSGIServer
        server = CherryPyWSGIServer(('0.0.0.0', 8080), app_factory())
        server.start()
    return action_server

def main():
    if len(sys.argv) >= 2 and sys.argv[1] == '-f':
        filename = sys.argv[2]
        import functools
        global make_app
        make_app = functools.partial(make_app, filename)
        args = sys.argv[3:]
    else:
        import os
        filename = os.environ.get('PROXY_CONF', None)
        args = sys.argv[1:]
    
    load_config(filename)
    
    from mapproxy.core.config import Options
    defaults = Options(host='0.0.0.0', port = 5050)
    
    action_run = make_runserver(make_app, host=defaults.host, port=defaults.port,
                                use_reloader=False, use_debugger=True,
                                extra_files=['services.yaml',
                                             'osc/proxy/core/defaults.yaml'])
    action_profile = make_runserver(make_profile_app, host=defaults.host,
                                    port=defaults.port, use_reloader=True)

    action_server = make_server(make_app)
    
    action_fcgi = make_fcgi(make_app)
    
    script.run(args=args)

if __name__ == '__main__':
    main()