Configuration
#############

There are two configuration files used by MapProxy.

``mappproxy.yaml``
    This is the main configuration of MapProxy. It configures all aspects of the server:
    Which servers should be started, where comes the data from, what should be cached,
    etc..

``seed.yaml``
    This file is the configuration for the ``mapproxy-seed`` tool. See :doc:`seeding documentation <seed>` for more information.

.. index:: mapproxy.yaml

mapproxy.yaml
-------------

The configuration uses the YAML format. The Wikipedia contains a `good introduction to YAML <http://en.wikipedia.org/wiki/YAML>`_.

The MapProxy configuration is grouped into sections, each configures a different aspect of MapProxy. These are the following sections:

- ``globals``:  Internals of MapProxy and default values that are used in the other configuration sections.

- ``services``:
  The services MapProxy offers, e.g. WMS or TMS.

- ``sources``: Define where MapProxy can retrieve new data.

- ``caches``: Configure the internal caches.

- ``layers``: Configure the layers that MapProxy offers. Each layer can consist of multiple sources and caches.

- ``grids``: Define the grids that MapProxy uses to aligns cached images.

The order of the sections is not important, so you can organize it your way.

.. note:: The indentation is significant and shall only contain space characters. Tabulators are **not** permitted for indentation.

There is another optional section:

.. versionadded:: 1.6.0

- ``parts``: YAML supports references and with that you can define configuration parts and use them in other configuration sections. For example, you can define all you coverages in one place and reference them from the sources. However, MapProxy will log a warning if you put the referent in a place where it is not a valid option. To prevent these warnings you are advised to put these configuration snippets inside the ``parts`` section.

For example::

  parts:
    coverages:
        mycoverage: &mycoverage
          bbox: [0, 0, 10, 10]
          srs: 'EPSG:4326'

  sources:
    mysource1:
      coverage: *mycoverage
      ...
    mysource2:
      coverage: *mycoverage
      ...


``base``
""""""""

You can split a configuration into multiple files with the ``base`` option. The ``base`` option loads the other files and merges the loaded configuration dictionaries together – it is not a literal include of the other files.

For example::

  base: [mygrids.yaml, mycaches_sources.yaml]
  service: ...
  layers: ...


.. versionchanged:: 1.4.0
  Support for recursive imports and for multiple files.

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

.. _layers_section:

layers
------

Here you can define all layers MapProxy should offer. The layer definition is similar to WMS: each layer can have a name and title and you can nest layers to build a layer tree.

Layers should be configured as a list (``-`` in YAML), where each layer configuration is a dictionary (``key: value`` in YAML)

::

  layers:
    - name: layer1
      title: Title of Layer 1
      sources: [cache1, source2]
    - name: layer2
      title: Title of Layer 2
      sources: [cache3]

Each layer contains information about the layer and where the data comes from.

.. versionchanged:: 1.4.0

The old syntax to configure each layer as a dictionary with the key as the name is deprecated.

::

  layers:
    mylayer:
      title: My Layer
      source: [mysoruce]

should become

::

  layers:
    - name: mylayer
      title: My Layer
      source: [mysoruce]

The mixed format where the layers are a list (``-``) but each layer is still a dictionary is no longer supported (e.g. ``- mylayer:`` becomes ``- name: mylayer``).

.. _layers_name:

``name``
"""""""""

The name of the layer. You can omit the name for group layers (e.g. layers with ``layers``), in this case the layer is not addressable in WMS and used only for grouping.


``title``
"""""""""
Readable name of the layer, e.g WMS layer title.


.. _layers:

``layers``
""""""""""

Each layer can contain another ``layers`` configuration. You can use this to build group layers and to build a nested layer tree.

For example::

  layers:
    - name: root
      title: Root Layer
      layers:
        - name: layer1
          title: Title of Layer 1
          layers:
            - name: layer1a
              title: Title of Layer 1a
              sources: [source1a]
            - name: layer1b
              title: Title of Layer 1b
              sources: [source1b]
        - name: layer2
          title: Title of Layer 2
          sources: [cache2]

``root`` and ``layer1`` is a group layer in this case. The WMS service will render ``layer1a`` and ``layer1b`` if you request ``layer1``. Note that ``sources`` is optional if you supply ``layers``. You can still configure ``sources`` for group layers. In this case the group ``sources`` will replace the ``sources`` of the child layers.

MapProxy will wrap all layers into an unnamed root layer, if you define multiple layers on the first level.

.. note::
  The old syntax (see ``name`` :ref:`above <layers_name>`) is not supported if you use the nested layer configuration format.

``sources``
"""""""""""
A list of data sources for this layer. You can use sources defined in the ``sources`` and ``caches`` section. MapProxy will merge multiple sources from left (bottom) to right (top).

