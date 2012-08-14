.. _mapproxy-util:

#############
mapproxy-util
#############


The commandline tool ``mapproxy-util`` provides sub-commands that are helpful when working with MapProxy.

To get a list of all sub-commands call::

 mapproxy-util


To call a sub-command::

  mapproxy-util subcommand


Each sub-command provides additional information::

  mapproxy-util subcommand --help


The current sub-commands are:

- :ref:`mapproxy_util_create`
- :ref:`mapproxy_util_serve_develop`
- :ref:`mapproxy_util_serve_multiapp_develop`
- :ref:`mapproxy_util_scales`
- :ref:`mapproxy_util_grids`


.. _mapproxy_util_create:

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


.. index:: testing, development, server
.. _mapproxy_util_serve_develop:

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

.. index:: testing, development, server, multiapp
.. _mapproxy_util_serve_multiapp_develop:

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




.. index:: scales, resolutions
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

``wms-capabilities``
====================

.. versionadded:: 1.5.0

This sub-command parses a valid capabilites document from a URL and displays all available layers.

This tool does not create a MapProxy configuration, but the output should help you to set up or modify your MapProxy configuration.

The command takes a valid URL GetCapabilities URL.

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
      srs: ['EPSG:31467', 'EPSG:31466', 'EPSG:4326', 'EPSG:25831', 'EPSG:25833',
            'EPSG:25832', 'EPSG:31468', 'EPSG:900913', 'CRS:84', 'EPSG:4258']
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
          srs: ['EPSG:31467', 'EPSG:31466', 'EPSG:25832', 'EPSG:25831', 'EPSG:25833',
                'EPSG:4326', 'EPSG:31468', 'EPSG:900913', 'CRS:84', 'EPSG:4258']
          bbox:
              EPSG:900913: [-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428]
              EPSG:4326: [-180.0, -85.0511287798, 180.0, 85.0511287798]
          queryable: False
          llbbox: [-180.0, -85.0511287798, 180.0, 85.0511287798]
        - name: foobar
          title: Group Layer
          url: http://127.0.0.1:8080/service?
          opaque: False
          srs: ['EPSG:31467', 'EPSG:31466', 'EPSG:25832', 'EPSG:25831', 'EPSG:25833',
                'EPSG:4326', 'EPSG:31468', 'EPSG:900913', 'CRS:84', 'EPSG:4258']
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
              srs: ['EPSG:31467', 'EPSG:31466', 'EPSG:25832', 'EPSG:25831', 'EPSG:25833',
                    'EPSG:4326', 'EPSG:31468', 'EPSG:900913', 'CRS:84', 'EPSG:4258']
              bbox:
                  EPSG:900913: [-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428]
                  EPSG:4326: [-180.0, -85.0511287798, 180.0, 85.0511287798]
              queryable: False
              llbbox: [-180.0, -85.0511287798, 180.0, 85.0511287798]
            - name: layer1b
              title: Title of Layer 1b
              url: http://127.0.0.1:8080/service?
              opaque: False
              srs: ['EPSG:31467', 'EPSG:31466', 'EPSG:25832', 'EPSG:25831', 'EPSG:25833',
                    'EPSG:4326', 'EPSG:31468', 'EPSG:900913', 'CRS:84', 'EPSG:4258']
              bbox:
                  EPSG:900913: [-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428]
                  EPSG:4326: [-180.0, -85.0511287798, 180.0, 85.0511287798]
              queryable: False
              llbbox: [-180.0, -85.0511287798, 180.0, 85.0511287798]


.. _mapproxy_util_grids:

``grids``
=========

.. versionadded:: 1.5.0

This sub-command displays information about configured grids.

The command takes a MapProxy configuration file and returns all configured grids.
Keep in mind that it will include the following two default grids:

  - GLOBAL_GEODETIC
  - GLOBAL_MERCATOR

Furthermore, default values for each grid will be displayed if they are not defined explicitly.
All options with default values are marked with an asterisk.

.. program:: mapproxy-util grids

.. cmdoption:: -f <path/to/config>, --mapproxy-config <path/to/config>

  Display all configured grids for this MapProxy configuration with detailed information.
  If this option is not set, the sub-command will try to use the last argument as the mapproxy config.

