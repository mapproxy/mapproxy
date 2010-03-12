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

"""
The WSGI application.
"""
from __future__ import with_statement
import re
import os
import sys
import threading
from cStringIO import StringIO
from mapproxy.core.config import base_config, load_base_config, abspath
from mapproxy.core.version import version_string
version = version_string()
# NOTE: do not import anything from mapproxy before init_logging is called
#       otherwise the logging will not be configured properly


ctx = threading.local()

def app_factory(global_options, **local_options):
    """
    Paster app_factory.
    """
    services_conf = local_options.get('services_conf', None)
    proxy_conf = local_options.get('proxy_conf', None)
    reload_files = local_options.get('reload_files', None)
    if reload_files is not None:
        init_paster_reload_files(reload_files)
    if proxy_conf is not None:
        load_base_config(proxy_conf)
    return make_wsgi_app(services_conf)

def init_paster_reload_files(reload_files):
    file_patterns = reload_files.split('\n')
    file_patterns.append(os.path.join(os.path.dirname(__file__), 'defaults.yaml'))
    init_paster_file_watcher(file_patterns)

def init_paster_file_watcher(file_patterns):
    from glob import glob
    for pattern in file_patterns:
        files = glob(pattern)
        _add_files_to_paster_file_watcher(files)
    
def _add_files_to_paster_file_watcher(files):
    import paste.reloader
    for file in files:
        paste.reloader.watch_file(file)
    
def init_logging_system():
    import logging.config
    try:
        import cloghandler
        cloghandler.ConcurrentRotatingFileHandler #disable pyflakes warning
    except ImportError:
        pass
    log_conf = base_config().log_conf
    if log_conf:
        log_conf = abspath(log_conf)
        if not os.path.exists(log_conf):
            print >>sys.stderr, 'ERROR: log configuration %s not found.' % log_conf
            return
        conf = open(log_conf).read()
        conf = conf.replace("{{conf_base_dir}}", base_config().conf_base_dir)
        logging.config.fileConfig(StringIO(conf))

def init_null_logging():
    import logging
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
    logging.getLogger().addHandler(NullHandler())

def make_wsgi_app(services_conf=None, init_logging=True):
    """
    Create a ProxyApp with the given services conf. Also initializes logging.
    
    :param services_conf: the file name of the services.yaml configuration,
                          if ``None`` the default is loaded.
    """
    if init_logging:
        init_logging_system()
    else:
        init_null_logging()
    
    from mapproxy.core.request import Request
    from mapproxy.core.response import Response
    from mapproxy.core.conf_loader import load_services
    
    services = load_services(services_conf)
    class ProxyApp(object):
        """
        The proxy WSGI application.
        """
        handler_path_re = re.compile('^/(\w+)')
        def __init__(self, services):
            self.handlers = {}
            for service in services.itervalues():
                for name in service.names:
                    self.handlers[name] = service
        
        def _set_ctx(self, environ):
            ctx.__dict__.clear()
            ctx.env = environ
        
        def __call__(self, environ, start_response):
            resp = None
            req = Request(environ)
            
            self._set_ctx(environ)
            
            match = self.handler_path_re.match(req.path)
            if match:
                handler_name = match.group(1)
                if handler_name in self.handlers:
                    try:
                        resp = self.handlers[handler_name].handle(req)
                    except Exception:
                        if base_config().debug_mode:
                            raise
                        else:
                            import traceback
                            traceback.print_exc(file=environ['wsgi.errors'])
                            resp = Response('internal error', status=500)
            if resp is None:
                resp = Response('not found', mimetype='text/plain', status=404)
            return resp(environ, start_response)
    
    app = ProxyApp(services)
    if os.environ.get('PROXY_LIGHTTPD_ROOTFIX', False):
        app = LighttpdCGIRootFix(app)
    return app

class LighttpdCGIRootFix(object):
    """Wrap the application in this middleware if you are using lighttpd
    with FastCGI or CGI and the application is mounted on the URL root.

    :param app: the WSGI application
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('SCRIPT_NAME', '')
        path_info = environ.get('PATH_INFO', '')
        if path_info == script_name:
            environ['PATH_INFO'] = path_info
        else:
            environ['PATH_INFO'] = script_name + path_info
        environ['SCRIPT_NAME'] = ''
        return self.app(environ, start_response)
