Installation via Docker
========================

MapProxy does have its own official docker images.
These are currently hosted on the GitHub container registry and can be found here:

  -  https://github.com/mapproxy/mapproxy/pkgs/container/mapproxy%2Fmapproxy

Currently we have 3 different images for every release, named e.g.

  - ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0
  - ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-dev
  - ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-nginx

The first one comes with everything installed, but no HTTP WebServer running. You can use it to implement your custom setup.

The second image, ending with `-dev`, starts the integrated webserver mapproxy provides through `mapproxy-util serve-develop`.

The third image, ending with `-nginx`, comes bundled with a preconfigured `nginx`_ HTTP Server, that lets you use MapProxy instantly in a production environment.

See the quickstart section below for a configuration / example on how to use those images.

There are also several inofficial Docker images available on `Docker Hub`_ that provide ready-to-use containers for MapProxy.

.. _`Docker Hub`: https://hub.docker.com/search?q=mapproxy

The community has very good experiences with the following ones:

- https://hub.docker.com/repository/docker/justb4/mapproxy/general (`github just4b <https://github.com/justb4/docker-mapproxy>`_)
- https://hub.docker.com/r/kartoza/mapproxy (`github kartoza <https://github.com/kartoza/docker-mapproxy>`_)

There are also images available that already include binaries for `MapServer` or `Mapnik`:

- https://github.com/justb4/docker-mapproxy-mapserver
- https://github.com/justb4/docker-mapproxy-mapserver-mapnik


Quickstart
----------

Depending on your needs, pull the desired image (see description above):

 docker pull ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0

or:

  docker pull ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-dev

or:

  docker pull ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-nginx

Create a directory (e.g. `mapproxyconfig`) for your configuration files. Put your configs into that folder.
If you do not supply config files (seed.yaml and mapproxy.yaml) the image will create them for you.

To start the docker container with a mount on your config folder, use the command matching your image.

Running the `plain` image without starting a webserver
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

  docker run --rm --name "mapproxy" -d -t -v `pwd`/mapproxyconfig:/mapproxy/config ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0

Afterwards, the `MapProxy` instance is idling and you can connect with the container via e.g.

  docker exec -it mapproxy bash

Running the `dev` image
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

  docker run --rm --name "mapproxy" -p 8080:8080 -d -t -v `pwd`/mapproxyconfig:/mapproxy/config ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-dev

Afterwards, the `MapProxy` instance is running on http://localhost:8080/demo/


Running the `nginx` image
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

  docker run --rm --name "mapproxy" -p 80:80 -d -t -v `pwd`/mapproxyconfig:/mapproxy/config ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-nginx

Afterwards, the `MapProxy` instance is running on http://localhost/mapproxy/demo/


.. _`nginx`: https://nginx.org

Build your own image
--------------------
There is currently one build argument you can use.

  - `MAPPROXY_VERSION`: Set the version you want to build.

Switch to the `docker` folder in the mapproxy repository checkout and then execute

For the `plain` image without starting a webserver
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

  docker build --build-arg MAPPROXY_VERSION=1.16.0 --target base -t ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0 .

For the `dev` image
~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

  docker build --build-arg MAPPROXY_VERSION=1.16.0 --target development -t ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-dev .

For the `nginx` image
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

  docker build --build-arg MAPPROXY_VERSION=1.16.0 --target nginx -t ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-nginx .
