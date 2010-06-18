Configuration
#############

.. highlight:: yaml

There are a few different configuration files used by MapProxy. Some are required and some are optional.

``services.yaml``
    This file configures which services and layers the proxy should offer. You can
    define from where the proxy should get which data. You can also set metadata like
    contact information for the Capabilities documents.
    
``proxy.yaml``
    This is the main configuration of the proxy. Configure which servers should be
    started, where the cached data should be stored, etc.
    
``seed.yaml``
    This file is the configuration for the ``mapproxy-seed`` tool.
    

``develop.ini`` and ``config.ini``
    These are the paster configuration files that are used to start the proxy in development or production mode.

services.yaml
=============

All layers the proxy offers are configured in this file. The configuration uses the YAML format.


.. note:: The indentation is significant and shall only contain space characters. Tabulators are **not** permitted for indentation.

The configuration contains the keys ``service`` and ``layers``.


services
^^^^^^^^

Here you can configure which services should be started. For more information about the 
services read :doc:`services`.


Here is an example::

  services:
    tms:
    wms:
      md:
        title: MapProxy Example WMS
        contact:
        # [...]

layers
^^^^^^

Here you can define all layers the proxy should offer. Each layer configuration is a YAML dictionary. The key of each layer is also the name of the layer, i.e. the name used in WMS layers argument. If MapProxy should use the same ordering of the layers for capability responses, you should put the definitions in a list (prepend a ``-`` before the key).
::

  layers:
    - layer1:
      option1: aaa
      option2: bbb
    - layer2:
      option1: xxx
      option2: yyy


Each configuration item contains information about the layer (e.g. title) and where the data comes from (e.g. which WMS source or which cache).


You define the data sources of each layer here. The configuration :ref:`is explained below
<sources-conf-label>`.

attribution
"""""""""""
Overwrite the system-wide attribution line for this layer.

``inverse``
  If this option is set to ``true``, the colors of the attribution will be inverted. Use this if the normal attribution is hard to on this layer (i.e. on aerial imagery).


caches
^^^^^^

Here you can configure wich sources should be cached with which tile grids.
Available options are:

sources
"""""""

A list with one or more source names. The sources needs to be defined in the ``sources`` configuration. This option is `required`.

format
""""""
The 

grids
"""""

You can configure one or more grids for each cache. Internally MapProxy will create a cache for each grid.

    srs: ['EPSG:4326', 'EPSG:900913']

MapProxy supports on-the-fly transformation of requests between different SRSs. So
it is not required to add an extra cache for each supported SRS. For best performance
only the SRS most requests are in should be used.

There is some special handling layers that need geographical and projected coordinate
systems. If you set both ``EPSG:4326`` and ``EPSG:900913`` all requests with projected
SRS will access the ``EPSG:900913`` cache, requests with geographical SRS will use
``EPSG:4326``. The distortions from the transformation should be acceptable these to cached SRS.

md
""""
Metadata for this layer. At the moment only ``title`` ist supported. It will be used as the human readable name for WMS layers.

param
""""""

With ``param`` you can set the parameters of the data-source and cache.

``format``
    This is the internal image format for the cache. The default is ``image/png``.

``request_format``
    This format is used to request new tiles. If the bandwidth to the WMS server is high
    (e.g. localhost or LAN) you should use ``image/tiff`` here. That prevents unnecessary
    encoding and decoding of the images. If unset ``format`` is used.

grids
^^^^^

Here you can define the tile grids that MapProxy uses for the internal caching.

Each grid can have the following options.

srs
"""
The spatial reference system used for the internal cache.

    srs: EPSG:4326

res
"""

The resolution for which MapProxy should cache tiles. There are three ways to configure the resolutions.

#. A factor between each resolution. With each step the resolution is multiplied by this
   factor. Defaults to 2.

#. A list with resolutions in units per pixel (degrees or meter per pixel).

#. The term ``sqrt2``. This option is a shorthand for a resolution factor of 1.4142
   (i.e. square root of two). With this factor the resolution doubles every second level.
   Compared to the default factor 2 you will get another cached level between all standard
   levels. This is suited for free zooming in vector-based layers where the results might
   look to blurry/pixelated in some resolutions.


For requests with no matching cached resolution the next best resolution is used and MapProxy will transform the result.

bbox
""""

The extend of your grid. You can use either a list or a string with the lower left and upper right coordinates. You can set the SRS of the coordinates with the ``bbox_srs`` option. If that option is not set the ``srs`` of the grid will be used.
::

  bbox: [0, 40, 15, 55]
    or
  bbox: "0,40,15,55"

bbox_srs
""""""""

The SRS of the grid bbox. See above.

tile_size
"""""""""

The size of each tile. Defaults to 256x256 pixel.
::
  
  tile_size: [512, 512]

num_levels
""""""""""

