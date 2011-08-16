#############
mapproxy-util
#############


The commandline tool ``mapproxy-util`` provides three sub-commands that are helpful when working with MapProxy.

To get a list of all sub-commands call::
 
 mapproxy-util
 

To call a sub-command::
  
  mapproxy-util subcommand


Each sub-command provides additional information::

  mapproxy-util subcommand --help
  



``create``
==========

This sub-command creates example configurations for you. There are templates for each configuration file.


.. program:: mapproxy-util create

.. cmdoption:: -l, --list-templates

  List names of all available configuration templates.

.. cmdoption:: -t <name>, --template <name>

  Create a configuration with the named template.

.. cmdoption:: -f <mapproxy.yaml>, --mapproxy-conf <mapproxy.yaml>

  The path to the MapProxy configuration. Required for some templates.

.. cmdoption:: --force

  Overwrite any existing configuration with the same output filename.



Configuration templates
-----------------------

Available templates are:

base-config:
  Creates an example ``mapproxy.yaml`` and ``seed.yaml`` file. You need to pass the destination directory to the command.


log-ini:
  Creates an example logging configuration. You need to pass the target filename to the command.

wsgi-app:
  Creates an example server script for the given MapProxy configuration (:option:`--f/--mapproxy-conf<mapproxy-util create -f>`) . You need to pass the target filename to the command.



Example
-------

::

  mapproxy-util create -t base-config ./



``serve-develop``
=================

This sub-command starts a MapProxy instance of your configuration as a stand-alone server.

You need to pass the MapProxy configuration as an argument. The server will automatically reload if you change the configuration or any of the MapProxy source code.


.. program:: mapproxy-util serve-develop

.. cmdoption:: -b <address>, --bind <address>
  
  The server address where the HTTP server should listen for incomming connections. Can be a port (``:8080``), a host (``localhost``) or both (``localhost:8081``). The default is ``localhost:8080``. You need to use ``0.0.0.0`` to be able to connect to the server from external clients.


Example
-------

::

  mapproxy-util serve-develop ./mapproxy.yaml


.. _mapproxy_util_scales:

``scales``
==========

This sub-command helps to convert between scales and resolutions.

Scales are ambiguous when the resolution of the output device (LCD, printer, mobile, etc) is unknown and therefore MapProxy only uses resolutions for configuration (see :ref:`scale_resolution`). You can use the ``scales`` sub-command to calculate between known scale values and resolutions.

The command takes a list with one or more scale values and returns the corresponding resolution value.

.. program:: mapproxy-util scales

.. cmdoption:: --unit <m|d>

  Return resolutions in this unit per pixel (default meter per pixel).

.. cmdoption:: -l <n>, --levels <n>

  Calculate resolutions for ``n`` levels. This will double the resolution of the last scale value if ``n`` is larger than the number of the provided scales.

.. cmdoption:: -d <dpi>, --dpi <dpi>

  The resolution of the output display to use for the calculation. You need to set this to the same value of the client/server software you are using. Common values are 72 and 96. The default value is the equivalent of a pixel size of .28mm, which is around 91 DPI. This is the value the OGC uses since the WMS 1.3.0 specification.

.. cmdoption:: --as-res-config

  Format the output so that it can be pasted into a MapProxy grid configuration.

.. cmdoption:: --res-to-scale

  Calculate from resolutions to scale.


Example
-------


For multiple levels as MapProxy configuration snippet:
::

  mapproxy-util scales -l 4 --as-res-config 100000

::

    res: [
         #  res            level        scale
           28.0000000000, #  0      100000.00000000
           14.0000000000, #  1       50000.00000000
            7.0000000000, #  2       25000.00000000
            3.5000000000, #  3       12500.00000000
    ]



With multiple scale values and custom DPI:
::

  mapproxy-util scales --dpi 96 --as-res-config \
      100000 50000 25000 10000
  
::

  res: [
       #  res            level        scale
         26.4583333333, #  0      100000.00000000
         13.2291666667, #  1       50000.00000000
          6.6145833333, #  2       25000.00000000
          2.6458333333, #  3       10000.00000000
  ]