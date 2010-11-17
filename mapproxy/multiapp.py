from __future__ import with_statement
import os

from mapproxy.request import Request
from mapproxy.response import Response
from mapproxy.util.collections import LRU
from mapproxy.wsgiapp import make_wsgi_app
from threading import Lock

import logging
log = logging.getLogger(__name__)

def app_factory(global_options, base_dir, **local_options):
    loader = DirectoryConfLoader(base_dir)
    list_apps = local_options.get('list_apps', False)
    return MultiMapProxy(loader, None, list_apps=list_apps)

class MultiMapProxy(object):
    def __init__(self, loader, conf, list_apps=False, app_cache_size=100):
        self.loader = loader
        self.conf = conf
        self.list_apps = list_apps
        self._app_init_lock = Lock()
        self.apps = LRU(app_cache_size)
    def __call__(self, environ, start_response):
        req = Request(environ)
        return self.handle(req)(environ, start_response)
    
    def handle(self, req):
        app_name = req.pop_path()
        if not app_name:
            return self.index_list()
        
        if not app_name or (
                app_name not in self.apps and not self.loader.app_available(app_name)
            ):
            return Response('not found', status=404)
        
        return self.proj_app(app_name)
    
    def index_list(self):
        import mapproxy.version
        html = "<html><body><h1>Welcome to MapProxy %s</h1>" % mapproxy.version.version
        
        if self.list_apps:
            html += "<h2>available apps:</h2><ul>"
            html += '\n'.join('<li><a href="%(name)s/">%(name)s</a></li>' % {'name': app}
                              for app in self.loader.available_apps())
            html += '</ul>'
        html += '</body></html>'
        return Response(html, content_type='text/html')

    def proj_app(self, proj_name):
        """
        Return the (cached) project app.
        """
        proj_app, timestamp = self.apps.get(proj_name, (None, None))
        
        if proj_app:
            if self.loader.needs_reload(proj_name, timestamp):
                # discard cached app
                proj_app = None
                del self.apps[proj_name]
        
        if not proj_app:
            with self._app_init_lock:
                if proj_name not in self.apps:
                    proj_app, m_time = self.create_app(proj_name)
                    self.apps[proj_name] = proj_app, m_time
        
        return proj_app
    
    def create_app(self, proj_name):
        """
        Returns a new configured MapProxy app and the timestamp of the configuration.
        """
        mapproxy_conf = self.loader.app_conf(proj_name)['mapproxy_conf']
        m_time = os.path.getmtime(mapproxy_conf)
        log.info('initializing project app %s with %s', proj_name, mapproxy_conf)
        app = make_wsgi_app(mapproxy_conf)
        return app, m_time


class ConfLoader(object):
    def needs_reload(self, app_name, timestamp):
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
    def __init__(self, base_dir, prefix='.yaml'):
        self.base_dir = base_dir
        self.prefix = prefix
    
    def needs_reload(self, app_name, timestamp):
        conf_file = self.filename_from_app_name(app_name)
        m_time = os.path.getmtime(conf_file)
        if m_time > timestamp:
            return True
        return False
    
    def _is_conf_file(self, fname):
        if not os.path.isfile(os.path.join(self.base_dir, fname)):
            return False
        if self.prefix:
            return fname.lower().endswith(self.prefix)
        else:
            return True
    
    def app_name_from_filename(self, fname):
        _path, fname = os.path.split(fname)
        app_name, _ext = os.path.splitext(fname)
        return app_name
    
    def filename_from_app_name(self, app_name):
        return os.path.join(self.base_dir, app_name + self.prefix or '')
        
    def available_apps(self):
        """
        List all available app names.
        """
        apps = []
        for f in os.listdir(self.base_dir):
            if self._is_conf_file(f):
                app_name = self.app_name_from_filename(f)
                apps.append(app_name)
        return apps
    
    def app_available(self, app_name):
        """
        Return if application is available.
        """
        conf_file = self.filename_from_app_name(app_name)
        return self._is_conf_file(conf_file)
    
    def app_conf(self, app_name):
        conf_file = self.filename_from_app_name(app_name)
        if not self._is_conf_file(conf_file):
            return None
        return {'mapproxy_conf': conf_file}