Deployment
==========

There are different ways to deploy Python web applications. MapProxy implements the Web Server Gateway Interface (WSGI) which is for Python what the Servlet API is for Java. 

The WSGI standard allows to choose between a wide range of servers and server integration components.

MapProxy uses ``paster serve``, a tool included as a dependency, to start these servers with a configured MapProxy application.

Paster needs a configuration where the application (MapProxy in this case) and the server is defined. The ``etc/`` directory created with ``paster create`` in the installation documentation already contains two example configurations.
Both configuration define MapProxy as the WSGI application to start and setup some configuration options.

The ``develop.ini`` uses the Paster HTTP Server as the WSGI server. This server already implements HTTP so you can directly access the MapProxy with your GIS client on port 8080.

With the ``--reload`` option of ``paster serve`` MapProxy will take notice when you change any configuration and will reload these files.

This server is sufficient for local testing of the configuration. For production deployment we recommend other solutions.

Production deployment
---------------------


`FastCGI`_ is a protocol to integrate web application into web servers.
FastCGI is language-independent and implemented by most popular web servers like Apache, ISS, Lighttpd or Nginx. The application run isolated from the web server. In this case you do not start MapProxy as an HTTP server but as a FastCGI server.

The example paster configuration ``config.ini`` does this. By default the configured server listens on a socket file (``var/fcgi-socket``) to wich you should point your web server. But you can also use TCP/IP with the ``host`` and ``port`` option. 

.. _`FastCGI`: http://www.fastcgi.com/


Lighttpd
""""""""

Here is an example Lighttpd configuration::

  $HTTP["host"] == "example.org" {
    fastcgi.server += (
      "/proxy" => ((
        "check-local" => "disable",
        "socket"      => "/home/olt/mymapproxy/var/fcgi-socket"
      ))
    )
  }

The first line restricts this configuration to the ``example.org`` hostname. In the third line you set the URL path where MapProxy should listen. The ``socket`` option should point to the ``fcgi-socket`` file that is used to communicate with the MapProxy FastCGI server.

With this configuration you can access the MapProxy WMS at http://example.org/proxy/service?

Other deployment options
""""""""""""""""""""""""

If you use Apache then you can integrate MapProxy with `mod_wsgi`_.
We will not go into detail about the installation here, but you can read more about `mod_wsgi installation`_ and then loosely follow the `Pylons integration`_ instructions. Pylons is a web framework that also uses paster for WSGI application configuration and deployment, so the steps are similar.

.. _`mod_wsgi`: http://code.google.com/p/modwsgi/
.. _`mod_wsgi installation`: http://code.google.com/p/modwsgi/wiki/InstallationInstructions
.. _`Pylons integration`: http://code.google.com/p/modwsgi/wiki/IntegrationWithPylons

