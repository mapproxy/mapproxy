Deployment
==========

There are different ways to deploy Python web applications. MapProxy implements the Web Server Gateway Interface (WSGI) which is for Python what the Servlet API is for Java. 

The WSGI standard allows to choose between a wide range of servers and server integration components.

MapProxy uses :ref:`Paste Deploy <http://pythonpaste.org/deploy/>` to start these servers with a configured MapProxy application. It is a dependency of MapProxy and should be installed already. You can access the tool with ``paster serve``.

Paste Deploy needs a configuration where the application (MapProxy in this case) and the server are defined. The ``etc/`` directory created with ``paster create`` (see :doc:`install`) already contains two example configurations.
Both configurations define MapProxy as the WSGI application to start and setup some configuration options.

Testing
-------

The ``develop.ini`` uses the Paster HTTP Server as the WSGI server. This server already implements HTTP so you can directly access the MapProxy with your Web or GIS client on port 8080.

With the ``--reload`` option of ``paster serve`` MapProxy will take notice when you change any configuration and will reload these files.

This server is sufficient for local testing of the configuration. For production deployment we recommend other solutions.

Production
----------

`FastCGI`_ is a protocol to integrate web applications into web servers.
FastCGI is language-independent and implemented by most popular web servers like Apache, Lighttpd or Nginx. The applications run isolated from the web server. In this case you do not start MapProxy as an HTTP server but as a FastCGI server.

The example paster configuration ``config.ini`` does this. By default the configured server listens on a socket file (``var/fcgi-socket``) to which you should point your web server. But you can also use TCP/IP with the ``host`` and ``port`` option.

.. note:: You need to install `flup <http://pypi.python.org/pypi/flup/>`_ to run MapProxy as a FastCGI server:
          ``pip install flup``

To start MapProxy as a FastCGI server::

  paster serve etc/config.ini

Next you must configure you web server to talk to this FastCGI server.

.. _`FastCGI`: http://www.fastcgi.com/

.. index:: lighttpd

Lighttpd
""""""""

Here is an example Lighttpd configuration::

  $HTTP["host"] == "example.org" {
    fastcgi.server += (
      "/proxy" => ((
        "check-local" => "disable",
        "socket"      => "/path/to/mymapproxy/var/fcgi-socket"
      ))
    )
  }

The first line restricts this configuration to the ``example.org`` hostname. In the third line you set the URL path where MapProxy should listen. The ``socket`` option should point to the ``fcgi-socket`` file that is used to communicate with the MapProxy FastCGI server.

With this configuration you can access the MapProxy WMS at http://example.org/proxy/service?

.. index:: mod_fastcgi, Apache

Apache mod_fastcgi
""""""""""""""""""

You can use the following snippet to add the MapProxy FastCGI to an Apache installation::

  LoadModule fastcgi_module modules/mod_fastcgi.so

  <IfModule mod_fastcgi.c>
   FastCGIExternalServer /tmp/madeup -socket /path/to/mymapproxy/var/fcgi-socket
   Alias /proxy /tmp/madeup
  </IfModule>

.. note:: ``/tmp/madeup`` is just a dummy value and you can choose any path you want, the only limitation is that the directory must exist but not the file. In this example there must be a ``/tmp`` directory but the file ``madeup`` should not exist.

.. index:: nginx

nginx
"""""

The following snippet adds MapProxy to an nginx installation. Note that you need to split the URI manually if you use an nginx version before 0.7.31. If you have a more recent version, you can use `fastcgi_split_path_info <http://wiki.nginx.org/NginxHttpFcgiModule#fastcgi_split_path_info>`_.

::

  server {
    # server options
    # ...
    
    location /proxy {
      if ($uri ~ "^(/proxy)(/.*)$") {
        set $script_name  $1;
        set $path_info  $2;
      }
      fastcgi_pass   unix:/path/to/mymapproxy/var/fcgi-socket;
      include fastcgi_params;
      fastcgi_param  SCRIPT_NAME $script_name;
      fastcgi_param  PATH_INFO   $path_info;
    }
  }


Other deployment options
""""""""""""""""""""""""

Refer to http://wsgi.org/wsgi/Servers for a list of some available WSGI servers. 

.. note::
  Because of the way Python handles threads in computing heavy applications (like MapProxy WMS is), you should choose a (pre)forking-based server for best performance.

.. index:: mod_wsgi, Apache

Apache mod_wsgi
^^^^^^^^^^^^^^^

If you use Apache then you can integrate MapProxy with `mod_wsgi`_.
We will not go into detail about the installation here, but you can read more about `mod_wsgi installation`_ and then loosely follow the `Pylons integration`_ instructions. Pylons is a web framework that also uses paster for WSGI application configuration and deployment, so the steps are similar.

.. _`mod_wsgi`: http://code.google.com/p/modwsgi/
.. _`mod_wsgi installation`: http://code.google.com/p/modwsgi/wiki/InstallationInstructions
.. _`Pylons integration`: http://code.google.com/p/modwsgi/wiki/IntegrationWithPylons

.. index:: MultiMapProxy

MultiMapProxy
-------------

.. versionadded:: 0.9.1
.. note:: The interface/configuration of MultiMapProxy is not stable yet and might change with future releases.

You can run multiple MapProxy instances (configurations) within one process. You can either manually map URLs to a MapProxy configuration as :ref:`described in the configuration examples <paster_urlmap>` or you can use the MultiMapProxy application.

MultiMapProxy can dynamically load configurations. You can put all configurations into one directory and MapProxy maps each file to a URL: ``conf/proj1.yaml`` is available at ``http://hostname/proj1/``.

Each configuration will be loaded on demand and MapProxy caches each loaded instance. The configuration will be reloaded if the file changes.

You can use Paste deploy, as described above, to configure and start MultiMapProxy. The application takes the following options:

``config_dir``
  The directory where MapProxy should look for configurations.

``allow_listing``
  If set to ``true``, MapProxy will list all available configurations at the root URL of your MapProxy. Defaults to false.


Example ``config.ini``::

  [app:main]
  use = egg:MapProxy#multiapp
  config_dir = %(here)s/projects
  allow_listing = true