The total number of cached resolution levels. Defaults to 20, except for grids with  ``sqrt2`` resolutions. This option has no effect when you set an explicit list of cache resolutions.

stretch_factor
""""""""""""""
MapProxy chooses the `optimal` cached level for requests that do not exactly
match any cached resolution. MapProxy will stretch or shrink images to the
requested resolution. The `stretch_factor` defines the maximum factor
MapProxy is allowed to stretch images. Stretched images result in better
performance but will look blurry when the value is to large (> 1.2).

Example: Your MapProxy caches 10m and 5m resolutions. Requests with 9m
resolution will be generated from the 10m level, requests for 8m from the 5m
level.
  
max_shrink_factor
"""""""""""""""""
This factor only applies for the first level and defines the maximum factor
that MapProxy will shrink images.

Example: Your MapProxy layer starts with 1km resolution. Requests with 3km
resolution will get a result, requests with 5km will get a blank response.




watermark
"""""""""""

Add a watermark right into the cached data. The watermark is thus also present in TMS or KML requests.

``text``
    The watermark text. Should be short.

``opacity``
    The opacity of the watermark (from 0 transparent to 255 full opaque).
    Use a value between 3 and 10 for unobtrusive watermarks.


.. _sources-conf-label:

sources
^^^^^^^

A sources defines where MapProxy can request new data. Each source has a ``type``, other available options are depended to this type.

MapProxy support the following source types:

``wms``
"""""""

Use this source to request WMS servers.

req
---

This describes the WMS source. The only required options are ``url`` and ``layers``.
You need to set ``transparent`` to ``true`` if you want to use this source as an overlay.
::

  req:
    url: http://example.org/service?
    layers: base,roads
    transparent: true

All other options are added to the query string of the request.
::

  req:
    url: http://example.org/service?
    layers: base,roads
    map: /path/to/mapfile
    

wms_opts
--------

This option affects what request MapProxy sends to the source WMS server.

``version`` is the WMS version number used for requests (supported: 1.0.0, 1.1.1, 1.3.0).
If ``featureinfo`` is true, MapProxy will mark the layer as queryable and incoming
`GetFeatureInfo` requests will be forwarded to the source server.


.. _supported_srs-label:

supported_srs
-------------
A list with SRSs that the WMS source supports. MapProxy will only query the source in these SRSs. It will reproject data if it needs to get data from this layer in any other SRS.

You don't need to configure this if you only use this WMS as a cache source and the WMS supports all SRS of the cache.  

    
If you have multiple ``supported_srs`` and MapProxy needs to reproject it will use the
fist projected SRS for requests in projected SRS, and vice versa for geographic SRS. E.g
when `supported_srs` is ``['EPSG:4326', 'EPSG:31467']`` caches for EPSG:900913 will use
EPSG:32467.
    
  ..  .. note:: For the configuration of SRS for MapProxy see `srs_configuration`_.

Minimal example::

  - type: cache_wms
    req:
      url: http://localhost:8080/service?
      layers: base

Full example::

  - type: wms
    wms_opts:
      version: 1.0.0
      featureinfo: True
    supported_srs: ['EPSG:4326', 'EPSG:31467']
    req:
      url: http://localhost:8080/service?mycustomparam=foo
      layers: roads
      another_param: bar
      transparent: true

``tiles``
""""""""""

The ``tiles`` source can retrieve data from existing tile servers like TileCache and GeoWebCache. This source takes a
``url`` option that contains a URL template. The template format is ``%(key_name)s``. MapProxy supports the following named variables in the URL:

``x``, ``y``, ``z``
  The tile coordinate.
``format``
  The format of the tile.
``quadkey``
  Quadkey for the tile as described in http://msdn.microsoft.com/en-us/library/bb259689.aspx
``tc_path``
  TileCache path like ``09/000/000/264/000/000/345``. Note that it does not contain any format
  extension.

Additionally you can specify the origin of the tile grid with the ``origin`` option.
Supported values are ``sw`` for south-west (lower-left) origin or ``nw`` for north-west
(upper-left) origin. ``sw`` is the default.

Example::

  - type: cache_tiles
    url: http://localhost:8080/tile?x=%(x)s&y=%(y)s&z=%(z)s&format=%(format)s
    origin: ``nw``


``debug``
"""""""""""

Adds information like resolution and bbox to the response image.
This is useful to determine a fixed set of resolutions for the ``res``-parameter.


globals
^^^^^^^

Here you can define some internals of MapProxy and default values that are used in the other configuration directives.


