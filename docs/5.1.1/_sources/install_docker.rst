Installation via Docker
========================

MapProxy has its own official docker images.
These are currently hosted on the GitHub container registry and can be found here:

  -  https://github.com/mapproxy/mapproxy/pkgs/container/mapproxy%2Fmapproxy

Currently we have 6 different images for every release, named e.g.

  - ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0
  - ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-alpine

  - ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-dev
  - ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-alpine-dev

  - ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-nginx
  - ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-alpine-nginx

The alpine variants use alpine base images and are functionally the same as the other images.

The first ones comes with everything installed, but no HTTP WebServer running. These can be used for seeding tasks or as
base images for implementing custom setups. As they have no WebServer running they are not used normally.

The images ending with ``-dev``, start the integrated webserver mapproxy provides through
``mapproxy-util serve-develop``. These should not be used in a production environment!

The images ending with ``-nginx``, come bundled with a preconfigured `nginx <https://nginx.org/>`_ HTTP Server, that
lets you use MapProxy instantly in a production environment.

See the quickstart section below for a configuration / example on how to use those images.

There are also several unofficial Docker images available on `Docker Hub <https://hub.docker.com/search?q=mapproxy>`_
that provide ready-to-use containers forMapProxy.

The community has very good experiences with the following ones:

- https://hub.docker.com/repository/docker/justb4/mapproxy/general (`github just4b <https://github.com/justb4/docker-mapproxy>`_)
- https://hub.docker.com/r/kartoza/mapproxy (`github kartoza <https://github.com/kartoza/docker-mapproxy>`_)

There are also images available that already include binaries for `MapServer` or `Mapnik`:

- https://github.com/justb4/docker-mapproxy-mapserver
- https://github.com/justb4/docker-mapproxy-mapserver-mapnik


Quickstart
----------

The mapproxy repository includes an `example docker compose file <https://github.com/mapproxy/mapproxy/blob/master/docker-compose.yaml>`_
that you can use to run one of the images or as a reference for the most commonly used options.

Create a directory (e.g. `mapproxyconfig`) for your configuration files. Put your configs into that folder.
If you do not supply a mapproxy config file the image will create a default seed.yaml and mapproxy.yaml for you.

Then pull the image that you want to use, for example:

.. code-block:: sh

  docker pull ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-nginx

And then run the image like this:

.. code-block:: sh

  docker run --rm --name "mapproxy" -p 80:80 -v `pwd`/mapproxyconfig/mapproxy.yaml:/mapproxy/config/mapproxy.yaml ghcr.io/mapproxy/mapproxy/mapproxy:1.16.0-nginx

Afterwards, the `MapProxy` instance is running on http://localhost/mapproxy/demo/


Configuration
-------------


Volume-Mounts
~~~~~~~~~~~~~

- ``/mapproxy/config/mapproxy.yaml``: MapProxy Config
- ``/mapproxy/config/logging.ini``: Logging-Configuration
- ``/mapproxy/config/cache_data``: Cache Data dir. Make sure that this directory is writable for the mapproxy image.
This can be achieved with `chmod -R a+r cache_data`


Environment Variables
~~~~~~~~~~~~~~~~~~~~~

- ``MULTIAPP_MAPPROXY``: **This can only be used in nginx images.** If set to ``true``, MapProxy will start in multi app
mode and will run all configurations in the ``/mapproxy/config/apps`` directory as different apps. Default is ``false``.
- ``MULTIAPP_ALLOW_LISTINGS``: In multi app mode if set to ``true``, MapProxy lists all available apps on the root page.
Default is ``false``.


Build your own image
--------------------

There exist 2 docker files in this repository. One for the debian based images (`Dockerfile`) and one for the alpine
based images (`Dockerfile-alpine`). Both are multistage and have different targets:

- `base` for the plain image that does not start a webserver
- `development` for the development image that starts the dev server
- `nginx` for the nginx image that uses nginx to run mapproxy

So if you want to build the alpine nginx image, the command would look like this:

.. code-block:: sh

  docker build -f Dockerfile-alpine --target nginx -t ghcr.io/mapproxy/mapproxy/mapproxy:latest-alpine-nginx .
