# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
