#!/usr/bin/env python
from __future__ import with_statement
import os
from mapproxy.core.config import base_config, abspath
from mapproxy.core.app import LighttpdCGIRootFix

def load_config(conf_file=None):
    if conf_file is not None:
        from mapproxy.core.config import load_base_config
        load_base_config(conf_file)

def make_app(conf_file=None):
    from mapproxy.core.app import make_wsgi_app
    load_config(conf_file)
    return make_wsgi_app()

def main():
    from optparse import OptionParser
    
    parser = OptionParser()
    parser.add_option("-f", "--proxy-conf",
                      dest="conf_file", default=None,
                      help="proxy configuration")
    
    (options, args) = parser.parse_args()
    
    if options.conf_file:
        filename = options.conf_file
    else:
        filename = os.environ.get('PROXY_CONF', None)
    
    load_config(filename)
    
    def app_factory():
        return make_app(conf_file=filename)
    
    from flup.server.fcgi_fork import WSGIServer
    
    WSGIServer(app_factory()).run()
