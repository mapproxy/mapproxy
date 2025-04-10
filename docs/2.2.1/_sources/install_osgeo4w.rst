﻿Installation on OSGeo4W
=======================


`OSGeo4W`_ is a popular package of open-source geospatial tools for Windows systems. Besides packing a lot of GIS tools and a nice installer, it also features a full Python installation, along with some of the packages that MapProxy needs to run.

.. _`OSGeo4W`: http://trac.osgeo.org/osgeo4w/

In order to install MapProxy within an OSGeo4W environment, the first step is to ensure that the needed Python packages are installed. In order to do so:

* Download and run the `OSGeo4W installer`
* Select advanced installation
* When shown a list of available packages, check (at least) ``python`` and ``python-pil`` for installation.

.. _`OSGeo4W installer`: http://download.osgeo.org/osgeo4w/osgeo4w-setup.exe

Please refer to the `OSGeo4W installer FAQ <http://trac.osgeo.org/osgeo4w/wiki/FAQ>`_ if you've got trouble running it.

At this point, you should see an OSGeo4W shell icon on your desktop and/or start menu. Right-click that, and *run as administrator*.

In the OSGeo4W window, run::

 C:\OSGeo4W> pip install mapproxy

and

::

 C:\OSGeo4W> pip install pyproj

If these last two commands didn't print out any errors, your installation of MapProxy is successful. You can now close the OSGeo4W shell with administrator privileges, as it is no longer needed.

In older versions of OSGeo4W  ``pip`` may not recognized. In such a case, please follow the instructions for `installing pip with get-pip.py <https://pip.pypa.io/en/stable/installing/#installing-with-get-pip-py>`_ and rerty the above ``pip install`` commands.

Check installation
------------------

To check if the MapProxy was successfully installed, you can launch a regular OSGeo4W shell, and call ``mapproxy-util``. You should see the installed version number::

  C:\OSGeo4W> mapproxy-util --version

.. note::

    You need to run *all* MapProxy-related commands from an OSGeo4W shell, and not from a standard command shell.

Now continue with :ref:`Create a configuration <create_configuration>` from the installation documentation.


Unattended OSGeo4W environment
-------------------------------


If you need to run unattended commands (like scheduled runs of *mapproxy-seed*), make a copy of ``C:\OSGeo4W\OSGeo4W.bat`` and modify the last line, to call ``cmd`` so it runs the MapProxy script you need, e.g.::

 cmd /c mapproxy-seed -s C:\path\to\seed.yaml -f C:\path\to\mapproxy.yaml









