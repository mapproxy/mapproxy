Configuration
#############

There are a few different configuration files used by MapProxy.

``mappproxy.yaml``
    This is the main configuration of MapProxy. It configures all aspects of the server:
    Which servers should be started, where comes the data from, what should be cached,
    etc..
    
``seed.yaml``
    This file is the configuration for the ``mapproxy-seed`` tool. See :doc:`seeding documentation <seed>` for more information.

``develop.ini`` or ``config.ini``
    These are the paster configuration files that are used to start MapProxy in development or production mode. See :doc:`deployment documentation <deployment>` for more information.


.. note:: The configuration changed with the 0.9.0 release and you have to update any older configuration. This is a one-time change and further versions will offer backwards-compatibility. Read the :doc:`migration guide <migrate>` for some help.

.. index:: mapproxy.yaml

mapproxy.yaml
=============

The configuration uses the YAML format.

The MapProxy configuration is grouped into six sections, each configures a different aspect of MapProxy. These are the following sections:

- ``globals``:  Internals of MapProxy and default values that are used in the other configuration sections.
  
- ``services``:
  The services MapProxy offers, e.g. WMS or TMS.

- ``sources``: Define where MapProxy can retrieve new data.

- ``caches``: Configure the internal caches.

- ``layers``: Configure the layers that MapProxy offers. Each layer can consist of multiple sources and caches.
  
- ``grids``: Define the grids that MapProxy uses to aligns cached images.
  
The order of the sections is not important, so you can organize it your way.

.. note:: The indentation is significant and shall only contain space characters. Tabulators are **not** permitted for indentation.

.. #################################################################################

.. index:: services

services
--------

Here you can configure which services should be started. The configuration for all services is described in the :doc:`services` documentation.

Here is an example::

  services:
    tms:
    wms:
      md:
        title: MapProxy Example WMS
        contact:
        # [...]

.. #################################################################################
.. index:: layers

layers
------

Here you can define all layers MapProxy should offer. Each layer configuration is a YAML dictionary. The key of each layer is also the name of the layer, i.e. the name used in WMS layers argument. If MapProxy should use the same ordering of the layers for capability responses, you should put the definitions in a list (prepend a ``-`` before the key).
::

  layers:
    - layer1:
      title: Title of Layer 1
      sources: [cache1, source2]
    - layer2:
      title: Title of Layer 2
      sources: [cache3]


Each layer contains information about the layer and where the data comes from.

``title``
"""""""""
Readable name of the layer, e.g WMS layer title.

``sources``
"""""""""""
A list of data sources for this layer. You can use sources defined in the ``sources`` and ``caches`` section. MapProxy will merge multiple sources from left (bottom) to right (top). 


``min_res``, ``max_res`` or ``min_scale``, ``max_scale``
""""""""""""""""""""""""""""""""""""""""""""""""""""""""
.. NOTE paragraph also in sources/wms section
 
Limit the layer to the given min and max resolution or scale. MapProxy will return a blank image for requests outside of these boundaries. You can use either the resolution or the scale values, missing values will be interpreted as `unlimited`. Resolutions should be in meters per pixel.

The values will also apear in the capabilities documents (i.e. WMS ScaleHint and Min/MaxScaleDenominator).

Pleas read :ref:`scale vs. resolution <scale_resolution>` for some notes on `scale`.


.. ``attribution``
.. """"""""""""""""
.. 
.. Overwrite the system-wide attribution line for this layer.
.. 
.. ``inverse``
..   If this option is set to ``true``, the colors of the attribution will be inverted. Use this if the normal attribution is hard to on this layer (i.e. on aerial imagery).


.. #################################################################################
.. index:: caches

caches
------

Here you can configure wich sources should be cached.
Available options are:

``sources``
"""""""""""

A list with one or more source names. The sources needs to be defined in the ``sources`` configuration. This option is `required`. MapProxy will merge multiple sources before they are stored on disk.

``format``
""""""""""

The internal image format for the cache. The default is ``image/png``.


``request_format``
""""""""""""""""""

MapProxy will try to use this format to request new tiles, if it is not set ``format`` is used. This option has no effect if the source does not support that format or the format of the source is set explicitly (see ``suported_format`` or ``format`` for sources).

.. index:: watermark

``link_single_color_images``
""""""""""""""""""""""""""""
If set to ``true``, MapProxy will not store tiles that only contain a single color as a
separate file. MapProxy stores these tiles only once and uses symbolic links to this file
for every occurrence. This can reduce the size of your tile cache if you have larger areas
with no data (e.g. water areas, areas with no roads, etc.).

