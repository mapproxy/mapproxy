Deployment
==========

MapProxy implements the Web Server Gateway Interface (WSGI) which is for Python what the Servlet API is for Java. There are different ways to deploy WSGI web applications.

MapProxy comes with a simple HTTP server that is easy to start and sufficient for local testing, see :ref:`deployment_testing`. For production and load testing it is recommended to choose one of the :ref:`production setups <deployment_production>`.


.. _deployment_testing:

Testing
-------

.. program:: mapproxy-util serve-develop

The ``serve-develop`` subcommand of ``mapproxy-util`` starts an HTTP server for local testing. It takes an existing MapProxy configuration file as an argument::


  mapproxy-util serve-develop mapproxy.yaml

The server automatically reloads if the configuration or any code of MapProxy changes.

.. cmdoption:: --bind, -b

  Set the socket MapProxy should listen. Defaults to ``localhost:8080``.
  Accepts either a port number or ``hostname:portnumber``.

.. cmdoption:: --debug

  Start MapProxy in debug mode. If you have installed Werkzeug_ (recommended) or Paste_, you will get an interactive traceback in the web browser on any unhandled exception (internal error).

.. note:: This server is sufficient for local testing of the configuration, but it is `not` stable for production or load testing.


The ``serve-multiapp-develop`` subcommand of ``mapproxy-util`` works similar to ``serve-develop`` but takes a directory of MapProxy configurations. See :ref:`multimapproxy`.

.. _deployment_production:

Production
----------

There are two common ways to deploy MapProxy in production.

Embedded in HTTP server
  You can directly integrate MapProxy into your web server. Apache can integrate Python web services with the ``mod_wsgi`` extension for example.

Behind an HTTP server or proxy
  You can run MapProxy as a separate local HTTP server behind an existing web server (nginx_, Apache, etc.) or an HTTP proxy (Varnish_, squid, etc).

Both approaches require a configuration that maps your MapProxy configuration with the MapProxy application. You can write a small script file for that.

Running MapProxy as a FastCGI server behind HTTP server, a third option, is no longer advised for new setups since the FastCGI package (flup) is no longer maintained and the Python HTTP server improved significantly.

.. _server_script:

Server script
~~~~~~~~~~~~~

You need a script that makes the configured MapProxy available for the Python WSGI servers.

You can create a basic script with ``mapproxy-util``::

  mapproxy-util create -t wsgi-app -f mapproxy.yaml config.py

The script contains the following lines and makes the configured MapProxy available as ``application``::

  from mapproxy.wsgiapp import make_wsgi_app
  application = make_wsgi_app('examples/minimal/etc/mapproxy.yaml')

This is sufficient for embedding MapProxy with ``mod_wsgi`` or for starting it with Python HTTP servers like ``gunicorn`` (see further below). You can extend this script to setup logging or to set environment variables.

You can enable MapProxy to automatically reload the configuration if it changes::

  from mapproxy.wsgiapp import make_wsgi_app
  application = make_wsgi_app('examples/minimal/etc/mapproxy.yaml', reloader=True)


.. index:: mod_wsgi, Apache

Apache mod_wsgi
---------------

The Apache HTTP server can directly integrate Python application with the `mod_wsgi`_ extension. The benefit is that you don't have to start another server. Read `mod_wsgi installation`_ for detailed instructions.

``mod_wsgi`` requires a server script that defines the configured WSGI function as ``application``. See :ref:`above <server_script>`.

You need to modify your Apache ``httpd.conf`` as follows::

  # if not loaded elsewhere
  LoadModule wsgi_module modules/mod_wsgi.so

  WSGIScriptAlias /mapproxy /path/to/mapproxy/config.py

  <Directory /path/to/mapproxy/>
    Order deny,allow
    Allow from all
  </Directory>


``mod_wsgi`` has a lot of options for more fine tuning. ``WSGIPythonHome`` or ``WSGIPythonPath`` lets you configure your ``virtualenv`` and  ``WSGIDaemonProcess``/``WSGIProcessGroup`` allows you to start multiple processes. See the `mod_wsgi configuration directives documentation <http://code.google.com/p/modwsgi/wiki/ConfigurationDirectives>`_. Using Mapnik also requires the ``WSGIApplicationGroup`` option.

.. note:: On Windows only the ``WSGIPythonPath`` option is supported. Linux/Unix supports ``WSGIPythonPath`` and ``WSGIPythonHome``. See also the `mod_wsgi documentation for virtualenv <mod_wsgi venv>`_ for detailed information when using multiple virtualenvs.

