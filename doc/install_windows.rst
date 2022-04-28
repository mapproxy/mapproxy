Installation on Windows
=======================

At frist you need a working Python installation. You can download Python from: https://www.python.org/download/. MapProxy requires Python 2.7, 3.4 or higher.

Virtualenv
----------

*If* you are using your Python installation for other applications as well, then we advise you to install MapProxy into a virtual Python environment to avoid any conflicts with different dependencies. *You can skip this if you only use the Python installation for MapProxy.*
`Read about virtualenv <https://virtualenv.pypa.io/en/latest/>`_ if you want to know more about the benefits.

To create a new virtual environment for your MapProxy installation and to activate it go to the command line and call::

 C:\Python27\python path\to\virtualenv.py c:\mapproxy_venv
 C:\mapproxy_venv\Scripts\activate.bat

.. note::
  The last step is required every time you start working with your MapProxy installation. Alternatively you can always explicitly call ``\mapproxy_venv\Scripts\<command>``.

.. note:: Apache mod_wsgi does not work well with virtualenv on Windows. If you want to use mod_wsgi for deployment, then you should skip the creation the virtualenv.

After you activated the new environment, you have access to ``python`` and ``pip``.
To install MapProxy with most dependencies call::

  pip install MapProxy

This might take a minute. You can skip the next step.


PIP
---

MapProxy and most dependencies can be installed with the ``pip`` command. ``pip`` is already installed if you are using Python >=2.7.9, or Python >=3.4. `Read the pip documentation for more information <https://pip.pypa.io/en/stable/installing/>`_.

After that you can install MapProxy with::

    c:\Python27\Scripts\pip install MapProxy

This might take a minute.

Dependencies
------------

Read :ref:`dependency_details` for more information about all dependencies.


Pillow and YAML
~~~~~~~~~~~~~~~

Pillow and PyYAML are installed automatically by ``pip``.

PyProj
~~~~~~

Since PROJ is generally not available on a Windows system, you will also need to install the Python package ``pyproj``.

::

  pip install pyproj

See *Platform dependent packages* below if this installation fails as Windows packages might not be available for pyproj.


Shapely and GEOS *(optional)*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shapely can be installed with ``pip install Shapely``. This will already include the required ``geos.dll``.


GDAL *(optional)*
~~~~~~~~~~~~~~~~~

MapProxy requires GDAL/OGR for coverage support. MapProxy can either load the ``gdal.dll`` directly or use the ``osgeo.ogr`` Python package. You can `download and install inofficial Windows binaries of GDAL and the Python package <http://www.gisinternals.com/sdk/>`_ (e.g. `gdal-19-xxxx-code.msi`).

You need to add the installation path to the Windows ``PATH`` environment variable in both cases.
You can set the variable temporary on the command line (spaces in the filename need no quotes or escaping)::

  set PATH=%PATH%;C:\Program Files (x86)\GDAL

Or you can add it to your `systems environment variables <http://www.computerhope.com/issues/ch000549.htm>`_.

You also need to set ``GDAL_DRIVER_PATH`` or ``OGR_DRIVER_PATH`` to the ``gdalplugins`` directory when you want to use the Oracle plugin (extra download from URL above)::

    set GDAL_DRIVER_PATH=C:\Program Files (x86)\GDAL\gdalplugins


.. _win_platform_packages:

Platform dependent packages
---------------------------

``pip`` downloads all packages from https://pypi.org/, but not all platform combinations might be available as a binary package, especially if you run a 64bit version of Python.

If you run into trouble during installation, because it is trying to compile something (e.g. complaining about ``vcvarsall.bat``), you should look at Christoph Gohlke's `Unofficial Windows Binaries for Python Extension Packages <http://www.lfd.uci.edu/~gohlke/pythonlibs/>`_. This is a reliable site for binary packages for Python. You need to download the right package: The ``cpxx`` code refers to the Python version (e.g. ``cp27`` for Python 2.7); ``win32`` for 32bit Python installations and ``amd64`` for 64bit.

You can install the ``.whl``, ``.zip`` or ``.exe`` packages with ``pip``::

  pip install path\to\package-xxx.whl


Check installation
------------------

To check if the MapProxy was successfully installed you can call ``mapproxy-util``. You should see the installed version number.
::

    mapproxy-util --version


Now continue with :ref:`Create a configuration <create_configuration>` from the installation documentation.

