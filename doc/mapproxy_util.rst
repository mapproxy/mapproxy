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
- :ref:`mapproxy_util_wms_capabilities`
- :ref:`mapproxy_util_grids`
- :ref:`mapproxy_util_export`
- ``autoconfig`` (see :ref:`mapproxy_util_autoconfig`)


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

.. cmdoption:: --version <versionnumber>

  Parse the Capabilities-document for the given version. Only version 1.1.1 and 1.3.0 are supported. The default value is 1.1.1



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

  Capabilities Document Version 1.1.1
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

Furthermore, default values for each grid will be displayed if they are not defined explicitly.
All default values are marked with an asterisk in the output.

.. program:: mapproxy-util grids

.. cmdoption:: -f <path/to/config>, --mapproxy-config <path/to/config>

  Display all configured grids for this MapProxy configuration with detailed information.
  If this option is not set, the sub-command will try to use the last argument as the mapproxy config.

.. cmdoption:: -l, --list

  Display only the names of the grids for the given configuration, which are used by any grid.

.. cmdoption:: --all

  Show also grids that are not referenced by any cache.

.. cmdoption:: -g <grid_name>, --grid <grid_name>

  Display information only for a single grid.
  The tool will exit, if the grid name is not found.

.. cmdoption:: -c <coverage name>, --coverage <coverage name>

  Display an approximation of the number of tiles for each level that  which are within this coverage.
  The coverage must be defined in Seed configuration.

.. cmdoption:: -s <seed.yaml>, --seed-conf <seed.yaml>

  This option loads the seed configuration and is needed if you use the ``--coverage`` option.

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
    localgrid2:
      base: localgrid
      srs: EPSG:25832
      res_factor: sqrt2
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

  mapproxy-util grids --grid localgrid --mapproxy-conf /path/to/mapproxy.yaml

::

    localgrid:
        Configuration:
            bbox: [5, 50, 10, 55]
            bbox_srs: 'EPSG:4326'
            min_res: 10000
            origin*: 'sw'
            srs: 'EPSG:31467'
            tile_size*: [256, 256]
        Levels: Resolutions, # x * y = total tiles
            00:  10000,             #      1 * 1      =        1
            01:  5000.0,            #      1 * 1      =        1
            02:  2500.0,            #      1 * 1      =        1
            03:  1250.0,            #      2 * 2      =        4
            04:  625.0,             #      3 * 4      =       12
            05:  312.5,             #      5 * 8      =       40
            06:  156.25,            #      9 * 15     =      135
            07:  78.125,            #     18 * 29     =      522
            08:  39.0625,           #     36 * 57     =   2.052K
            09:  19.53125,          #     72 * 113    =   8.136K
            10:  9.765625,          #    144 * 226    =  32.544K
            11:  4.8828125,         #    287 * 451    = 129.437K
            12:  2.44140625,        #    574 * 902    = 517.748K
            13:  1.220703125,       #   1148 * 1804   =   2.071M
            14:  0.6103515625,      #   2295 * 3607   =   8.278M
            15:  0.30517578125,     #   4589 * 7213   =  33.100M
            16:  0.152587890625,    #   9178 * 14426  = 132.402M
            17:  0.0762939453125,   #  18355 * 28851  = 529.560M
            18:  0.03814697265625,  #  36709 * 57701  =   2.118G
            19:  0.019073486328125, #  73417 * 115402 =   8.472G


.. _mapproxy_util_export:

``export``
==========

This sub-command exports tiles from one cache to another. This is similar to the seed tool, but you don't need to edit the configuration. The destination cache, grid and the coverage can be defined on the command line.


.. program:: mapproxy-util export


Required arguments:

.. cmdoption:: -f, --mapproxy-conf

  The path to the MapProxy configuration of the source cache.

.. cmdoption:: --source

  Name of the source or cache to export.

.. cmdoption:: --levels

  Comma separated list of levels to export. You can also define a range of levels. For example ``'1,2,3,4,5'``, ``'1..10'`` or ``'1,3,4,6..8'``.

.. cmdoption:: --grid

  The tile grid for the export. The option can either be the name of the grid as defined in the in the MapProxy configuration, or it can be the grid definition itself. You can define a grid as a single string of the key-value pairs. The grid definition :ref:`supports all grid parameters <grids>`. See below for examples.

.. cmdoption:: --dest

  Destination of the export. Can be a filename, directory or URL, depending on the export ``--type``.

.. cmdoption:: --type

  Choose the export type. See below for a list of all options.

Other options:

.. cmdoption:: --fetch-missing-tiles

  If MapProxy should request missing tiles from the source. By default, the export tool will only existing tiles.

.. cmdoption:: --coverage, --srs, --where

  Limit the export to this coverage. You can use a BBOX, WKT files or OGR datasources. See :doc:`coverages`.

.. option:: -c N, --concurrency N

  The number of concurrent export processes.


Export types
------------

``tms``:
    Export tiles in a TMS like directory structure.

``mapproxy`` or ``tc``:
    Export tiles like the internal cache directory structure. This is compatible with TileCache.

``mbtile``:
    Export tiles into a MBTile file.

``sqlite``:
    Export tiles into SQLite level files.

``geopackage``:
    Export tiles into a GeoPackage file.

``arcgis``:
    Export tiles in a ArcGIS exploded cache directory structure.

``compact-v1``:
    Export tiles as ArcGIS compact cache bundle files (version 1).


Examples
--------

Export tiles into a TMS directory structure under ``./cache/``. Limit export to the BBOX and levels 0 to 6.

::

    mapproxy-util export -f mapproxy.yaml --grid osm_grid \
        --source osm_cache --dest ./cache/ \
        --levels 1..6 --coverage 5,50,10,60 --srs 4326

Export tiles into an MBTiles file. Limit export to a shape coverage.

::

    mapproxy-util export -f mapproxy.yaml --grid osm_grid \
        --source osm_cache --dest osm.mbtiles --type mbtile \
        --levels 1..6 --coverage boundaries.shp \
        --where 'CNTRY_NAME = "Germany"' --srs 3857

Export tiles into an MBTiles file using a custom grid definition.

::

    mapproxy-util export -f mapproxy.yaml --levels 1..6 \
        --grid "srs='EPSG:4326' bbox=[5,50,10,60] tile_size=[512,512]" \
        --source osm_cache --dest osm.mbtiles --type mbtile \