A more complete configuration might look like::

  # if not loaded elsewhere
  LoadModule wsgi_module modules/mod_wsgi.so

  WSGIScriptAlias /mapproxy /path/to/mapproxy/config.py
  WSGIDaemonProcess mapproxy user=mapproxy group=mapproxy processes=8 threads=25
  WSGIProcessGroup mapproxy
  # WSGIPythonHome should contain the bin and lib dir of your virtualenv
  WSGIPythonHome /path/to/mapproxy/venv
  WSGIApplicationGroup %{GLOBAL}

  <Directory /path/to/mapproxy/>
    Order deny,allow
    Allow from all
  </Directory>


.. _`mod_wsgi`: http://code.google.com/p/modwsgi/
.. _`mod_wsgi installation`: http://code.google.com/p/modwsgi/wiki/InstallationInstructions
.. _`mod_wsgi venv`: https://code.google.com/p/modwsgi/wiki/VirtualEnvironments

Behind HTTP server or proxy
---------------------------

There are Python HTTP servers available that can directly run MapProxy. Most of them are robust and efficient, but there are some odd HTTP clients out there that (mis)interpret the HTTP standard in various ways. It is therefor recommended to put a HTTP server or proxy in front that is mature and widely deployed (like Apache_, Nginx_, etc.).

Python HTTP Server
~~~~~~~~~~~~~~~~~~

You need start these servers in the background on start up. It is recommended to create an init script for that or to use tools like upstart_ or supervisord_.

Gunicorn
""""""""

Gunicorn_ is a Python WSGI HTTP server for UNIX. Gunicorn use multiple processes but the process number is fixed. The default worker is synchronous, meaning that a process is blocked while it requests data from another server for example. You need to choose an asynchronous worker like eventlet_.

You need a server script that creates the MapProxy application (see :ref:`above <server_script>`). The script needs to be in the directory from where you start ``gunicorn`` and it needs to end with ``.py``.

To start MapProxy with the Gunicorn web server with four processes, the eventlet worker and our server script (without ``.py``)::

  cd /path/of/config.py/
  gunicorn -k eventlet -w 4 -b :8080 config:application


An example upstart script (``/etc/init/mapproxy.conf``) might look like::

    start on runlevel [2345]
    stop on runlevel [!2345]

    respawn

    setuid mapproxy
    setgid mapproxy

    chdir /etc/opt/mapproxy

    exec /opt/mapproxy/bin/gunicorn -k eventlet -w 8 -b :8080 application \
        >>/var/log/mapproxy/gunicorn.log 2>&1


Spawning
""""""""

Spawning_ is another Python WSGI HTTP server for UNIX that supports multiple processes and multiple threads.

::

  cd /path/of/config.py/
  spawning config.application --threads=8 --processes=4 \
    --port=8080


HTTP Proxy
~~~~~~~~~~

You can either use a dedicated HTTP proxy like Varnish_ or a general HTTP web server with proxy capabilities like Apache with mod_proxy_ in front of MapProxy.

You need to set some HTTP headers so that MapProxy can generate capability documents with the URL of the proxy, instead of the local URL of the MapProxy application.

* ``Host`` – is the hostname that clients use to acces MapProxy (i.e. the proxy)
* ``X-Script-Name`` – path of MapProxy when the URL is not ``/`` (e.g. ``/mapproxy``)
* ``X-Forwarded-Host`` – alternative to ``HOST``
* ``X-Forwarded-Proto`` – should be ``https`` when the client connects with HTTPS

