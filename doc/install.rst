Installation
============

This tutorial guides you to the MapProxy installation process on Unix systems. For Windows refer to :doc:`install_windows`.

This tutorial was created and tested with Debian and Ubuntu, if you're installing MapProxy on a different system you might need to change some package names.

MapProxy is `registered at the Python Package Index <https://pypi.org/project/MapProxy/>`_ (PyPI). If you have Python 3.9 or higher, you can install MapProxy with::

  python -m pip install MapProxy

This is really, easy `but` we recommend to install MapProxy into a `virtual Python environment`_. A ``virtualenv`` is a self-contained Python installation where you can install arbitrary Python packages without affecting the system installation. You also don't need root permissions for the installation.

`Read about virtualenv <https://virtualenv.pypa.io/en/latest/>`_ if you want to know more about the benefits.


.. _`virtual Python environment`: http://guide.python-distribute.org/virtualenv.html

Create a new virtual environment
--------------------------------

``virtualenv`` is available as ``python-virtualenv`` on most Linux systems. You can also `install Virtualenv from source <https://virtualenv.pypa.io/en/latest/installation.html>`_.

To create a new environment with the name ``venv`` call::

    virtualenv --system-site-packages venv

You should now have a Python installation under ``venv/bin/python``.

.. note:: Virtualenv will use your Python system packages (like ``python-imaging`` or ``python-yaml``) only when the virtualenv was created with the ``--system-site-packages`` option.

You need to either prefix all commands with ``venv/bin``, set your ``PATH`` variable to include the bin directory or `activate` the virtualenv with::

    source venv/bin/activate

This will change the ``PATH`` for your `current` session.


Install Dependencies
--------------------

MapProxy is written in Python, thus you will need a working Python installation. MapProxy works with Python 3.9 or higher, which should already be installed with most Linux distributions.

MapProxy requires a few third-party libraries that are required to run.

Installation
^^^^^^^^^^^^

On a Debian or Ubuntu system, you need to install the following packages::

  sudo apt-get install libgeos-dev libgdal-dev libxml2-dev libxslt-dev

Additional dependencies are installed automatically via pip when running `pip install MapProxy`. It is possible to use
apt packages for some dependencies instead, pip will detect them if they are already installed and can be used. The apt
packages will only work if the python version you are using is the same as the system wide installed python. The system
packages can be quite old, so this is **not recommended**::

  sudo apt-get install python3-dev python3-pil python3-yaml python3-pyproj python3-lxml python3-shapely


Install MapProxy
----------------

Your virtual environment should contain `pip`_, a tool to install Python packages.

To install you need to call::

  pip install MapProxy

You specify the release version of MapProxy. E.g.::

  pip install MapProxy==1.10.0

or to get the latest 1.10.0 version::

  pip install "MapProxy>=1.10.0,<=1.10.99"

To check if the MapProxy was successfully installed, you can call the `mapproxy-util` command.
::

    mapproxy-util --version

.. _`pip`: https://pip.pypa.io/en/stable/

.. note::

  ``pip`` will download packages from the `Python Package Index <https://pypi.org/>`_ and therefore require full internet access. You need to set the ``https_proxy`` environment variable if you only have access to the internet via an HTTP proxy. See :ref:`http_proxy` for more information.

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

    mapproxy-util serve-develop mymapproxy/mapproxy.yaml

There is already a test layer configured that obtains data from the `Omniscale OpenStreetMap WMS`_. Feel free to use this service for testing.

MapProxy comes with a demo service that lists all configured WMS and TMS layers. You can access that service at http://localhost:8080/demo/

.. _`Omniscale OpenStreetMap WMS`: https://maps.omniscale.com/


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

New releases of MapProxy are backwards compatible with older configuration files. MapProxy will issue warnings on start-up if a behavior will change in the next releases. You are advised to upgrade in single release steps (e.g. 1.9.0 to 1.10.0 to 1.11.0) and to check the output of ``mapproxy-util serve-develop`` for any warnings. You should also refer to the Changes Log of each release to see if there is anything to pay attention for.

If you upgrade from 0.8, please read the `old migration documentation <http://mapproxy.org/docs/1.5.0/migrate.html>`_.