.. note:: This feature is only available on Unix, since Windows has no support for symbolic links.

``minimize_meta_requests``
""""""""""""""""""""""""""
If set to ``true``, MapProxy will only issue a single request to the source. This option can reduce the request latency for uncached areas (on demand caching).

By default MapProxy requests all uncached meta tiles that intersect the requested bbox. With a typical configuration it is not uncommon that a requests will trigger four requests each larger than 2000x2000 pixel. With the ``minimize_meta_requests`` option enabled, each request will trigger only one request to the source. That request will be aligned to the next tile boundaries and the tiles will be cached.


``watermark``
"""""""""""""

Add a watermark right into the cached tiles. The watermark is thus also present in TMS or KML requests.

``text``
    The watermark text. Should be short.

``opacity``
    The opacity of the watermark (from 0 transparent to 255 full opaque).
    Use a value between 3 and 10 for unobtrusive watermarks.


``grids``
"""""""""

You can configure one or more grids for each cache. MapProxy will create one cache for each grid.
::

    srs: ['EPSG:4326', 'EPSG:900913']


MapProxy supports on-the-fly transformation of requests with different SRSs. So
it is not required to add an extra cache for each supported SRS. For best performance
only the SRS most requests are in should be used.

There is some special handling layers that need geographical and projected coordinate
systems. If you set both ``EPSG:4326`` and ``EPSG:900913`` all requests with projected
SRS will access the ``EPSG:900913`` cache, requests with geographical SRS will use
``EPSG:4326``.


``meta_size`` and ``meta_buffer``
"""""""""""""""""""""""""""""""""

Change the ``meta_size`` and ``meta_buffer`` of this cache. See :ref:`global cache options <meta_size>` for more details.

``use_direct_from_level`` and ``use_direct_from_res``
"""""""""""""""""""""""""""""""""""""""""""""""""""""

You can limit until which resolution MapProxy should cache data with these two options.
Requests below the configured resolution or level will be passed to the underlying source and the results will not be stored. The resolution of ``use_direct_from_res`` should use the units of the first configured grid of this cache.


Example ``caches`` configuration
""""""""""""""""""""""""""""""""
::

 caches:
  simple:
    source: [mysource]
    grids: [mygrid]
  fullexample:
    source: [mysource, mysecondsource]
    grids: [mygrid, mygrid2]
    meta_size: [8, 8]
    meta_buffer: 256
    watermark:
      text: MapProxy
    request_format: image/tiff
    format: image/jpeg
  


.. #################################################################################
.. index:: grids

grids
-----

Here you can define the tile grids that MapProxy uses for the internal caching.
There are multiple options to define the grid, but beware, not all are required at the same time and some combinations will result in ambiguous results.


``srs``
"""""""

The spatial reference system used for the internal cache, written as ``EPSG:xxxx``.

.. index:: tile_size

``tile_size``
"""""""""""""

The size of each tile. Defaults to 256x256 pixel.
::

  tile_size: [512, 512]

.. index:: res

``res``
"""""""

A list with all resolutions that MapProxy should cache.
::
  
  res: [1000, 500, 200, 100]

.. index:: res_factor

``res_factor``
""""""""""""""

Here you can define a factor between each resolution.
It should be either a number or the term ``sqrt2``. 
``sqrt2`` is a shorthand for a resolution factor of 1.4142, the square root of two. With this factor the resolution doubles every second level.
Compared to the default factor 2 you will get another cached level between all standard
levels. This is suited for free zooming in vector-based layers where the results might
look to blurry/pixelated in some resolutions.

For requests with no matching cached resolution the next best resolution is used and MapProxy will transform the result.

``threshold_res``
"""""""""""""""""

A list with resolutions at which MapProxy should switch from one level to another. MapProxy automatically tries to determine the optimal cache level for each request. You can tweak the behavior with the ``stretch_factor`` option (see below).

If you need explicit transitions from one level to another at fixed resolutions, then you can use the ``threshold_res`` option to define these resolutions. You only need to define the explicit transitions.