Nginx
"""""

Here is an example for the Nginx_ webserver with the included proxy module. It forwards all requests to ``example.org/mapproxy`` to ``localhost:8181/``::

  server {
    server_name example.org;
    location /mapproxy {
      proxy_pass http://localhost:8181;
      proxy_set_header Host $http_host;
      proxy_set_header X-Script-Name /mapproxy;
    }
  }

Apache
""""""

Here is an example for the Apache_ webserver with the included ``mod_proxy`` and ``mod_headers`` modules. It forwards all requests to ``example.org/mapproxy`` to ``localhost:8181/``

::

  <IfModule mod_proxy.c>
    <IfModule mod_headers.c>
          <Location /mapproxy>
                  ProxyPass http://localhost:8181
                  ProxyPassReverse  http://localhost:8181
                  RequestHeader add X-Script-Name "/mapproxy"
          </Location>
    </IfModule>
  </IfModule>

You need to make sure that both modules are loaded. The ``Host`` is already set to the right value by default.


Other deployment options
------------------------

Refer to http://wsgi.readthedocs.org/en/latest/servers.html for a list of some available WSGI servers.

FastCGI
~~~~~~~

.. note:: Running MapProxy as a FastCGI server behind HTTP server is no longer advised for new setups since the used Python package (flup) is no longer maintained. Please refer to the `MapProxy 1.5.0 deployment documentation for more information on FastCGI <http://mapproxy.org/docs/1.5.0/deployment.html>`_.


Performance
-----------

Because of the way Python handles threads in computing heavy applications (like MapProxy WMS is), you should choose a server that uses multiple processes (pre-forking based) for best performance.

The examples above are all minimal and you should read the documentation of your components to get the best performance with your setup.


Load Balancing and High Availablity
-----------------------------------

You can easily run multiple MapProxy instances in parallel and use a load balancer to distribute requests across all instances, but there are a few things to consider when the instances share the same tile cache with NFS or other network filesystems.

MapProxy uses file locks to prevent that multiple processes will request the same image twice from a source. This would typically happen when two or more requests for missing tiles are processed in parallel by MapProxy and these tiles belong to the same meta tile. Without locking MapProxy would request the meta tile for each request. With locking, only the first process will get the lock and request the meta tile. The other processes will wait till the the first process releases the lock and will then use the new created tile.

Since file locking doesn't work well on most network filesystems you are likely to get errors when MapProxy writes these files on network filesystems. You should configure MapProxy to write all lock files on a local filesystem to prevent this. See :ref:`globals.cache.lock_dir<lock_dir>` and :ref:`globals.cache.tile_lock_dir<tile_lock_dir>`.

With this setup the locking will only be effective when parallel requests for tiles of the same meta tile go to the same MapProxy instance. Since these requests are typically made from the same client you should enable *sticky sessions* in you load balancer when you offer tiled services (WMTS/TMS/KML).


.. _nginx: http://nginx.org
.. _mod_proxy: http://httpd.apache.org/docs/current/mod/mod_proxy.html
.. _Varnish: http://www.varnish-cache.org/
.. _werkzeug: http://pypi.python.org/pypi/Werkzeug
.. _paste: http://pypi.python.org/pypi/Paste
.. _gunicorn: http://gunicorn.org/
.. _Spawning: http://pypi.python.org/pypi/Spawning
.. _FastCGI: http://www.fastcgi.com/
.. _flup: http://pypi.python.org/pypi/flup
.. _mod_fastcgi: http://www.fastcgi.com/mod_fastcgi/docs/mod_fastcgi.html
.. _mod_fcgid: http://httpd.apache.org/mod_fcgid/
.. _eventlet: http://pypi.python.org/pypi/eventlet
.. _Apache: http://httpd.apache.org/
.. _upstart: http://upstart.ubuntu.com/
.. _supervisord: http://supervisord.org/

Logging
-------

MapProxy uses the Python logging library for the reporting of runtime information, errors and warnings. You can configure the logging with Python code or with an ini-style configuration. Read the `logging documentation for more information <http://docs.python.org/howto/logging.html#configuring-logging>`_.


Loggers
~~~~~~~

MapProxy uses multiple loggers for different parts of the system. The loggers build a hierarchy and are named in dotted-notation. ``mapproxy`` is the logger for everything, ``mapproxy.source`` is the logger for all sources, ``mapproxy.source.wms`` is the logger for all WMS sources, etc. If you configure on logger (e.g. ``mapproxy``) then all sub-loggers will also use this configuration.

Here are the most important loggers:

``mapproxy.system``
  Logs information about the system and the installation (e.g. used projection library).

``mapproxy.config``
  Logs information about the configuration.

``mapproxy.source.XXX``
  Logs errors and warnings for service ``XXX``.

``mapproxy.source.request``
  Logs all requests to sources with URL, size in kB and duration in milliseconds.


Enabling logging
~~~~~~~~~~~~~~~~

The :ref:`test server <deployment_testing>` is already configured to log all messages to the console (``stdout``). The other deployment options require a logging configuration.

Server Script
"""""""""""""

You can use the Python logging API or load an ``.ini`` configuration if you have a :ref:`server script <server_script>` for deployment.

The example script created with ``mapproxy-util create -t wsgi-app`` already contains code to load an ``.ini`` file. You just need to uncomment these lines and create a ``log.ini`` file. You can create an example ``log.ini`` with::

  mapproxy-util create -t log-ini log.ini


.. index:: MultiMapProxy
.. _multimapproxy:

MultiMapProxy
-------------

.. versionadded:: 1.2.0

You can run multiple MapProxy instances (configurations) within one process with the MultiMapProxy application.

MultiMapProxy can dynamically load configurations. You can put all configurations into one directory and MapProxy maps each file to a URL: ``conf/proj1.yaml`` is available at ``http://hostname/proj1/``.

Each configuration will be loaded on demand and MapProxy caches each loaded instance. The configuration will be reloaded if the file changes.

MultiMapProxy as the following options:

``config_dir``
  The directory where MapProxy should look for configurations.

``allow_listing``
  If set to ``true``, MapProxy will list all available configurations at the root URL of your MapProxy. Defaults to ``false``.


Server Script
~~~~~~~~~~~~~

There is a ``make_wsgi_app`` function in the ``mapproxy.multiapp`` package that creates configured MultiMapProxy WSGI application. Replace the ``application`` definition in your script as follows::

  from mapproxy.multiapp import make_wsgi_app
  application = make_wsgi_app('/path/to.projects', allow_listing=True)

