Installation on Windows
=======================

At frist you need a working Python installation. You can download Python from: http://www.python.org/download/. MapProxy requires Python 2.5, 2.6 or 2.7, it is *not* compatible with Python 3.

We advise you to install MapProxy into a `virtual Python environment`_. 
`Read about virtualenv <http://virtualenv.openplans.org/#what-it-does>`_ if you want to now more about the benefits.

A self-contained version of virtualenv is available at:
http://bitbucket.org/ianb/virtualenv/raw/1.5.1/virtualenv.py

.. _`virtual Python environment`: http://guide.python-distribute.org/virtualenv.html

To create a new virtual environment for our proxy installation and to activate it go to the command line and call::
 
 C:\Python26\python path\to\virtualenv.py c:\mapproxy_venv
 C:\mapproxy_venv\Scripts\activate.bat

.. note::
  The last step is required every time you start working with your MapProxy installation. Alternatively you can always explicitly call ``\mapproxy_venv\Scripts\<command>``.

.. note:: Apache mod_wsgi does not work with virtualenv on Windows. If you want to use mod_wsgi for deployment, then you should skip the creation the virtualenv. You need to `install the distribute package <http://pypi.python.org/pypi/distribute#distribute-setup-py>`_ to get the ``easy_install`` command.

.. note::
  If you put you virtual environment in a directory that contains a space in the name (e.g. "Documents and Settings" or "Program Files"), you will not be able to use the ``--reload`` option of `paster` unless you `install the appropriate win32api module <http://sourceforge.net/projects/pywin32/files/>`_.


After you activated the new environment, you have access to ``python`` and ``easy_install``.
To install MapProxy with most dependencies call::

  easy_install MapProxy

This might take some minutes.

Since libproj4 is generally not available on a Windows system, you will also need to install the Python package ``pyproj``.

::
  
  easy_install pyproj


To check if the MapProxy was successfully installed you can directly call the `version` module. You should see the installed version number.
::

    python -m mapproxy.version


Now continue with :ref:`Create a configuration <create_configuration>` from the installation documentation.


