# -:- encoding: utf-8 -:-
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

import os

from mapproxy.request import Request
from mapproxy.response import Response
from mapproxy.util.collections import LRU
from mapproxy.wsgiapp import make_wsgi_app as make_mapproxy_wsgi_app
from mapproxy.compat import iteritems

from threading import Lock

import logging
log = logging.getLogger(__name__)

def asbool(value):
    """
    >>> all([asbool(True), asbool('trUE'), asbool('ON'), asbool(1)])
    True
    >>> any([asbool(False), asbool('false'), asbool('foo'), asbool(None)])
    False
    """
    value = str(value).lower()
    return value in ('1', 'true', 'yes', 'on')

def app_factory(global_options, config_dir, allow_listing=False, **local_options):
    """
    Create a new MultiMapProxy app.

    :param config_dir: directory with all mapproxy configurations
    :param allow_listing: allow to list all available apps
    """
    return make_wsgi_app(config_dir, asbool(allow_listing))

def make_wsgi_app(config_dir, allow_listing=True, debug=False):
    """
    Create a MultiMapProxy with the given config directory.

    :param config_dir: the directory with all project configurations.
    :param allow_listing: True if MapProxy should list all instances
        at the root URL
    """
    config_dir = os.path.abspath(config_dir)
    loader = DirectoryConfLoader(config_dir)
    return MultiMapProxy(loader, list_apps=allow_listing, debug=debug)


class MultiMapProxy(object):

    def __init__(self, loader, list_apps=False, app_cache_size=100, debug=False):
        self.loader = loader
        self.list_apps = list_apps
        self._app_init_lock = Lock()
        self.apps = LRU(app_cache_size)
        self.debug = debug

    def __call__(self, environ, start_response):
        req = Request(environ)
        return self.handle(req)(environ, start_response)

    def handle(self, req):
        app_name = req.pop_path()
        if not app_name:
            return self.index_list(req)

        if not app_name or (
                app_name not in self.apps and not self.loader.app_available(app_name)
            ):
            return Response('not found', status=404)

        # safe instance/app name for authorization
        req.environ['mapproxy.instance_name'] = app_name
        return self.proj_app(app_name)

    def index_list(self, req):
        """
        Return greeting response with a list of available apps (if enabled with list_apps).
        """
        import mapproxy.version
        html = "<html><body><h1>Welcome to MapProxy %s</h1>" % mapproxy.version.version

        url = req.script_url
        if self.list_apps:
            html += "<h2>available instances:</h2><ul>"
            html += '\n'.join('<li><a href="%(url)s/%(name)s/">%(name)s</a></li>' % {'url': url, 'name': app}
                              for app in self.loader.available_apps())
            html += '</ul>'
        html += '</body></html>'
        return Response(html, content_type='text/html')

    def proj_app(self, proj_name):
        """
        Return the (cached) project app.
        """
        proj_app, timestamps = self.apps.get(proj_name, (None, None))

        if proj_app:
            if self.loader.needs_reload(proj_name, timestamps):
                # discard cached app
                proj_app = None

        if not proj_app:
            with self._app_init_lock:
                proj_app, timestamps = self.apps.get(proj_name, (None, None))
                if self.loader.needs_reload(proj_name, timestamps):
                    proj_app, timestamps = self.create_app(proj_name)
                    self.apps[proj_name] = proj_app, timestamps
                else:
                    proj_app, timestamps = self.apps[proj_name]

        return proj_app

    def create_app(self, proj_name):
        """
        Returns a new configured MapProxy app and a dict with the
        timestamps of all configuration files.
        """
        mapproxy_conf = self.loader.app_conf(proj_name)['mapproxy_conf']
        log.info('initializing project app %s with %s', proj_name, mapproxy_conf)
        app = make_mapproxy_wsgi_app(mapproxy_conf, debug=self.debug)
        return app, app.config_files


class ConfLoader(object):
    def needs_reload(self, app_name, timestamps):
        """
        Returns ``True`` if the configuration of `app_name` changed
        since `timestamp`.
        """
        raise NotImplementedError()

    def app_available(self, app_name):
        """
        Returns ``True`` if `app_name` is available.
        """
        raise NotImplementedError()

    def available_apps(self):
        """
        Returns a list with all available lists.
        """
        raise NotImplementedError()

    def app_conf(self, app_name):
        """
        Returns a configuration dict for the given `app_name`,
        None if the app is not found.

        The configuration dict contains at least 'mapproxy_conf'
        with the filename of the configuration.
        """
        raise NotImplementedError()


class DirectoryConfLoader(ConfLoader):
    """
    Load application configurations from a directory.
    """
    def __init__(self, base_dir, suffix='.yaml'):
        self.base_dir = base_dir
        self.suffix = suffix

    def needs_reload(self, app_name, timestamps):
        if not timestamps:
            return True
        for conf_file, timestamp in iteritems(timestamps):
            m_time = os.path.getmtime(conf_file)
            if m_time > timestamp:
                return True
        return False

    def _is_conf_file(self, fname):
        if not os.path.isfile(fname):
            return False
        if self.suffix:
            return fname.lower().endswith(self.suffix)
        else:
            return True

    def app_name_from_filename(self, fname):
        """
        >>> DirectoryConfLoader('/tmp/').app_name_from_filename('/tmp/foobar.yaml')
        'foobar'
        """
        _path, fname = os.path.split(fname)
        app_name, _ext = os.path.splitext(fname)
        return app_name

    def filename_from_app_name(self, app_name):
        """
        >>> DirectoryConfLoader('/tmp/').filename_from_app_name('foobar')
        '/tmp/foobar.yaml'
        """
        return os.path.join(self.base_dir, app_name + self.suffix or '')

    def available_apps(self):
        apps = []
        for f in os.listdir(self.base_dir):
            if self._is_conf_file(os.path.join(self.base_dir, f)):
                app_name = self.app_name_from_filename(f)
                apps.append(app_name)
        apps.sort()
        return apps

    def app_available(self, app_name):
        conf_file = self.filename_from_app_name(app_name)
        return self._is_conf_file(conf_file)

    def app_conf(self, app_name):
        conf_file = self.filename_from_app_name(app_name)
        if not self._is_conf_file(conf_file):
            return None
        return {'mapproxy_conf': conf_file}