Example: You are caching at 1000, 500 and 200m/px resolutions and you are required to display the 1000m/px level for requests with lower than 700m/px resolutions and the 500m/px level for requests with higher resolutions. You can define that transition as follows::

  res: [1000, 500, 200]
  threshold_res: [700]

Requests with 1500, 1000 or 701m/px resolution will use the first level, requests with 700 or 500m/px will use the second level. All other transitions (between 500 an 200m/px in this case) will be calculated automatically with the ``stretch_factor`` (about 416m/px in this case with a default configuration).

``bbox``
""""""""

The extent of your grid. You can use either a list or a string with the lower left and upper right coordinates. You can set the SRS of the coordinates with the ``bbox_srs`` option. If that option is not set the ``srs`` of the grid will be used.
::

  bbox: [0, 40, 15, 55]
    or
  bbox: "0,40,15,55"

``bbox_srs``
""""""""""""

The SRS of the grid bbox. See above.

``num_levels``
""""""""""""""

The total number of cached resolution levels. Defaults to 20, except for grids with  ``sqrt2`` resolutions. This option has no effect when you set an explicit list of cache resolutions.

``min_res`` and ``max_res``
"""""""""""""""""""""""""""
The the resolutions of the first and the last level.

``stretch_factor``
""""""""""""""""""
MapProxy chooses the `optimal` cached level for requests that do not exactly
match any cached resolution. MapProxy will stretch or shrink images to the
requested resolution. The `stretch_factor` defines the maximum factor
MapProxy is allowed to stretch images. Stretched images result in better
performance but will look blurry when the value is to large (> 1.2).

Example: Your MapProxy caches 10m and 5m resolutions. Requests with 9m
resolution will be generated from the 10m level, requests for 8m from the 5m
level.
  
``max_shrink_factor``
""""""""""""""""""""""
This factor only applies for the first level and defines the maximum factor
that MapProxy will shrink images.

Example: Your MapProxy layer starts with 1km resolution. Requests with 3km
resolution will get a result, requests with 5km will get a blank response.

``base``
""""""""

With this option, you can base the grid on the options of another grid you already defined.

Defining Resolutions
""""""""""""""""""""

There are multiple options that influence the resolutions MapProxy will use for caching: ``res``, ``res_factor``, ``min_res``, ``max_res``, ``num_levels`` and also ``bbox`` and ``tile_size``. We describe the process MapProxy uses to build the list of all cache resolutions.

If you supply a list with resolution values in ``res`` then MapProxy will use this list and will ignore all other options.

If ``min_res`` is set then this value will be used for the first level, otherwise MapProxy will use the resolution that is needed for a single tile (``tile_size``) that contains the whole ``bbox``.

If you have ``max_res`` and ``num_levels``: The resolutions will be distributed between ``min_res`` and ``max_res``, both resolutions included. The resolutions will be logarithmical, so you will get a constant factor between each resolution. With resolutions from 1000 to 10 and 6 levels you would get 1000, 398, 158, 63, 25, 10 (rounded here for readability).

If you have ``max_res`` and ``res_factor``: The resolutions will be multiplied by ``res_factor`` until larger then ``max_res``.

If you have ``num_levels`` and ``res_factor``: The resolutions will be multiplied by ``res_factor`` for up to ``num_levels`` levels.


Example ``grids`` configuration
"""""""""""""""""""""""""""""""

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
      

.. #################################################################################
.. index:: sources

.. _sources-conf-label:

sources
-------

A sources defines where MapProxy can request new data. Each source has a ``type`` and all other options are dependent to this type.

See :doc:`sources` for the documentation of all available sources.

An example::

  sources:
    sourcename:
      type: wms
      req:
        url: http://localhost:8080/service?
        layers: base
    anothersource:
      type: wms
      # ...


.. #################################################################################
.. index:: globals
.. _globals-conf-label:

globals
-------

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

.. _meta_size:

``meta_size``
  MapProxy does not make a single request for every tile but will request a large meta-tile that consist of multiple tiles. ``meta_size`` defines how large a meta-tile is. A ``meta_size`` of ``[4, 4]`` will request 16 tiles in one pass. With a tile size of 256x256 this will result in 1024x1024 requests to the source WMS.
  
``meta_buffer``
  MapProxy will increase the size of each meta-tile request by this number of
  pixels in each direction. This can solve cases where labels are cut-off at
  the edge of tiles.


