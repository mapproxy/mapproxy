import os
import cherrypy
import mapproxy.wsgiapp

if __name__ == '__main__':
    os.chdir('C:\Users\Striar.Yunis\Documents\mymapproxy')
    cherrypy.log.access_log.propagate = False
    config = {'global': {'request.show_tracebacks': False, 'log.screen': False, 'request.show_mismatched_params': False,
                         'server.ssl_module': 'builtin', 'log.access_file': '', 'server.max_request_body_size': 0,
                         'engine.SIGTERM': None, 'checker.on': False, 'engine.autoreload.on': False,
                         'server.socket_timeout': 60, 'server.ssl_enabled': False, 'server.socket_port': 8080,
                         'engine.SIGHUP': None, 'environment': 'embedded', 'tools.log_headers.on': False,
                         'log.error_file': ''}}
    cherrypy.config.update(config)
    mapproxy_app = mapproxy.wsgiapp.make_wsgi_app(services_conf='mapproxy2.yaml', debug=True,
                                                  ignore_config_warnings=True, reloader=False)
    cherrypy.tree.graft(mapproxy_app, '/mapproxy')
    cherrypy.config.update({'server.socket_host': '0.0.0.0'})
    cherrypy.engine.start()
    cherrypy.engine.block()
