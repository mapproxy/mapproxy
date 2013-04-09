Installation on Windows
=======================

.. note:: You can also :doc:`install MapProxy inside an existing OSGeo4W installation<install_osgeo4w>`.

At frist you need a working Python installation. You can download Python from: http://www.python.org/download/. MapProxy requires Python 2.5, 2.6 or 2.7, it is *not* compatible with Python 3.

We advise you to install MapProxy into a `virtual Python environment`_.
`Read about virtualenv <http://virtualenv.openplans.org/#what-it-does>`_ if you want to now more about the benefits.

A self-contained version of virtualenv is available at:
https://github.com/pypa/virtualenv/raw/1.6.1/virtualenv.py

.. _`virtual Python environment`: http://guide.python-distribute.org/virtualenv.html

To create a new virtual environment for our proxy installation and to activate it go to the command line and call::

 C:\Python27\python path\to\virtualenv.py c:\mapproxy_venv
 C:\mapproxy_venv\Scripts\activate.bat

.. note::
  The last step is required every time you start working with your MapProxy installation. Alternatively you can always explicitly call ``\mapproxy_venv\Scripts\<command>``.

.. note:: Apache mod_wsgi does not work well with virtualenv on Windows. If you want to use mod_wsgi for deployment, then you should skip the creation the virtualenv. You need to `install the distribute package <http://pypi.python.org/pypi/distribute#distribute-setup-py>`_ to get the ``easy_install`` command.

After you activated the new environment, you have access to ``python`` and ``easy_install``.
To install MapProxy with most dependencies call::

  easy_install MapProxy

This might take a minute.


Dependencies
------------

Read :ref:`dependency_details` for more information about all dependencies.


PIL and YAML
~~~~~~~~~~~~

PIL and PyYAML are installed automatically by ``easy_install``.

PyProj
~~~~~~

Since libproj4 is generally not available on a Windows system, you will also need to install the Python package ``pyproj``.

::

  easy_install pyproj


Shapely and GEOS *(optional)*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shapely can be installed with ``easy_install Shapely``. This will already include the required ``geos.dll``.


GDAL *(optional)*
~~~~~~~~~~~~~~~~~

MapProxy requires GDAL/OGR for coverage support. MapProxy can either load the ``gdal.dll`` directly or use the ``osgeo.ogr`` Python package. You can `download and install inofficial Windows binaries of GDAL and the Python package <http://www.gisinternals.com/sdk/>`_ (e.g. `gdal-19-xxxx-code.msi`).

You need to add the installation path to the Windows ``PATH`` environment variable in both cases.
You can set the variable temporary on the command line (spaces in the filename need no quotes or escaping)::

  set PATH=%PATH%;C:\Program Files (x86)\GDAL

Or you can add it to your `systems environment variables <http://www.computerhope.com/issues/ch000549.htm>`_.

You also need to set ``GDAL_DRIVER_PATH`` or ``OGR_DRIVER_PATH`` to the ``gdalplugins`` directory when you want to use the Oracle plugin (extra download from URL above)::

    set GDAL_DRIVER_PATH=C:\Program Files (x86)\GDAL\gdalplugins


Platform dependent packages
---------------------------

All Python packages are downloaded from http://pypi.python.org/, but not all platform combinations might be available as a binary package, especially if you run a 64bit version of Windows.

If you run into troubles during installation, because it is trying to compile something (e.g. complaining about ``vcvarsall.bat``), you should look at Christoph Gohlke's `Unofficial Windows Binaries for Python Extension Packages <http://www.lfd.uci.edu/~gohlke/pythonlibs/>`_.

You can install the ``.exe`` packages with ``easy_install``::

  easy_install path\to\package-xxx.exe


Check installation
------------------

To check if the MapProxy was successfully installed you can call ``mapproxy-util``. You should see the installed version number.
::

    mapproxy-util --version


Now continue with :ref:`Create a configuration <create_configuration>` from the installation documentation.


