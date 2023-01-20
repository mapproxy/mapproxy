Installation via Docker
=======================


There are several inofficial Docker images available on `Docker Hub`_ that provide ready-to-use containers for MapProxy.

.. _`Docker Hub`: https://hub.docker.com/search?q=mapproxy

The community has very good experiences with the following ones:

- https://hub.docker.com/repository/docker/justb4/mapproxy/general (`github just4b <https://github.com/justb4/docker-mapproxy>`_)
- https://hub.docker.com/r/kartoza/mapproxy (`github kartoza <https://github.com/kartoza/docker-mapproxy>`_)


Quickstart
------------------

As for an example the image of `kartoza/mapproxy`_ is used (`just4b/docker-mapproxy <https://hub.docker.com/repository/docker/justb4/mapproxy/general>`_ works the same way).

Create a directory (e.g. `mapproxy`) for your configuration files and mount it as a volume:

::

  docker run --name "mapproxy" -p 8080:8080 -d -t -v `pwd`/mapproxy:/mapproxy kartoza/mapproxy

Afterwards, the `MapProxy` instance is running on `localhost:8080`.

In a production environment you might want to put a `nginx`_ in front of the MapProxy container, that serves as a reverse proxy.
See the `Kartoza GitHub Repository`_ for detailed documentation and example docker-compose files. 

.. _`kartoza/mapproxy`: https://hub.docker.com/r/kartoza/mapproxy
.. _`nginx`: https://nginx.org
.. _`GitHub Repository`: https://github.com/kartoza/docker-mapproxy

There are also images available that already include binaries for `MapServer` or `Mapnik`:

- https://github.com/justb4/docker-mapproxy-mapserver
- https://github.com/justb4/docker-mapproxy-mapserver-mapnik

.. note::
  Please feel free to make suggestions for an official MapProxy docker image.
