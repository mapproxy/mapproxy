.. _mapproxy-util:

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


``serve-multiapp-develop``
==========================

.. versionadded:: 1.3.0


This sub-command is similar to ``serve-develop`` but it starts a :ref:`MultiMapProxy <multimapproxy>` instance.

You need to pass a directory of your MapProxy configurations as an argument. The server will automatically reload if you change any configuration or any of the MapProxy source code.


.. program:: mapproxy-util serve-multiapp-develop

.. cmdoption:: -b <address>, --bind <address>
  
  The server address where the HTTP server should listen for incomming connections. Can be a port (``:8080``), a host (``localhost``) or both (``localhost:8081``). The default is ``localhost:8080``. You need to use ``0.0.0.0`` to be able to connect to the server from external clients.


Example
-------

::

  mapproxy-util serve-multiapp-develop my_projects/



.. _mapproxy_util_scales:

``scales``
==========

.. versionadded:: 1.2.0

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

.. _mapproxy_util_wms_capabilities:

``wms_capabilities``
==========

.. versionadded:: 1.5.0

This sub-command parses a valid capabilites document from an URL and displays all available layers.

This tool does not create a MapProxy configuration, instead the displayed values shall help you to set up/modify your MapProxy configuration.

The command takes any valid URL, if errors occur during the parsing process or opening of the URL, an error message will be shown.

.. program:: mapproxy-util wms_capabilities

.. cmdoption:: --host <URL>

  Display all available Layers for this service. Each new layer will be marked with a hyphen and all sublayers are indented.


Example
-------

With the following MapProxy layer configuration:
::

  layers:
    - name: osm
      title: Omniscale OSM WMS - osm.omniscale.net
      sources: [osm_cache]
    - name: foo
      title: Group Layer
      layers:
        - name: layer1a
          title: Title of Layer 1a
          sources: [osm_cache]
        - name: layer1b
          title: Title of Layer 1b
          sources: [osm_cache]

Parsed capabilities document:
::

  mapproxy-util wms-capabilities http://127.0.0.1:8080/service?REQUEST=GetCapabilities

::

  Root-Layer:
    - title: MapProxy WMS Proxy
      url: http://127.0.0.1:8080/service?
      opaque: False
      srs: ['EPSG:31467', 'EPSG:31466', 'EPSG:4326', 'EPSG:25831', 'EPSG:25833', 'EPSG:25832', 'EPSG:31468', 'EPSG:900913', 'CRS:84', 'EPSG:4258']
      bbox: 
          EPSG:900913: [-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428]
          EPSG:4326: [-180.0, -85.0511287798, 180.0, 85.0511287798]
      queryable: False
      llbbox: [-180.0, -85.0511287798, 180.0, 85.0511287798]
      layers: 
        - name: osm
          title: Omniscale OSM WMS - osm.omniscale.net
          url: http://127.0.0.1:8080/service?
          opaque: False
          srs: ['EPSG:31467', 'EPSG:31466', 'EPSG:25832', 'EPSG:25831', 'EPSG:25833', 'EPSG:4326', 'EPSG:31468', 'EPSG:900913', 'CRS:84', 'EPSG:4258']
          bbox: 
              EPSG:900913: [-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428]
              EPSG:4326: [-180.0, -85.0511287798, 180.0, 85.0511287798]
          queryable: False
          llbbox: [-180.0, -85.0511287798, 180.0, 85.0511287798]
        - name: foobar
          title: Group Layer
          url: http://127.0.0.1:8080/service?
          opaque: False
          srs: ['EPSG:31467', 'EPSG:31466', 'EPSG:25832', 'EPSG:25831', 'EPSG:25833', 'EPSG:4326', 'EPSG:31468', 'EPSG:900913', 'CRS:84', 'EPSG:4258']
          bbox: 
              EPSG:900913: [-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428]
              EPSG:4326: [-180.0, -85.0511287798, 180.0, 85.0511287798]
          queryable: False
          llbbox: [-180.0, -85.0511287798, 180.0, 85.0511287798]
          layers: 
            - name: layer1a
              title: Title of Layer 1a
              url: http://127.0.0.1:8080/service?
              opaque: False
              srs: ['EPSG:31467', 'EPSG:31466', 'EPSG:4326', 'EPSG:25831', 'EPSG:25833', 'EPSG:25832', 'EPSG:31468', 'EPSG:900913', 'CRS:84', 'EPSG:4258']
              bbox: 
                  EPSG:900913: [-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428]
                  EPSG:4326: [-180.0, -85.0511287798, 180.0, 85.0511287798]
              queryable: False
              llbbox: [-180.0, -85.0511287798, 180.0, 85.0511287798]
            - name: layer1b
              title: Title of Layer 1b
              url: http://127.0.0.1:8080/service?
              opaque: False
              srs: ['EPSG:31467', 'EPSG:31466', 'EPSG:4326', 'EPSG:25831', 'EPSG:25833', 'EPSG:25832', 'EPSG:31468', 'EPSG:900913', 'CRS:84', 'EPSG:4258']
              bbox: 
                  EPSG:900913: [-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428]
                  EPSG:4326: [-180.0, -85.0511287798, 180.0, 85.0511287798]
              queryable: False
              llbbox: [-180.0, -85.0511287798, 180.0, 85.0511287798]