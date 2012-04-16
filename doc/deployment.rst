Deployment
==========

MapProxy implements the Web Server Gateway Interface (WSGI) which is for Python what the Servlet API is for Java. There are different ways to deploy WSGI web applications.

MapProxy comes with a simple HTTP server that is easy to start and sufficient for local testing, see :ref:`deployment_testing`. For production and load testing it is recommended to choose one of the :ref:`production setups <deployment_production>`.

.. versionchanged:: 1.1.0
  MapProxy used `Paste Deploy <http://pythonpaste.org/deploy/>`_ (``paste serve``) for all deployment tasks prior to 1.1.0. This is now optional, see :ref:`paste_deploy`.

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

.. _deployment_production:

Production
----------

There are three ways to deploy MapProxy in production.

HTTP behind HTTP proxy
  You can run MapProxy as a separate local HTTP server behind an existing web server as a reverse proxy (nginx_, Apache, etc.) or an HTTP proxy (Varnish_, squid, etc).

FastCGI behind HTTP server
  You can run MapProxy as a FastCGI server behind a web server that supports the FastCGI protocol.

Embedded in HTTP server
  You can directly integrate MapProxy into your web server. Apache can integrate Python web services with the ``mod_wsgi`` extension for example. 

All approaches require a configuration that maps your MapProxy configuration with the MapProxy application. For the first two approaches you also need to configure the HTTP/FastCGI server. You can write a small script file for that or use Paste Deploy.

.. _server_script:

Server script
~~~~~~~~~~~~~

You need a script that makes the configured MapProxy available for the Python WSGI servers.

You can create a basic script with ``mapproxy-util``::

  mapproxy-util create -t wsgi-app -f mapproxy.yaml config.py

The script contains the following lines and makes the configured MapProxy available as ``application``::

  from mapproxy.wsgiapp import make_wsgi_app
  application = make_wsgi_app('examples/minimal/etc/mapproxy.yaml')

This is sufficient for embedding MapProxy with ``mod_wsgi`` or for starting it with ``gunicorn`` for example (see further below).

You can extend that script to start an actual server. All server follow a similar scheme and take the application as an argument.

Here is an example of a FastCGI server (based on flup)::

  from mapproxy.wsgiapp import make_wsgi_app
  application = make_wsgi_app('examples/minimal/etc/mapproxy.yaml')

  if __name__ == '__main__':
      from flup.server.fcgi_fork import WSGIServer
      WSGIServer(application, bindAddress='var/fcgi-socket').run()

You can start this server with::

  python config.py

`if __name__ == '__main__':` is a Python idiom that prevents code to be run when a script is not started, but imported by other applications. This allows you to use this script also in `mod_wsgi`, `gunicorn`, etc.

.. _paste_deploy:

Paste Deploy
~~~~~~~~~~~~

`Paste Deploy <http://pythonpaste.org/deploy/>`_ is a system for configuring WSGI applications and servers. You can use Paste's tool ``paster serve`` to start servers instead of creating your own server scripts. Paste Deploy requires a configuration that defines the application and the server.


Here is a minimal ``config.ini`` example that shows how you configure MapProxy as the WSGI application and Flup as a FastCGI server.
::

  [app:main]
  use = egg:MapProxy#app
  mapproxy_conf = %(here)s/mapproxy.yaml

  [server:main]
  use = egg:Flup#fcgi_fork
  socket = %(here)s/../var/fcgi-socket


To start the server with that configuration::

  paster serve config.ini

Paste Deploy allows you to easily combine multiple WSGI applications and to connect them with different WSGI filters. It is the recommended way for more complex setups, for example with MultiMapProxy or custom authentication filters.


HTTP behind HTTP proxy
----------------------

There are Python HTTP servers available that can directly run MapProxy. Most of them are robust and efficient, but there are some odd HTTP clients out there that (mis)interpret the HTTP standard in various ways. It is therefor recommended to put a HTTP server or proxy in front that is mature and widely deployed (like Apache_, Nginx_, etc.).

Python HTTP Server
~~~~~~~~~~~~~~~~~~

Gunicorn
""""""""

Gunicorn_ is a Python WSGI HTTP server for UNIX. Gunicorn use multiple processes but the process number is fixed. The default worker is synchronous, meaning that a process is blocked while it requests data from another server for example. You need to choose an asynchronous worker like eventlet_.

