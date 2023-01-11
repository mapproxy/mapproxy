Installation via Docker
=======================


There are several inofficial Docker images available on `Docker Hub`_ that provide ready-to-use containers for MapProxy.

.. _`Docker Hub`: https://hub.docker.com/search?q=mapproxy


Quickstart
------------------

As for an example the image of `kartoza/mapproxy`_ is used.
Create a directory (e.g. `mapproxy`) for your configuration files and mount it as a volume:

::

  docker run --name "mapproxy" -p 8080:8080 -d -t -v `pwd`/mapproxy:/mapproxy kartoza/mapproxy

Afterwards, the `MapProxy` instance is running on `localhost:8080`.

I a production environment you might want to put a `nginx`_ in front of the MapProxy container, that serves as a reverse proxy.
See the `GitHub Repository`_ for detailed documentation and example docker-compose files. 

.. _`kartoza/mapproxy`: https://hub.docker.com/r/kartoza/mapproxy
.. _`nginx`: https://nginx.org
.. _`GitHub Repository`: https://github.com/kartoza/docker-mapproxy
