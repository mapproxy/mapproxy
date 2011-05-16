# WSGI module for use with Apache mod_wsgi or gunicorn

# from logging.config import fileConfig
# import os.path
# fileConfig('./log.ini', {'here': os.path.dirname(__file__)})

from mapproxy.wsgiapp import make_wsgi_app
application = make_wsgi_app('%s')
