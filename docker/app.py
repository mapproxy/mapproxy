# WSGI module for use with Apache mod_wsgi or gunicorn

from logging.config import fileConfig
import os.path
from mapproxy.wsgiapp import make_wsgi_app

log_config = r'/mapproxy/config/logging.ini'
if os.path.isfile(log_config):
    fileConfig(log_config, {'here': os.path.dirname(__file__)})

application = make_wsgi_app(r'/mapproxy/config/mapproxy.yaml', reloader=True)