WMS and Mapserver sources also support tagged names (``wms:lyr1,lyr2``). See :ref:`tagged_source_names`.

``tile_sources``
""""""""""""""""

.. versionadded:: 1.8.2

A list of caches for this layer. This list overrides ``sources`` for WMTS and TMS. ``tile_sources`` are not merged like ``sources``, instead all the caches are added as additional tile (matrix) sets.


``min_res``, ``max_res`` or ``min_scale``, ``max_scale``
""""""""""""""""""""""""""""""""""""""""""""""""""""""""
.. NOTE paragraph also in sources/wms section

Limit the layer to the given min and max resolution or scale. MapProxy will return a blank image for requests outside of these boundaries (``min_res`` is inclusive, ``max_res`` exclusive). You can use either the resolution or the scale values, missing values will be interpreted as `unlimited`. Resolutions should be in meters per pixel.

The values will also apear in the capabilities documents (i.e. WMS ScaleHint and Min/MaxScaleDenominator).

Pleas read :ref:`scale vs. resolution <scale_resolution>` for some notes on `scale`.

``legendurl``
"""""""""""""

Configure a URL to an image that should be returned as the legend for this layer. Local URLs (``file://``) are also supported. MapProxy ignores the legends from the sources of this layer if you configure a ``legendurl`` here.

.. _layer_metadata:

``md``
""""""

.. versionadded:: 1.4.0

Add additional metadata for this layer. This metadata appears in the WMS 1.3.0 capabilities documents. Refer to the OGC 1.3.0 specification for a description of each option.

See also :doc:`inspire` for configuring additional INSPIRE metadata.

Here is an example layer with extended layer capabilities::

  layers:
    - name: md_layer
      title: WMS layer with extended capabilities
      sources: [wms_source]
      md:
        abstract: Some abstract
        keyword_list:
          - vocabulary: Name of the vocabulary
            keywords:   [keyword1, keyword2]
          - vocabulary: Name of another vocabulary
            keywords:   [keyword1, keyword2]
          - keywords:   ["keywords without vocabulary"]
        attribution:
          title: My attribution title
          url:   http://example.org/
        logo:
           url:    http://example.org/logo.jpg
           width:  100
           height: 100
           format: image/jpeg
        identifier:
          - url:    http://example.org/
            name:   HKU1234
            value:  Some value
        metadata:
          - url:    http://example.org/metadata2.xml
            type:   INSPIRE
            format: application/xml
          - url:    http://example.org/metadata2.xml
            type:   ISO19115:2003
            format: application/xml
        data:
          - url:    http://example.org/datasets/test.shp
            format: application/octet-stream
          - url:    http://example.org/datasets/test.gml
            format: text/xml; subtype=gml/3.2.1
        feature_list:
          - url:    http://example.org/datasets/test.pdf
            format: application/pdf

``dimensions``
""""""""""""""

.. versionadded:: 1.6.0

.. note:: Dimensions are only supported for uncached WMTS services for now. See :ref:`wmts_dimensions` for a working use-case.

Configure the dimensions that this layer supports. Dimensions should be a dictionary with one entry for each dimension.
Each dimension is another dictionary with a list of ``values`` and an optional ``default`` value. When the ``default`` value is omitted, the last value will be used.

::

  layers:
    - name: dimension_layer
      title: layer with dimensions
      sources: [cache]
      dimensions:
        time:
          values:
            - "2012-11-12T00:00:00"
            - "2012-11-13T00:00:00"
            - "2012-11-14T00:00:00"
            - "2012-11-15T00:00:00"
          default: "2012-11-15T00:00:00"
        elevation:
          values:
            - 0
            - 1000
            - 3000


.. ``attribution``
.. """"""""""""""""
..
.. Overwrite the system-wide attribution line for this layer.
..
.. ``inverse``
..   If this option is set to ``true``, the colors of the attribution will be inverted. Use this if the normal attribution is hard to on this layer (i.e. on aerial imagery).