You need a server script that creates the MapProxy application (see :ref:`above <server_script>`). The script needs to be in the directory from where you start ``gunicorn`` and it needs to end with ``.py``.

To start MapProxy with the Gunicorn web server with four processes, the eventlet worker and our server script (without ``.py``)::
  
  cd /path/of/config.py/
  gunicorn -k eventlet -w 4 -b :8080 config:application

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

Here is an example for the Apache_ webserver with the included ``mod_proxy`` and ``mod_headers`` modules. It forwards all requests to ``example.org/mapproxy`` to ``localhost:8181/``.::

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

FastCGI
-------

FastCGI_ is a protocol to integrate web applications into web servers.
FastCGI is language-independent and implemented by most popular web servers. The applications run isolated from the web server. In this case you do not start MapProxy as an HTTP server but as a FastCGI server.


FastCGI Server
~~~~~~~~~~~~~~

flup_ is the best choice for an FastCGI server. It runs either multi threaded or multi processed (fork based).

To start a FastCGI server from your server script, add the following lines::

  if __name__ == '__main__':
      from flup.server.fcgi_fork import WSGIServer
      WSGIServer(application).run()


The FastCGI server can listen to a TCP port or to a UNIX socket. You can configure this with the ``bindAddress`` argument.

::

  WSGIServer(application, bindAddress='./fcgi.socket').run()
  # or
  WSGIServer(application,
             bindAddress=('localhost', 8181)).run()


For Paste Deploy you can configure the server as follows::

  [server:main]
  use = egg:Flup#fcgi_fork
  socket = %(here)s/../var/fcgi-socket



FastCGI Client
~~~~~~~~~~~~~~

Next you must configure you web server to forward incoming requests to your FastCGI server. Your web server acts as a FastCGI client in this case.


.. index:: mod_fastcgi, Apache

Apache mod_fastcgi and mod_fcgid
""""""""""""""""""""""""""""""""

There are two modules that support FastCGI for Apache. mod_fastcgi_ is an external module, while mod_fcgid_ is included in recent Apache versions.

For mod_fastcgi you can use the following snippet to add MapProxy to an Apache installation::

  # if not loaded else where
  LoadModule fastcgi_module modules/mod_fastcgi.so

  <IfModule mod_fastcgi.c>
   FastCGIExternalServer /tmp/madeup -socket \
      /path/to/mymapproxy/var/fcgi-socket
   Alias /mapproxy /tmp/madeup
  </IfModule>

.. note:: ``/tmp/madeup`` is just a dummy value and you can choose any path you want, the only limitation is that the directory must exist but not the file. In this example there must be a ``/tmp`` directory but the file ``madeup`` should not exist.

The ``fcgi-socket`` file needs to be writeable by the Apache process and you need to permit access to the parent directory of the ``madeup`` file. 

::

  <Directory "/tmp">
    Order allow,deny
    Allow from all
  </Directory>


.. seealso::
  Read `Deploying MapProxy on CentOS5 x86_64 using apache2 with mod_fastcgi or mod_fcgid <http://tmintt.eu/content/deploying-mapproxy-centos5-x8664-using-apache2-modfastcgi-or-modfcgid>`_ for more information on how to configure both.


.. index:: nginx

nginx
~~~~~

The following snippet adds MapProxy to an Nginx_ installation. Note that you need to split the URI manually if you use an nginx version before 0.7.31. If you have a more recent version, you can use `fastcgi_split_path_info <http://wiki.nginx.org/NginxHttpFcgiModule#fastcgi_split_path_info>`_.

::

  server {
    # server options
    # ...
    
    location /mapproxy {
      if ($uri ~ "^(/mapproxy)(/.*)$") {
        set $script_name  $1;
        set $path_info  $2;
      }
      fastcgi_pass   unix:/path/to/fcgi-socket;
      include fastcgi_params;
      fastcgi_param  SCRIPT_NAME $script_name;
      fastcgi_param  PATH_INFO   $path_info;
    }
  }


.. index:: lighttpd

Lighttpd
~~~~~~~~

Here is an example Lighttpd configuration::

  $HTTP["host"] == "example.org" {
    fastcgi.server += (
      "/mapproxy" => ((
        "check-local" => "disable",
        "socket"      => "/path/to/mymapproxy/var/fcgi-socket"
      ))
    )
  }