``base_dir``
  The base directory where all cached tiles will be stored. The path can
  either be absolute (e.g. ``/var/mapproxy/cache``) or relative to the
  mapproxy.yaml file.

``lock_dir``
  MapProxy uses locking to prevent multiple request for the same meta-tile.
  This option defines where the temporary lock files will be stored. The path
  can either be absolute (e.g. ``/tmp/lock/mapproxy``) or relative to the
  mapproxy.yaml file.
  
  .. note:: 
    Old locks will not be removed immediately but when new locks are created.
    So you will always find some old lock files in this directory.

``concurrent_tile_creators``
  This limits the number of parallel requests MapProxy will make to a source WMS. This limit is per request and not for all MapProxy requests. To limit the requests MapProxy makes to a single server use the ``concurrent_requests`` option.

  Example: A request in an uncached region requires MapProxy to fetch four meta-tiles. A ``concurrent_tile_creators`` value of two allows MapProxy to make two requests to the source WMS request in parallel. The splitting of the meta tile and the encoding of the new tiles will happen in parallel to.

``srs``
"""""""

``proj_data_dir``
  MapProxy uses Proj4 for all coordinate transformations. If you need custom projections
  or need to tweak existing definitions (e.g. add towgs parameter set) you can point
  MapProxy yo your own set of proj4 init files. The path should contain a ``epsg`` file
  with the EPSG definitions.
  
  The configured path can be absolute or relative to the mapproxy.yaml.

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
  
  You need to add the SRS name to the appropriate parameter, if that is not the case for
  your SRS.::

   srs:
     # for North/East ordering
     axis_order_ne: ['EPSG:9999', 'EPSG:9998']
     # for East/North ordering
     axis_order_en: ['EPSG:0000', 'EPSG:0001']
     
  
  If you need to override one of the default values, then you need to define both axis
  order options, even if one is empty.

.. _http_ssl:

``http``
""""""""

Secure HTTPS Connections (HTTPS)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. note:: You need Python 2.6 or the `SSL module <http://pypi.python.org/pypi/ssl>`_ for this feature.

MapProxy supports access to HTTPS servers. Just use ``https`` instead of ``http`` when
defining the URL of a source. MapProxy needs a file that contains the root and CA
certificates. See the `Python SSL documentation <http://docs.python.org/dev/library/ssl.html#ssl-certificates>`_ for more information
about the format.
::

  http:
    ssl_ca_certs: ./certs_file

If you want to use SSL but do not need certificate verification, then you can disable it with the ``ssl_no_cert_check`` option. You can also disable this check on a source level, see :ref:`WMS source options <wms_source-ssl_no_cert_check>`.
::

  http:
    ssl_no_cert_check: True

``client_timeout``
^^^^^^^^^^^^^^^^^^

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


Notes
=====

.. _scale_resolution:

Scale vs. resolution
--------------------

Scale is the ratio of a distance on a map and the corresponding distance on the ground. This implies that the map distance and the ground distance are measured in the same unit. For MapProxy a `map` is just a collection of pixels and the pixels do not have any size/dimension. They do correspond to a ground size but the size on the `map` is depended of the physical output format. MapProxy can thus only work with resolutions (pixel per ground unit) and not scales.

This applies to all servers and the OGC WMS standard as well. Some neglect this fact and assume a fixed pixel dimension (like 72dpi), the OCG WMS 1.3.0 standard uses a pixel size of 0.28 mm/px (around 96dpi). But you need to understand that a `scale` will differ if you print a map (200, 300 or more dpi) or if you show it on a computer display (typical 90-120 dpi, but there are mobile devices with more than 300 dpi).

MapProxy will use the OCG value (0.28mm/px) if it's necessary to use a scale value (e.g. MinScaleDenominator in WMS 1.3.0 capabilities), but you should always use resolutions within MapProxy.


WMS ScaleHint
""""""""""""""

The WMS ScaleHint is a bit misleading. The parameter is not a scale but the diagonal pixel resolution. It also defines the ``min`` as the minimum value not the minimum resolution (e.g. 10m/px is a lower resolution than 5m/px, but 5m/px is the minimum value). MapProxy always uses the term resolutions as the side length in ground units per pixel and minimum resolution is always the higher number (100m/px < 10m/px). Keep that in mind when you use these values.
