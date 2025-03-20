# WSGI module for use with Apache mod_wsgi or gunicorn

from logging.config import fileConfig
import os


log_config = r'/mapproxy/config/logging.ini'

if os.path.isfile(log_config):
    print('Loading log config')
    fileConfig(log_config, {'here': os.path.dirname(__file__)})

multiapp_mapproxy = os.environ.get('MULTIAPP_MAPPROXY', False)

if multiapp_mapproxy:
    from mapproxy.multiapp import make_wsgi_app

    multiapp_allow_listings = os.environ.get('MULTIAPP_ALLOW_LISTINGS', False)

    print('Starting MapProxy in multi app mode')
    application = make_wsgi_app(r'/mapproxy/config/apps/', allow_listing=multiapp_allow_listings)
else:
    from mapproxy.wsgiapp import make_wsgi_app

    print('Starting MapProxy in single app mode')
    application = make_wsgi_app(r'/mapproxy/config/mapproxy.yaml', reloader=True)
