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
WSGI utils
"""

def lighttpd_root_fix_filter_factory(global_conf):
    return LighttpdCGIRootFix

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
