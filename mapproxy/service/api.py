"""
API service handler
"""
import inspect
import json
import os
import re
import sys
import urllib

import yaml

from mapproxy.config.spec  import validate_mapproxy_conf
from mapproxy.response     import Response
from mapproxy.service.base import Server
from mapproxy.util.yaml    import load_yaml_file


class WebError(Exception):
    """
    Exception that represents an HTTP status code.
    """
    def __init__(self, msg, status_code):
       Exception.__init__(self, msg)
       self.msg = msg
       self.status_code = status_code


def get_handlers():
    """
    Return an iterator over all IHandler classes in this module that define
    a URL regex.
    """
    for name, obj in inspect.getmembers(sys.modules[__name__]):
        if (inspect.isclass(obj) and issubclass(obj, IHandler) and obj.sUrlRegEx is not None):
            yield obj


class ApiServer(Server):
    """
    Provides a REST API for MapProxy.

    @type config:    L{ProxyConfiguration}
    @ivar config:    Configuration for our app.
    @ivar _handlers: List of List of IHandler classes.
    """
    names = ('api',)

    def __init__(self, config = None):
        Server.__init__(self)

        self.config = config
        self._handlers = []

        # Build up a list of all IHandler classes in this module.
        for handler in get_handlers():
            re_str = handler.sUrlRegEx
            if not re_str.startswith("^"):
                re_str = "^" + re_str
            if not re_str.endswith("$"):
                re_str = re_str + "$"
            reg_ex = re.compile(re_str)

            self._handlers.append( (reg_ex, handler) )

    def handle(self, req):
        """
        Returns a response for the given HTTP request.
        """
        # Remove the top level '/api' from the path.
        req.pop_path()

        # Find the correct handler given the URL
        url_path = urllib.unquote_plus(req.path)
        groups  = ()
        handler = None
        for (reg_ex, handler_type) in self._handlers:
            match = reg_ex.match(url_path)
            if match is not None:
               handler = handler_type(self.config.abs_path)
               groups = match.groups()
               break

        # Return an error code if we can't find a request handler.
        if handler is None:
            return Response("Not found", status = 404)

        # Attempt to find request handler method for HTTP method.
        http_method = req.environ.get("REQUEST_METHOD", "GET")
        found_method = getattr(handler, http_method.lower(), None)
        if found_method is None:
            return Response("Not allowed", status = 405)

        # Get response from the request handler and handle any exceptions that
        # may be raised.
        try:
            return found_method(req, *groups)
        except WebError as er:
            return Response(er.message, status = er.status_code)


class IHandler(object):
    """
    Base request handler that contains common utility methods.

    @type sUrlRegEx: str
    @cvar sUrlRegEx: Regular expression used to match URLs that we should handle.
                     If set to None the handler is treated as an abstract base
                     class and not checked.
    """
    sUrlRegEx = None

    def __init__(self, config_path):
        self._config_path = config_path
        self._config_data = None

    #{ Configuration access
    def _get_config(self):
        """
        Lazily parse and return the entire configuration.
        """
        if self._config_data is None:
            conf_file = os.path.normpath(self._config_path)
            self._config_data = load_yaml_file(conf_file)
        return self._config_data
    _config = property(_get_config)

    def _write_config(self, new_config):
        """
        Write the given configuration to disk and update our cached version.
        """
        with open(self._config_path, "w") as conf_file:
           yaml.dump(new_config, conf_file)
        self._config_data = new_config
    #}

    #{ JSON helpers
    def _get_json_content(self, req):
        length = int(req.environ["CONTENT_LENGTH"])
        data   = req.environ["wsgi.input"].read(length)
        return yaml.safe_load(data)

    def _build_json_response(self, data):
        data = json.dumps(data)
        return Response(data, content_type = "application/json")
    #}

    def _validate_config(self, config):
        """
        Attempt to validate the given configuration. Raises an exception if the
        validation fails.
        """
        # Validate the new configuration.
        (errors, informal_only) = validate_mapproxy_conf(config)
        if not informal_only or len(errors) > 0:
            raise WebError("\n".join(errors), 400)

        # Verify that the new configuration could be loaded.
        from mapproxy.config.loader import ConfigurationError, ProxyConfiguration
        try:
            proxy = ProxyConfiguration(config)
            services = proxy.configured_services()
        except ConfigurationError as ex:
            msg = "Failed to update configuration:\n%s" % (ex.message)
            raise WebError(msg, 404)


class ConfigHandler(IHandler):
    """
    Request handler that allows the user to GET/PUT the entire configuration.
    """
    sUrlRegEx  = "/config"

    def get(self, req):
        """
        Return the current configuration as JSON.
        """
        return self._build_json_response(self._config)

    def put(self, req):
        """
        Attempt to set the configuration to the body of the request. The new
        configuration is only accepted after validating it.
        """
        new_config = self._get_json_content(req)

        # Validate the configuration with the new layer.
        self._validate_config(new_config)

        # Write the configuration to disk.
        self._write_config(new_config)
        return self._build_json_response(self._config)
