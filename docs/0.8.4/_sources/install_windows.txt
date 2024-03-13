Installation on Windows
=======================

At frist you need a working Python installation. You can download Python from: http://www.python.org/download/. MapProxy requires Python 2.5 or 2.6, it is *not* compatible with Python 3.

We highly advise you to install MapProxy into a `virtual Python environment`_. 
`Read about virtualenv <http://virtualenv.openplans.org/#what-it-does>`_ if you want to now more about the benefits.

A self-contained version of virtualenv is available at:
http://bitbucket.org/ianb/virtualenv/raw/1.4.8/virtualenv.py

.. _`virtual Python environment`: http://guide.python-distribute.org/virtualenv.html


To create a new virtual environment for our proxy installation and to activate it go to the command line and call::
 
 C:\Python26\python path\to\virtualenv.py c:\mapproxy_venv
 C:\mapproxy_venv\Scripts\activate.bat
 
.. note::
  The last step is required every time you start working with your MapProxy installation.

.. note::
  If you put you virtual environment in a directory that contains a space in the name (e.g. "Documents and Settings" or "Program Files"), you will not be able to use the ``--reload`` option of `paster` unless you `install the appropriate win32api module <http://sourceforge.net/projects/pywin32/files/>`_.


After you activated the new environment, you have access to ``python`` and ``easy_install``.
To install MapProxy with all dependencies now call::

  easy_install MapProxy

This might take some minutes.

To check if the MapProxy was successfully installed you can directly call the `version` module. You should see the installed version number.
::

    python -m mapproxy.core.version


Now continue with :ref:`Create a configuration <create_configuration>` from the installation documentation.