``image``
"""""""""

Here you can define some options that affect the way MapProxy generates image results.

``resampling_method``
  The resampling method used when results need to be rescaled or transformed.
  You can use one of nearest, bilinear or bicubic. Nearest is the fastest and
  bicubic the slowest. The results will look best with bilinear or bicubic.
  Bicubic enhances the contrast at edges and should be used for vector images.
  
  With `bilinear` you should get about 2/3 of the `nearest` performance, with
  `bicubic` 1/3.
  
  See the examples below for results of `nearest`, `bilinear` and `bicubic`.
  
  .. image:: imgs/nearest.png
  .. image:: imgs/bilinear.png
  .. image:: imgs/bicubic.png


.. _jpeg_quality:

``jpeg_quality``
  An integer value from 0 to 100. Larger values result in slower performance,
  larger file sizes but better image quality. You should try values between 75
  and 90 for good compromise between performance and quality.

``cache``
"""""""""

``meta_size``
  MapProxy does not make a single request for every tile but will request a large meta-tile that consist of multiple tiles. ``meta_size`` defines how large a meta-tile is. A ``meta_size`` of ``[4, 4]`` will request 64 tiles in one pass. With a tile size of 256x256 this will result in 1024x1024 requests to the source WMS.
  
``meta_buffer``
  MapProxy will increase the size of each meta-tile request by this number of
  pixels in each direction. This can solve cases where labels are cut-off at
  the edge of tiles.


``base_dir``
  The base directory where all cached tiles will be stored. The path can
  either be absolute (e.g. ``/var/mapproxy/cache``) or relative to the
  proxy.yaml file.

``lock_dir``
  MapProxy uses locking to prevent multiple request for the same meta-tile.
  This option defines where the temporary lock files will be stored. The path
  can either be absolute (e.g. ``/tmp/lock/mapproxy``) or relative to the
  proxy.yaml file.
  
  .. note:: 
    Old locks will not be removed immediately but when new locks are created.
    So you will always find some old lock files in this directory.


``srs``
"""""""

``proj_data_dir``
  MapProxy uses Proj4 for all coordinate transformations. If you need custom projections
  or need to tweak existing definitions (e.g. add towgs parameter set) you can point
  MapProxy yo your own set of proj4 init files. The path should contain a ``epsg`` file
  with the EPSG definitions.
  
  The configured path can be absolute or relative to the proxy.yaml.

.. _axis_order:

``axis_order_ne`` and ``axis_order_ne``
  The axis ordering defines in which order coordinates are given, i.e. lon/lat or lat/lon.
  The ordering is dependent to the SRS. Most clients and servers did not respected the
  ordering and everyone used lon/lat ordering. With the WMS 1.3.0 specification the OGC
  emphasized that the axis ordering of the SRS should be used. 

  Here you can define the axis ordering of your SRS. This might be required for proper
  WMS 1.3.0 support if you use any SRS that is not in the default configuration.
  
  By default MapProxy assumes lat/long (north/east) order for all geographic and x/y
  (east/north) order for all projected SRS.
  
  If that is not the case for your SRS you need to add the SRS name to the appropriate
  parameter::

   srs:
     # for North/East ordering
     axis_order_ne: ['EPSG:9999', 'EPSG:9998']
     # for East/North ordering
     axis_order_en: ['EPSG:0000', 'EPSG:0001']

.. _http_ssl:

``http.ssl``
""""""""""""

.. note:: You need Python 2.6 or the `SSL module <http://pypi.python.org/pypi/ssl>`_ for this feature.

MapProxy supports access to HTTPS servers. Just use ``https`` instead of ``http`` when
defining the URL of a source. MapProxy needs a file that contains the root and CA
certificates. See the `Python SSL documentation <http://docs.python.org/dev/library/ssl.html#ssl-certificates>`_ for more information
about the format.
::

  http:
    ssl:
      ca_certs: ./certs_file

If you want to use SSL but do not need certificate verification, then you can disable it with the ``insecure`` option.
::

  http:
    ssl:
      insecure: True


``tile_creator_pool_size``
""""""""""""""""""""""""""

This limits the number of parallel requests MapProxy will make to a source WMS. This limit is per request and not for all MapProxy requests.

Example: A request in an uncached region requires MapProxy to fetch four meta-tiles. A tile_creator_pool_size of two allows MapProxy to make two requests to the source WMS request in parallel.

``http_client_timeout``
"""""""""""""""""""""""

This defines how long MapProxy should wait for data from source servers. Increase this value if your source servers are slower.

``tiles``
""""""""""

Configuration options for the TMS/Tile service.

``expires_hours``
  The number of hours a Tile is valid. TMS clients like web browsers will
  cache the tile for this time. Clients will try to refresh the tiles after
  that time. MapProxy supports the ETag and Last-Modified headers and will
  respond with the appropriate HTTP `'304 Not modified'` response if the tile
  was not changed.