.. #################################################################################
.. index:: caches

.. _caches:

caches
------

Here you can configure which sources should be cached.
Available options are:

``sources``
"""""""""""

A list of data sources for this cache. You can use sources defined in the ``sources`` and ``caches`` section. This parameter is `required`. MapProxy will merge multiple sources from left (bottom) to right (top) before they are stored on disk.

::

    caches:
      my_cache:
        sources: [background_wms, overlay_wms]
        ...

WMS and Mapserver sources also support tagged names (``wms:lyr1,lyr2``). See :ref:`tagged_source_names`.

Band merging
^^^^^^^^^^^^
.. versionadded:: 1.9.0

You can also define a list of sources for each color band. The target color bands are specified as ``r``, ``g``, ``b`` for RGB images, optionally with ``a`` for the alpha band. You can also use ``l`` (luminance) to create tiles with a single color band (e.g. grayscale images).

You need to define the ``source`` and the ``band`` index for each source band. The indices of the source bands are numeric and start from 0.


The following example creates a colored infra-red (false-color) image by using near infra-red for red, red (band 0) for green, and green (band 1) for blue::

  caches:
    cir_cache:
       sources:
           r: [{source: nir_cache, band: 0}]
           g: [{source: dop_cache, band: 0}]
           b: [{source: dop_cache, band: 1}]


You can define multiple sources for each target band. The values are summed and clipped at 255. An optional ``factor`` allows you to reduce the values. You can use this to mix multiple bands into a single grayscale image::

  caches:
   grayscale_cache:
       sources:
           l: [
               {source: dop_cache, band: 0, factor: 0.21},
               {source: dop_cache, band: 1, factor: 0.72},
               {source: dop_cache, band: 2, factor: 0.07},
           ]



Cache sources
^^^^^^^^^^^^^
.. versionadded:: 1.5.0

You can also use other caches as a source. MapProxy loads tiles directly from that cache if the grid of the target cache is identical or *compatible* with the grid of the source cache. You have a compatible grid when all tiles in the cache grid are also available in source grid, even if the tile coordinates (X/Y/Z) are different.

When the grids are not compatible, e.g. when they use different projections, then MapProxy will access the source cache as if it is a WMS source and it will use meta-requests and do image reprojection as necessary.

See :ref:`using_existing_caches` for more information.


.. _mixed_image_format:

``format``
""""""""""

The internal image format for the cache. Available options are ``image/png``, ``image/jpeg`` etc. and ``mixed``.
The default is ``image/png``.

.. versionadded:: 1.5.0

With the ``mixed`` format, MapProxy stores tiles as either PNG or JPEG, depending on the transparency of each tile.
Images with transparency will be stored as PNG, fully opaque images as JPEG.
You need to set the ``request_format`` to ``image/png`` when using ``mixed``-mode::

    caches:
      mixed_mode_cache:
        format: mixed
        request_format: image/png
        ...


``request_format``
""""""""""""""""""

MapProxy will try to use this format to request new tiles, if it is not set ``format`` is used. This option has no effect if the source does not support that format or the format of the source is set explicitly (see ``suported_format`` or ``format`` for sources).


.. _link_single_color_images:

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

By default MapProxy requests all uncached meta-tiles that intersect the requested bbox. With a typical configuration it is not uncommon that a requests will trigger four requests each larger than 2000x2000 pixel. With the ``minimize_meta_requests`` option enabled, each request will trigger only one request to the source. That request will be aligned to the next tile boundaries and the tiles will be cached.

.. index:: watermark

``watermark``
"""""""""""""

Add a watermark right into the cached tiles. The watermark is thus also present in TMS or KML requests.

``text``
    The watermark text. Should be short.

``opacity``
    The opacity of the watermark (from 0 transparent to 255 full opaque).
    Use a value between 30 and 100 for unobtrusive watermarks.

``font_size``
  Font size of the watermark text.

