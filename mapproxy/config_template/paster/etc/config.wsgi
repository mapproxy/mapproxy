# WSGI module for use with Apache mod_wsgi

import os
from paste.deploy import loadapp

application = loadapp('config:config.ini', relative_to=os.path.dirname(__file__))