.. cmdoption:: -l, --list

  Display only the names of the grids for the given configuration.

.. cmdoption:: -g <grid_name>, --grid <grid_name>

  Display information only for a single grid.
  The tool will exit, if the grid name is not found.

Example
-------

With the following MapProxy grid configuration:
::

  grids:
    localgrid:
      srs: EPSG:31467
      bbox: [5,50,10,55]
      bbox_srs: EPSG:4326
      min_res: 10000
      res_factor: sqrt2
    localgrid2:
      base: localgrid
      srs: EPSG:25832
      tile_size: [512, 512]


List all configured grids:
::

  mapproxy-util grids --list --mapproxy-config /path/to/mapproxy.yaml

::

    GLOBAL_GEODETIC
    GLOBAL_MERCATOR
    localgrid
    localgrid2


Display detailed information for one specific grid:
::

  mapproxy-util grids --grid localgrid --mapproxy-config /path/to/mapproxy.yaml

::

  localgrid:
    Configuration:
        bbox: [5, 50, 10, 55]
        bbox_srs: 'EPSG:4326'
        min_res: 10000
        origin*: 'sw'
        res_factor: 'sqrt2'
        srs: 'EPSG:31467'
        tile_size*: [256, 256]
    Levels: Resolutions, # Tiles x * Tiles y = total tiles:
        00:  10000,                # 1 * 1 = 1
        01:  7071.067811865475,    # 1 * 1 = 1
        02:  4999.999999999999,    # 1 * 1 = 1
        03:  3535.5339059327366,   # 1 * 1 = 1
        04:  2499.999999999999,    # 1 * 1 = 1
        05:  1767.766952966368,    # 1 * 2 = 2
        06:  1249.9999999999993,   # 2 * 2 = 4
        07:  883.8834764831838,    # 2 * 3 = 6
        08:  624.9999999999995,    # 3 * 4 = 12
        09:  441.94173824159185,   # 4 * 5 = 20
        10:  312.4999999999997,    # 5 * 8 = 40
        11:  220.9708691207959,    # 7 * 10 = 70
        12:  156.24999999999986,   # 9 * 15 = 135
        13:  110.48543456039795,   # 13 * 20 = 260
        14:  78.12499999999993,    # 18 * 29 = 522
        15:  55.242717280198974,   # 26 * 40 = 1040
        16:  39.062499999999964,   # 36 * 57 = 2052
        17:  27.621358640099487,   # 51 * 80 = 4080
        18:  19.531249999999982,   # 72 * 113 = 8136
        19:  13.810679320049744,   # 102 * 160 = 16320
        20:  9.765624999999991,    # 144 * 226 = 32544
        21:  6.905339660024872,    # 203 * 319 = 64757
        22:  4.882812499999996,    # 287 * 451 = 129437
        23:  3.452669830012436,    # 406 * 638 = 259028
        24:  2.441406249999998,    # 574 * 902 = 517748
        25:  1.726334915006218,    # 812 * 1276 = 1036112
        26:  1.220703124999999,    # 1147 * 1804 = 2069188
        27:  0.863167457503109,    # 1623 * 2551 = 4140273
        28:  0.6103515624999994,   # 2295 * 3608 = 8280360
        29:  0.4315837287515545,   # 3245 * 5102 = 16555990
        30:  0.3051757812499997,   # 4589 * 7216 = 33114224
        31:  0.21579186437577724,  # 6489 * 10204 = 66213756
        32:  0.15258789062499986,  # 9177 * 14431 = 132433287
        33:  0.10789593218788862,  # 12977 * 20408 = 264834616
        34:  0.07629394531249993,  # 18353 * 28861 = 529685933
        35:  0.05394796609394431,  # 25954 * 40815 = 1059312510
        36:  0.038146972656249965, # 36705 * 57721 = 2118649305
        37:  0.026973983046972155, # 51908 * 81629 = 4237198132
        38:  0.019073486328124983, # 73409 * 115441 = 8474408369
        39:  0.013486991523486078, # 103815 * 163258 = 16948629270
