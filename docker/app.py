# WSGI module for use with Apache mod_wsgi or gunicorn

from logging.config import fileConfig
import os.path
from mapproxy.wsgiapp import make_wsgi_app

fileConfig(r'/mapproxy/config/logging.ini', {'here': os.path.dirname(__file__)})

application = make_wsgi_app(r'/mapproxy/config/mapproxy.yaml', reloader=True)
