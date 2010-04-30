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

    wget http://bitbucket.org/ianb/virtualenv/raw/1.4.8/virtualenv.py
    
Next we create a new virtual environment for our proxy installation. It is a good idea to organize all your environments into a single directory. I use ``~/venv`` for that. To create a new environment with the name ``mapproxy`` and to activate it call::

    python virtualenv.py --distribute ~/venv/mapproxy
    source ~/venv/mapproxy/bin/activate

.. note::
  The last step is required every time you start working with your MapProxy installation.

.. _`distribute`: http://packages.python.org/distribute/

Install MapProxy
----------------

Dependencies
~~~~~~~~~~~~

To install MapProxy you need

* C compiler
* Python 2.5 or 2.6 (development tools)

MapProxy uses the Python Image Library (PIL). To get full support for JPEG and PNG images and attribution/watermarks you will need the following libraries:

* libjpeg
* zlib
* libfreetype

To install all requirements on Debian or Ubuntu call::

    sudo aptitude install build-essential python-dev \
        libjpeg-dev libz-dev libfreetype6-dev


Installation
~~~~~~~~~~~~

Your virtual environment should already contain `pip`_, a tool to install Python packages. If not, ``easy_install pip`` is enough to get it. We have put a requirements file online that describes which Python packages are needed for MapProxy and where to get these.

To install MapProxy and all dependencies, call the following::

    pip install -r http://bitbucket.org/olt/mapproxy/raw/tip/requirements.txt

To check if the MapProxy was successfully installed, you can directly call the `version` module. You should see the installed version number.
::

    python -m mapproxy.core.version

.. _`pip`: http://pip.openplans.org/


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

You can now issue you first request to the MapProxy: `http://localhost:8080/service?`_
The capabilities document is at: http://localhost:8080/service?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetCapabilities

.. _`http://localhost:8080/service?`: http://localhost:8080/service?LAYERS=osm&FORMAT=image%2Fjpeg&SPHERICALMERCATOR=true&SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&STYLES=&EXCEPTIONS=application%2Fvnd.ogc.se_inimage&SRS=EPSG%3A900913&BBOX=229037.9129083,6551465.7261979,1596343.4746286,7469933.0579081&WIDTH=1118&HEIGHT=751

.. _`Omniscale OpenStreetMap WMS`: http://osm.omniscale.net/
