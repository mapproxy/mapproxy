Installation
============

This tutorial guides you to the MapProxy installation process on Unix systems. For Windows refer to :doc:`install_windows`.

This tutorial was created and tested with Debian 5.0/6.0 and Ubuntu 10.04 LTS, if you're installing MapProxy on a different system you might need to change some package names.

MapProxy is `registered at the Python Package Index <http://pypi.python.org/pypi/MapProxy>`_ (PyPI). If you have installed Python setuptools (``python-setuptools`` on Debian) you can install MapProxy with ``sudo easy_install MapProxy``.

This is really easy `but` we recommend to install MapProxy into a `virtual Python environment`_. A ``virtualenv`` is a self-contained Python installation where you can install arbitrary Python packages without affecting the system installation. You also don't need root permissions for the installation.

`Read about virtualenv <http://virtualenv.openplans.org/#what-it-does>`_ if you want to know more about the benefits.


.. _`virtual Python environment`: http://guide.python-distribute.org/virtualenv.html

Create a new virtual environment
--------------------------------

``virtualenv`` is available as ``python-virtualenv`` on most Linux systems. You can also download a self-contained version::

    wget https://github.com/pypa/virtualenv/raw/master/virtualenv.py

To create a new environment with the name ``mapproxy`` call::

    virtualenv --system-site-packages mapproxy
    # or
    python virtualenv.py --system-site-packages mapproxy

You should now have a Python installation under ``mapproxy/bin/python``.

.. note:: Newer versions of virtualenv will use your Python system packages (like ``python-imaging`` or ``python-yaml``) only when the virtualenv was created with the ``--system-site-packages`` option. If your (older) version of virtualenv does not have this option, then it will behave that way by default.

You need to either prefix all commands with ``mapproxy/bin``, set your ``PATH`` variable to include the bin directory or `activate` the virtualenv with::

    source mapproxy/bin/activate

This will change the ``PATH`` for you and will last for that terminal session.

.. _`distribute`: http://packages.python.org/distribute/

Install Dependencies
--------------------

MapProxy is written in Python, thus you will need a working Python installation. MapProxy works with Python 2.7, 3.3 and 3.4 which should already be installed with most Linux distributions. Python 2.6 should still work, but it is no longer officially supported.

MapProxy has some dependencies, other libraries that are required to run. There are different ways to install each dependency. Read :ref:`dependency_details` for a list of all required and optional dependencies.

Installation
^^^^^^^^^^^^

On a Debian or Ubuntu system, you need to install the following packages::

  sudo aptitude install python-imaging python-yaml libproj0

To get all optional packages::

  sudo aptitude install libgeos-dev python-lxml libgdal-dev python-shapely

.. note::
  Check that the ``python-shapely`` package is ``>=1.2``, if it is not
  you need to install it with ``pip install Shapely``.

.. _dependency_details:

Dependency details
^^^^^^^^^^^^^^^^^^

libproj
~~~~~~~
MapProxy uses the Proj4 C Library for all coordinate transformation tasks. It is included in most distributions as ``libproj0``.

.. _dependencies_pil:

Pillow
~~~~~~
Pillow, the successor of the Python Image Library (PIL), is used for the image processing and it is included in most distributions as ``python-imaging``. Please make sure that you have Pillow installed as MapProxy is no longer compatible with the original PIL. The version of ``python-imaging`` should be >=2.

You can install a new version of Pillow from source with::

  sudo aptitude install build-essential python-dev libjpeg-dev \
    zlib1g-dev libfreetype6-dev
  pip install Pillow


YAML
~~~~

MapProxy uses YAML for the configuration parsing. It is available as ``python-yaml``, but you can also install it as a Python package with ``pip install PyYAML``.

Shapely and GEOS *(optional)*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You will need Shapely to use the :doc:`coverage feature <coverages>` of MapProxy. Shapely offers Python bindings for the GEOS library. You need Shapely (``python-shapely``) and GEOS (``libgeos-dev``). You can install Shapely as a Python package with ``pip install Shapely`` if you system does not provide a recent (>= 1.2.0) version of Shapely.

GDAL *(optional)*
~~~~~~~~~~~~~~~~~
The :doc:`coverage feature <coverages>` allows you to read geometries from OGR datasources (Shapefiles, PostGIS, etc.). This package is optional and only required for OGR datasource support (BBOX, WKT and GeoJSON coverages are supported natively). OGR is part of GDAL (``libgdal-dev``).

.. _lxml_install:

lxml *(optional)*
~~~~~~~~~~~~~~~~~

`lxml`_ is used for more advanced WMS FeatureInformation operations like XSL transformation or the concatenation of multiple XML/HTML documents. It is available as ``python-lxml``.

.. _`lxml`: http://lxml.de

Install MapProxy
----------------

Your virtual environment should already contain `pip`_, a tool to install Python packages. If not, ``easy_install pip`` is enough to get it.

To install you need to call::

  pip install MapProxy

You specify the release version of MapProxy. E.g.::

  pip install MapProxy==1.8.0

or to get the latest 1.8.0 version::

  pip install "MapProxy>=1.8.0,<=1.8.99"

To check if the MapProxy was successfully installed, you can call the `mapproxy-util` command.
::

    mapproxy-util --version

.. _`pip`: http://pip.openplans.org/

.. note::

  ``pip`` and ``easy_install`` will download packages from the `Python Package Index <http://pypi.python.org>`_ and therefore they require full internet access. You need to set the ``http_proxy`` environment variable if you only have access to the internet via an HTTP proxy. See :ref:`http_proxy` for more information.

.. _create_configuration:

Create a configuration
----------------------

To create a new set of configuration files for MapProxy call::

    mapproxy-util create -t base-config mymapproxy

This will create a ``mymapproxy`` directory with a minimal example configuration (``mapproxy.yaml`` and ``seed.yaml``) and two full example configuration files (``full_example.yaml`` and ``full_seed_example.yaml``).

Refer to the :doc:`configuration documentation<configuration>` for more information. With the default configuration the cached data will be placed in the ``cache_data`` subdirectory.


Start the test server
---------------------

To start a test server::

    cd mymapproxy
    mapproxy-util serve-develop mapproxy.yaml

There is already a test layer configured that obtains data from the `Omniscale OpenStreetMap WMS`_. Feel free to use this service for testing.

MapProxy comes with a demo service that lists all configured WMS and TMS layers. You can access that service at http://localhost:8080/demo/

.. _`Omniscale OpenStreetMap WMS`: http://osm.omniscale.de/


Upgrade
-------

You can upgrade MapProxy with pip in combination with a version number or with the ``--upgrade`` option.
Use the ``--no-deps`` option to avoid upgrading the dependencies.

To upgrade to version 1.x.y::

  pip install 'MapProxy==1.x.y'


To upgrade to the latest release::

  pip install --upgrade --no-deps MapProxy


To upgrade to the current development version::

  pip install --upgrade --no-deps https://github.com/mapproxy/mapproxy/tarball/master


Changes
^^^^^^^

New releases of MapProxy are backwards compatible with older configuration files. MapProxy will issue warnings on startup if a behavior will change in the next releases. You are advised to upgrade in single release steps (e.g. 1.2.0 to 1.3.0 to 1.4.0) and to check the output of ``mapproxy-util serve-develop`` for any warnings. You should also refer to the Changes Log of each release to see if there is anything to pay attention for.

If you upgrade from 0.8, please read the old mirgation documentation <http://mapproxy.org/docs/1.5.0/migrate.html>`_.