``color``
  Color of the watermark text. Default is grey which works good for vector images. Can be either a list of color values (``[255, 255, 255]``) or a hex string (``#ffffff``).

``spacing``
  Configure the spacing between repeated watermarks. By default the watermark will be placed on
  every tile, with ``wide`` the watermark will be placed on every second tile.


``grids``
"""""""""

You can configure one or more grids for each cache. MapProxy will create one cache for each grid.
::

    grids: ['my_utm_grid', 'GLOBAL_MERCATOR']


MapProxy supports on-the-fly transformation of requests with different SRSs. So
it is not required to add an extra cache for each supported SRS. For best performance
only the SRS most requests are in should be used.

There is some special handling for layers that need geographical and projected coordinate
systems. For example, if you set one grid with ``EPSG:4326`` and one with ``EPSG:3857``
then all requests for projected SRS will access the ``EPSG:3857`` cache and
requests for geographical SRS will use ``EPSG:4326``.


``meta_size`` and ``meta_buffer``
"""""""""""""""""""""""""""""""""

Change the ``meta_size`` and ``meta_buffer`` of this cache. See :ref:`global cache options <meta_size>` for more details.

``bulk_meta_tiles``
"""""""""""""""""""

Enables meta-tile handling for tiled sources. See :ref:`global cache options <meta_size>` for more details.

``image``
"""""""""

:ref:`See below <image_options>` for all image options.


``use_direct_from_level`` and ``use_direct_from_res``
"""""""""""""""""""""""""""""""""""""""""""""""""""""

You can limit until which resolution MapProxy should cache data with these two options.
Requests below the configured resolution or level will be passed to the underlying source and the results will not be stored. The resolution of ``use_direct_from_res`` should use the units of the first configured grid of this cache. This takes only effect when used in WMS services.

``disable_storage``
""""""""""""""""""""

If set to ``true``, MapProxy will not store any tiles for this cache. MapProxy will re-request all required tiles for each incoming request,
even if the there are matching tiles in the cache. See :ref:`seed_only <wms_seed_only>` if you need an *offline* mode.

.. note:: Be careful when using a cache with disabled storage in tile services when the cache uses WMS sources with metatiling.

``cache_dir``
"""""""""""""

Directory where MapProxy should store tiles for this cache. Uses the value of ``globals.cache.base_dir`` by default. MapProxy will store each cache in a subdirectory named after the cache and the grid SRS (e.g. ``cachename_EPSG1234``).
See :ref:`directory option<cache_file_directory>` on how configure a complete path.

``cache``
"""""""""

.. versionadded:: 1.2.0

Configure the type of the background tile cache. You configure the type with the ``type`` option.  The default type is ``file`` and you can leave out the ``cache`` option if you want to use the file cache. Read :doc:`caches` for a detailed list of all available cache backends.


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
    cache:
      type: file
      directory_layout: tms


.. #################################################################################
.. index:: grids

.. _grids:

grids
-----

Here you can define the tile grids that MapProxy uses for the internal caching.
There are multiple options to define the grid, but beware, not all are required at the same time and some combinations will result in ambiguous results.

There are three pre-defined grids all with global coverage:

- ``GLOBAL_GEODETIC``: EPSG:4326, origin south-west, compatible with OpenLayers map in EPSG:4326
- ``GLOBAL_MERCATOR``: EPSG:900913, origin south-west, compatible with OpenLayers map in EPSG:900913
- ``GLOBAL_WEBMERCATOR``: similar to ``GLOBAL_MERCATOR`` but uses EPSG:3857 and origin north-west, compatible with OpenStreetMap/etc.

.. versionadded:: 1.6.0
    ``GLOBAL_WEBMERCATOR``

``name``
""""""""

Overwrite the name of the grid used in WMTS URLs. The name is also used in TMS and KML URLs when the ``use_grid_names`` option of the services is set to ``true``.

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

MapProxy always expects your BBOX coordinates order to be east, south, west, north, regardless of your SRS :ref:`axis order <axis_order>`.

::

  bbox: [0, 40, 15, 55]
    or
  bbox: "0,40,15,55"

``bbox_srs``
""""""""""""

The SRS of the grid bbox. See above.

.. index:: origin

.. _grid_origin:

``origin``
""""""""""

.. versionadded:: 1.3.0

The default origin (x=0, y=0) of the tile grid is the lower left corner, similar to TMS. WMTS defines the tile origin in the upper left corner. MapProxy can translate between services and caches with different tile origins, but there are some limitations for grids with custom BBOX and resolutions that are not of factor 2. You can only use one service in these cases and need to use the matching ``origin`` for that service.

The following values are supported:

``ll`` or ``sw``:
  If the x=0, y=0 tile is in the lower-left/south-west corner of the tile grid. This is the default.

``ul`` or ``nw``:
  If the x=0, y=0 tile is in the upper-left/north-west corner of the tile grid.


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

.. _image_resampling_method:

``resampling_method``
  The resampling method used when results need to be rescaled or transformed.
  You can use one of nearest, bilinear or bicubic. Nearest is the fastest and
  bicubic the slowest. The results will look best with bilinear or bicubic.
  Bicubic enhances the contrast at edges and should be used for vector images.

  With `bilinear` you should get about 2/3 of the `nearest` performance, with
  `bicubic` 1/3.

  See the examples below:

  ``nearest``:

    .. image:: imgs/nearest.png

  ``bilinear``:

    .. image:: imgs/bilinear.png

  ``bicubic``:

    .. image:: imgs/bicubic.png

.. _image_paletted:

``paletted``
  Enable paletted (8bit) PNG images. It defaults to ``true`` for backwards compatibility. You should set this to ``false`` if you need 24bit PNG files. You can enable 8bit PNGs for single caches with a custom format (``colors: 256``).

``formats``
  Modify existing or define new image formats. :ref:`See below <image_options>` for all image format options.


.. _globals_cache:

``cache``
"""""""""

The following options define how tiles are created and stored. Most options can be set individually for each cache as well.

.. versionadded:: 1.6.0 ``tile_lock_dir``
.. versionadded:: 1.10.0 ``bulk_meta_tiles``


.. _meta_size:

``meta_size``
  MapProxy does not make a single request for every tile it needs, but it will request a large meta-tile that consist of multiple tiles. ``meta_size`` defines how large a meta-tile is. A ``meta_size`` of ``[4, 4]`` will request 16 tiles in one pass. With a tile size of 256x256 this will result in 1024x1024 requests to the source. Tiled sources are still requested tile by tile, but you can configure MapProxy to load multiple tiles in bulk with `bulk_meta_tiles`.


.. _bulk_meta_tiles:

``bulk_meta_tiles``
  Enables meta-tile handling for caches with tile sources.
  If set to `true`, MapProxy will request neighboring tiles from the source even if only one tile is requested from the cache. ``meta_size`` defines how many tiles should be requested in one step and ``concurrent_tile_creators`` defines how many requests are made in parallel. This option improves the performance for caches that allow to store multiple tiles with one request, like SQLite/MBTiles but not the ``file`` cache.


``meta_buffer``
  MapProxy will increase the size of each meta-tile request by this number of
  pixels in each direction. This can solve cases where labels are cut-off at
  the edge of tiles.

``base_dir``
  The base directory where all cached tiles will be stored. The path can
  either be absolute (e.g. ``/var/mapproxy/cache``) or relative to the
  mapproxy.yaml file. Defaults to ``./cache_data``.

.. _lock_dir:

``lock_dir``
  MapProxy uses locking to limit multiple request to the same service. See ``concurrent_requests``.
  This option defines where the temporary lock files will be stored. The path
  can either be absolute (e.g. ``/tmp/lock/mapproxy``) or relative to the
  mapproxy.yaml file. Defaults to ``./cache_data/tile_locks``.

.. _tile_lock_dir:

``tile_lock_dir``
  MapProxy uses locking to prevent that the same tile gets created multiple times.
  This option defines where the temporary lock files will be stored. The path
  can either be absolute (e.g. ``/tmp/lock/mapproxy``) or relative to the
  mapproxy.yaml file. Defaults to ``./cache_data/dir_of_the_cache/tile_locks``.


``concurrent_tile_creators``
  This limits the number of parallel requests MapProxy will make to a source. This limit is per request for this cache and not for all MapProxy requests. To limit the requests MapProxy makes to a single server use the ``concurrent_requests`` option.

  Example: A request in an uncached region requires MapProxy to fetch four meta-tiles. A ``concurrent_tile_creators`` value of two allows MapProxy to make two requests to the source WMS request in parallel. The splitting of the meta-tile and the encoding of the new tiles will happen in parallel to.


``link_single_color_images``
  Enables the ``link_single_color_images`` option for all caches if set to ``true``. See :ref:`link_single_color_images`.

.. _max_tile_limit:

``max_tile_limit``
  Maximum number of tiles MapProxy will merge together for a WMS request. This limit is for each layer and defaults to 500 tiles.


``srs``
"""""""

``proj_data_dir``
  MapProxy uses Proj4 for all coordinate transformations. If you need custom projections
  or need to tweak existing definitions (e.g. add towgs parameter set) you can point
  MapProxy to your own set of proj4 init files. The path should contain an ``epsg`` file
  with the EPSG definitions.

  The configured path can be absolute or relative to the mapproxy.yaml.

.. _axis_order:

``axis_order_ne`` and ``axis_order_en``
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

HTTP related options.

Secure HTTPS Connections (HTTPS)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. note:: You need Python 2.6 or the `SSL module <http://pypi.python.org/pypi/ssl>`_ for this feature.

MapProxy supports access to HTTPS servers. Just use ``https`` instead of ``http`` when
defining the URL of a source. MapProxy needs a file that contains the root and CA
certificates. If the server certificate is signed by a "standard" root certificate (i.e. your browser does not warn you), then you can use a cert file that is distributed with your system. On Debian based systems you can use ``/etc/ssl/certs/ca-certificates.crt``.
See the `Python SSL documentation <http://docs.python.org/dev/library/ssl.html#ssl-certificates>`_ for more information about the format.

::

  http:
    ssl_ca_certs: /etc/ssl/certs/ca-certificates.crt

If you want to use SSL but do not need certificate verification, then you can disable it with the ``ssl_no_cert_checks`` option. You can also disable this check on a source level, see :ref:`WMS source options <wms_source_ssl_no_cert_checks>`.
::

  http:
    ssl_no_cert_checks: True

``client_timeout``
^^^^^^^^^^^^^^^^^^

This defines how long MapProxy should wait for data from source servers. Increase this value if your source servers are slower.

``method``
^^^^^^^^^^

Configure which HTTP method should be used for HTTP requests. By default (`AUTO`) MapProxy will use GET for most requests, except for requests with a long query string (e.g. WMS requests with `sld_body`) where POST is used instead. You can disable this behavior with either `GET` or `POST`.

::

  http:
    method: GET

``headers``
^^^^^^^^^^^

Add additional HTTP headers to all requests to your sources.
::

  http:
    headers:
      My-Header: header value


``access_control_allow_origin``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. versionadded:: 1.8.0

Sets the ``Access-control-allow-origin`` header to HTTP responses for `Cross-origin resource sharing <http://en.wikipedia.org/wiki/Cross-origin_resource_sharing>`_. This header is required for WebGL or Canvas web clients. Defaults to `*`. Leave empty to disable the header. This option is only available in `globals`.


``tiles``
""""""""""

Configuration options for the TMS/Tile service.

``expires_hours``
  The number of hours a Tile is valid. TMS clients like web browsers will
  cache the tile for this time. Clients will try to refresh the tiles after
  that time. MapProxy supports the ETag and Last-Modified headers and will
  respond with the appropriate HTTP `'304 Not modified'` response if the tile
  was not changed.


``mapserver``
"""""""""""""

Options for the :ref:`Mapserver source<mapserver_label>`.

``binary``
^^^^^^^^^^

The complete path to the ``mapserv`` executable. Required if you use the ``mapserver`` source.

``working_dir``
^^^^^^^^^^^^^^^

Path where the Mapserver should be executed from. It should be the directory where any relative paths in your mapfile are based on. Defaults to the directory of ``binary``.


.. _image_options:

Image Format Options
--------------------

.. versionadded:: 1.1.0

There are a few options that affect how MapProxy encodes and transforms images. You can set these options in the ``globals`` section or individually for each source or cache.

Options
"""""""

Available options are:

``format``
  The mime-type of this image format. The format defaults to the name of the image configuration.

``mode``
  One of ``RGB`` for 24bit images, ``RGBA`` 32bit images with alpha, ``P`` for paletted images or ``I`` for integer images.

``colors``
  The number of colors to reduce the image before encoding. Use ``0`` to disable color reduction (quantizing) for this format and ``256`` for paletted images. See also :ref:`globals.image.paletted <image_paletted>`.

``transparent``
  ``true`` if the image should have an alpha channel.

``resampling_method``
  The resampling method used for scaling or reprojection. One of ``nearest``, ``bilinear`` or ``bicubic``.

``encoding_options``
  Options that modify the way MapProxy encodes (saves) images. These options are format dependent. See below.

``opacity``
  Configures the opacity of a layer or cache. This value is used when the source or cache is placed on other layers and it can be used to overlay non-transparent images. It does not alter the image itself, and only effects when multiple layers are merged to one image. The value should be between 0.0 (full transparent) and 1.0 (opaque, i.e. the layers below will not be rendered).


``encoding_options``
^^^^^^^^^^^^^^^^^^^^

The following encoding options are available:

.. _jpeg_quality:

``jpeg_quality``
  An integer value from 0 to 100 that defines the image quality of JPEG images. Larger values result in slower performance, larger file sizes but better image quality. You should try values between 75 and 90 for good compromise between performance and quality.

``quantizer``
  The algorithm used to quantize (reduce) the image colors. Quantizing is used for GIF and paletted PNG images. Available quantizers are ``mediancut`` and ``fastoctree``. ``fastoctree`` is much faster and also supports 8bit PNG with full alpha support, but the image quality can be better with ``mediancut`` in some cases.
  The quantizing is done by the Python Image Library (PIL). ``fastoctree`` is a `new quantizer <http://mapproxy.org/blog/improving-the-performance-for-png-requests/>`_ that is only available in Pillow >=2.0. See :ref:`installation of PIL<dependencies_pil>`.

Global
""""""

You can configure image formats globally with the ``image.formats`` option. Each format has a name and one or more options from the list above. You can choose any name, but you need to specify a ``format`` if the name is not a valid mime-type (e.g. ``myformat`` instead of ``image/png``).

Here is an example that defines a custom format::

  globals:
    image:
      formats:
        my_format:
          format: image/png
          mode: P
          transparent: true


You can also modify existing image formats::

  globals:
    image:
      formats:
        image/png:
          encoding_options:
            quantizer: fastoctree


MapProxy will use your image formats when you are using the format name as the ``format`` of any source or cache.

For example::

  caches:
    mycache:
      format: my_format
      sources: [source1, source2]
      grids: [my_grid]


Local
"""""

You can change all options individually for each cache or source. You can do this by choosing a base format and changing some options::

  caches:
    mycache:
      format: image/jpeg
      image:
        encoding_options:
          jpeg_quality: 80
      sources: [source1, source2]
      grids: [my_grid]

You can also configure the format from scratch::

  caches:
    mycache:
      image:
        format: image/jpeg
        resampling_method: nearest
      sources: [source1, source2]
      grids: [my_grid]


Notes
-----

.. _scale_resolution:

Scale vs. resolution
""""""""""""""""""""

Scale is the ratio of a distance on a map and the corresponding distance on the ground. This implies that the map distance and the ground distance are measured in the same unit. For MapProxy a `map` is just a collection of pixels and the pixels do not have any size/dimension. They do correspond to a ground size but the size on the `map` is depended of the physical output format. MapProxy can thus only work with resolutions (pixel per ground unit) and not scales.

This applies to all servers and the OGC WMS standard as well. Some neglect this fact and assume a fixed pixel dimension (like 72dpi), the OCG WMS 1.3.0 standard uses a pixel size of 0.28 mm/px (around 91dpi). But you need to understand that a `scale` will differ if you print a map (200, 300 or more dpi) or if you show it on a computer display (typical 90-120 dpi, but there are mobile devices with more than 300 dpi).

You can convert between scales and resolutions with the :ref:`mapproxy-util scales tool<mapproxy_util_scales>`.


MapProxy will use the OCG value (0.28mm/px) if it's necessary to use a scale value (e.g. MinScaleDenominator in WMS 1.3.0 capabilities), but you should always use resolutions within MapProxy.


WMS ScaleHint
^^^^^^^^^^^^^

The WMS ScaleHint is a bit misleading. The parameter is not a scale but the diagonal pixel resolution. It also defines the ``min`` as the minimum value not the minimum resolution (e.g. 10m/px is a lower resolution than 5m/px, but 5m/px is the minimum value). MapProxy always uses the term resolutions as the side length in ground units per pixel and minimum resolution is always the higher number (100m/px < 10m/px). Keep that in mind when you use these values.