The first line restricts this configuration to the ``example.org`` hostname. In the third line you set the URL path where MapProxy should listen. The ``socket`` option should point to the ``fcgi-socket`` file that is used to communicate with the MapProxy FastCGI server.


.. index:: mod_wsgi, Apache

Embedding
---------

Some web servers can directly integrate Python code. The benefit is that you don't have to start another server, but the downside is that your application runs with the same privileges of your web server.

Apache mod_wsgi
~~~~~~~~~~~~~~~

If you use Apache then you can integrate MapProxy with `mod_wsgi`_. Read `mod_wsgi installation`_ for detailed instructions. 

``mod_wsgi`` requires a server script that defines the configured WSGI function as ``application``. See :ref:`above <server_script>`.

You need to modify your Apache ``httpd.conf`` as follows::

  # if not loaded elsewhere
  LoadModule wsgi_module modules/mod_wsgi.so

  WSGIScriptAlias /mapproxy /path/to/mapproxy/config.py

  <Directory /path/to/mapproxy/>
    Order deny,allow
    Allow from all
  </Directory>


``mod_wsgi`` has a lot of options for more fine tuning. ``WSGIPythonHome`` lets you configure your ``virtualenv`` and  ``WSGIDaemonProcess``/``WSGIProcessGroup`` allows you to start multiple processes. See the `mod_wsgi configuration directives documentation <http://code.google.com/p/modwsgi/wiki/ConfigurationDirectives>`_.

.. _`mod_wsgi`: http://code.google.com/p/modwsgi/
.. _`mod_wsgi installation`: http://code.google.com/p/modwsgi/wiki/InstallationInstructions


Other deployment options
------------------------

Refer to http://wsgi.org/wsgi/Servers for a list of some available WSGI servers. 

Performance
-----------

Because of the way Python handles threads in computing heavy applications (like MapProxy WMS is), you should choose a server that uses multiple processes (pre-forking based) for best performance.

The examples above are all minimal and you should read the documentation of your components to get the best performance with your setup.


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

Paste Deploy
""""""""""""
You can add the logging configuration to your deployment ``.ini`` file if you use :ref:`paste_deploy`.

Server Script
"""""""""""""

You can use the Python logging API or load an ``.ini`` configuration if you have a :ref:`server script <server_script>` for deployment.

The example script created with ``mapproxy-util create -t wsgi-app`` already contains code to load an ``.ini`` file. You just need to uncomment the lines and create a ``log.ini`` file. You can create an example ``log.ini`` with::

  mapproxy-util create -t log-ini log.ini


.. index:: MultiMapProxy
.. _multimapproxy:

MultiMapProxy
-------------

.. versionadded:: 0.9.1

You can run multiple MapProxy instances (configurations) within one process. You can either manually map URLs to a MapProxy configuration as :ref:`described in the configuration examples <paster_urlmap>` or you can use the MultiMapProxy application.

MultiMapProxy can dynamically load configurations. You can put all configurations into one directory and MapProxy maps each file to a URL: ``conf/proj1.yaml`` is available at ``http://hostname/proj1/``.

Each configuration will be loaded on demand and MapProxy caches each loaded instance. The configuration will be reloaded if the file changes.

MultiMapProxy as the following options:

``config_dir``
  The directory where MapProxy should look for configurations.

``allow_listing``
  If set to ``true``, MapProxy will list all available configurations at the root URL of your MapProxy. Defaults to ``false``.


Server Script
~~~~~~~~~~~~~

.. versionadded:: 1.2.0

There is a ``make_wsgi_app`` function in the ``mapproxy.multiapp`` package that creates configured MultiMapProxy WSGI application.

::
  
  from mapproxy.multiapp import make_wsgi_app
  application = make_wsgi_app('/path/to.projects', allow_listing=True)


Paste Deploy
~~~~~~~~~~~~

You can use Paste deploy, as described above, to configure and start MultiMapProxy. You need to use ``egg:MapProxy#multiapp`` instead of ``egg:MapProxy#app`` and you need to change the options.

Example ``config.ini``::

  [app:main]
  use = egg:MapProxy#multiapp
  config_dir = %(here)s/projects
  allow_listing = true

