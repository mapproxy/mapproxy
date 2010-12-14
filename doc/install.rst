Installation
============

This tutorial guides you to the MapProxy installation process on Unix systems. For Windows refer to :doc:`install_windows`.

This tutorial was created and tested with Debian 5.0, if you're installing MapProxy on a different system you might need to change some package names. 


MapProxy is `registered at the Python Package Index <http://pypi.python.org/pypi/MapProxy>`_ (PyPI). If you have installed Python setuptools (``python-setuptools`` on Debian) you can install MapProxy with ``sudo easy_install MapProxy``. This is really easy `but` we recommend to **not** use this method. 

We highly advise you to install MapProxy into a `virtual Python environment`_. 
`Read about virtualenv <http://virtualenv.openplans.org/#what-it-does>`_ if you want to know more about the benefits.

.. _`virtual Python environment`: http://guide.python-distribute.org/virtualenv.html

Create a new virtual environment
--------------------------------

If you don't have `virtualenv` installed, you can download a self-contained version::

    wget http://bitbucket.org/ianb/virtualenv/raw/1.5.1/virtualenv.py
    
Next we create a new virtual environment for our proxy installation. It is a good idea to organize all your environments into a single directory. I use ``~/venv`` for that. To create a new environment with the name ``mapproxy`` and to activate it call::

    python virtualenv.py --distribute ~/venv/mapproxy
    source ~/venv/mapproxy/bin/activate

.. note::
  The last step is required every time you start working with your MapProxy installation.

.. _`distribute`: http://packages.python.org/distribute/

Install MapProxy
----------------

MapProxy is written in Python, thus you will need a working Python installation. MapProxy works with Python 2.5, 2.6 and 2.7.

MapProxy has some dependencies, other libraries that are required to run. Most dependencies are small Python libraries that will be installed automatically when you install MapProxy. There are two exceptions for the base of MapProxy (libproj and PIL) and another for more advanced functionality (Shapely, GEOS, GDAL).

libproj
~~~~~~~
MapProxy uses the Proj4 C Library for all coordinate transformation tasks. Most distributions offer this library as a binary package. On Debian or Ubuntu you can install it with::
  
   sudo aptitude install libproj0
  

PIL
~~~
The Python Image Library (PIL) is also included in most distributions. On Debian or Ubuntu you can install it with::
  
    sudo aptitude install python-imaging


Shapely and GEOS
~~~~~~~~~~~~~~~~
You will need Shapely to use the :doc:`coverage feature <coverages>` of MapProxy. Shapely offers Python bindings for the GEOS library. You need Shapely >= 1.2.0 and GEOS >= 3.1.0::

    sudo aptitude install libgeos-dev
    pip install Shapely

GDAL
~~~~
The :doc:`coverage feature <coverages>` allows you to read geometries from OGR datasources (Shapefiles, PostGIS, etc.). This package is optional and only required for OGR datasource support. OGR is part of GDAL::

    sudo aptitude install libgdal-dev


Installation
~~~~~~~~~~~~

Your virtual environment should already contain `pip`_, a tool to install Python packages. If not, ``easy_install pip`` is enough to get it.

To install you need to call::

  pip install MapProxy

You specify the release version of MapProxy. E.g.::

  pip install MapProxy==0.9.0
  
or to get the latest 0.9 version::
 
  pip install "MapProxy>=0.9.0,<=0.9.99"

To check if the MapProxy was successfully installed, you can directly call the `version` module. You should see the installed version number.
::

    python -m mapproxy.version

.. _`pip`: http://pip.openplans.org/


.. _create_configuration:

Create a configuration
----------------------

To create a new set of configuration files for MapProxy call::

    paster create -t mapproxy_conf mymapproxy

This will create a ``mymapproxy`` directory with an ``etc``, ``var`` and ``tmp`` directory.
The ``etc`` directory contains all configuration files. Refer to the configuration documentation for more information. With the default configuration all log files and the cached data will be placed in the ``var`` directory.

Start the test server
---------------------

To start a test server::

    cd mymapproxy
    paster serve etc/develop.ini --reload

There is already a test layer configured that obtains data from the `Omniscale OpenStreetMap WMS`_. Feel free to use this service for testing.

MapProxy comes with a demo service that lists all configured WMS and TMS layers. You can access that service at http://localhost:8080/demo/

.. _`Omniscale OpenStreetMap WMS`: http://osm.omniscale.net/
