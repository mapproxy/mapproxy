.. _sources:

Sources
#######

MapProxy supports the following sources:

- :ref:`wms_label`
- :ref:`arcgis_label`
- :ref:`tiles_label`
- :ref:`mapserver_label`
- :ref:`mapnik_label`
- :ref:`debug_label`

You need to choose a unique name for each configured source. This name will be used to reference the source in the ``caches`` and ``layers`` configuration.

The sources section looks like::

  sources:
    mysource1:
      type: xxx
      type_dependend_option1: a
      type_dependend_option2: b
    mysource2:
      type: yyy
      type_dependend_option3: c

See below for a detailed description of each service.

.. _wms_label:

WMS
"""

Use the type ``wms`` to for WMS servers.

``req``
^^^^^^^

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
    layers: roads
    styles: simple
    map: /path/to/mapfile


You can also configure ``sld`` or ``sld_body`` parameters, in this case you can omit ``layers``. ``sld`` can also point to a ``file://``-URL. MapProxy will read this file and use the content as the ``sld_body``. See :ref:`sources with SLD <sld_example>` for more information.

You can omit layers if you use :ref:`tagged_source_names`.

``wms_opts``
^^^^^^^^^^^^

This option affects what request MapProxy sends to the source WMS server.

``version``
  The WMS version number used for requests (supported: 1.0.0, 1.1.0, 1.1.1, 1.3.0). Defaults to 1.1.1.

``legendgraphic``
  If this is set to ``true``, MapProxy will request legend graphics from this source. Each MapProxy WMS layer that contains one or more sources with legend graphics will then have a LegendURL.

``legendurl``
  Configure a URL to an image that should be returned as the legend for this source. Local URLs (``file://``) are also supported.

``map``
  If this is set to ``false``, MapProxy will not request images from this source. You can use this option in combination with ``featureinfo: true`` to create a source that is only used for feature info requests.

``featureinfo``
  If this is set to ``true``, MapProxy will mark the layer as queryable and incoming `GetFeatureInfo` requests will be forwarded to the source server.

``featureinfo_xslt``
  Path to an XSLT script that should be used to transform incoming feature information.

``featureinfo_format``
  The ``INFO_FORMAT`` for FeatureInfo requests. By default MapProxy will use the same format as requested by the client.

  ``featureinfo_xslt`` and ``featureinfo_format``


See :ref:`FeatureInformation for more information <fi_xslt>`.

``coverage``
^^^^^^^^^^^^

Define the covered area of the source. The source will only be requested if there is an intersection between the requested data and the coverage. See :doc:`coverages <coverages>` for more information about the configuration. The intersection is calculated for meta-tiles and not the actual client request, so you should expect more visible data at the coverage boundaries.

.. _wms_seed_only:

``seed_only``
^^^^^^^^^^^^^

Disable this source in regular mode. If set to ``true``, this source will always return a blank/transparent image. The source will only be requested during the seeding process. You can use this option to run MapProxy in an offline mode.

.. _source_minmax_res:

``min_res``, ``max_res`` or ``min_scale``, ``max_scale``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. NOTE paragraph also in configuration/layers section

Limit the source to the given min and max resolution or scale. MapProxy will return a blank image for requests outside of these boundaries (``min_res`` is inclusive, ``max_res`` exclusive). You can use either the resolution or the scale values, missing values will be interpreted as `unlimited`. Resolutions should be in meters per pixel.

The values will also apear in the capabilities documents (i.e. WMS ScaleHint and Min/MaxScaleDenominator). The boundaries will be regarded for each source, but the values in the capabilities might differ if you combine multiple sources or if the MapProxy layer already has a ``min/max_res`` configuration.

Please read :ref:`scale vs. resolution <scale_resolution>` for some notes on `scale`.

.. _supported_srs:

``supported_srs``
^^^^^^^^^^^^^^^^^

A list with SRSs that the WMS source supports. MapProxy will only query the source in these SRSs. It will reproject data if it needs to get data from this layer in any other SRS.

You don't need to configure this if you only use this WMS as a cache source and the WMS supports all SRS of the cache.

If MapProxy needs to reproject and the source has multiple ``supported_srs``, then it will use the first projected SRS for requests in a projected SRS, or the first geographic SRS for requests in a geographic SRS. E.g when `supported_srs` is ``['EPSG:4326', 'EPSG:31467']`` caches with EPSG:3857 (projected, meter) will use EPSG:31467 (projected, meter) and not EPSG:4326 (geographic, lat/long).

  ..  .. note:: For the configuration of SRS for MapProxy see `srs_configuration`_.

``forward_req_params``
^^^^^^^^^^^^^^^^^^^^^^

.. versionadded:: 1.5.0

A list with request parameters that will be forwarded to the source server (if available in the original request). A typical use case of this feature would be to forward the `TIME` parameter when working with a WMS-T server.

This feature only works with :ref:`uncached sources <direct_source>`.

``supported_formats``
^^^^^^^^^^^^^^^^^^^^^

Use this option to specify which image formats your source WMS supports. MapProxy only requests images in one of these formats, and will convert any image if it needs another format. If you do not supply this options, MapProxy assumes that the source supports all formats.

``image``
^^^^^^^^^

See :ref:`image_options` for other options.

``transparent_color``

  Specify a color that should be converted to full transparency. Can be either a list of color values (``[255, 255, 255]``) or a hex string (``#ffffff``).

``transparent_color_tolerance``

  Tolerance for the ``transparent_color`` substitution. The value defines the tolerance in each direction. E.g. a tolerance of 5 and a color value of 100 will convert colors in the range of 95 to 105.

  ::

    image:
      transparent_color: '#ffffff'
      transparent_color_tolerance: 20

.. _wms_source_concurrent_requests_label:

``concurrent_requests``
^^^^^^^^^^^^^^^^^^^^^^^
This limits the number of parallel requests MapProxy will issue to the source server.
It even works across multiple WMS sources as long as all have the same ``concurrent_requests`` value and all ``req.url`` parameters point to the same host. Defaults to 0, which means no limitation.


``http``
^^^^^^^^

You can configure the following HTTP related options for this source:

- ``method``
- ``headers``
- ``client_timeout``
- ``ssl_ca_certs``
- ``ssl_no_cert_checks`` (see below)

See :ref:`HTTP Options <http_ssl>` for detailed documentation.

.. _wms_source_ssl_no_cert_checks:

``ssl_no_cert_checks``

  MapProxy checks the SSL server certificates for any ``req.url`` that use HTTPS. You need to supply a file (see) that includes that certificate, otherwise MapProxy will fail to establish the connection. You can set the ``http.ssl_no_cert_checks`` options to ``true`` to disable this verification.

.. _tagged_source_names:

Tagged source names
^^^^^^^^^^^^^^^^^^^

.. versionadded:: 1.1.0

MapProxy supports tagged source names for most sources. This allows you to define the layers of a source in the caches or (WMS)-layers configuration.

Instead of referring to a source by the name alone, you can add a list of comma delimited layers: ``sourcename:lyr1,lyr2``. You need to use quotes for tagged source names.

This works for layers and caches::

  layers:
    - name: test
      title: Test Layer
      sources: ['wms1:lyr1,lyr2']

  caches:
    cache1:
      sources: ['wms1:lyrA,lyrB']
      [...]

  sources:
    wms1:
      type: wms
      req:
        url: http://example.org/service?


You can either omit the ``layers`` in the ``req`` parameter, or you can use them to limit the tagged layers. In this case MapProxy will raise an error if you configure ``layers: lyr1,lyr2`` and then try to access ``wms:lyr2,lyr3`` for example.


Example configuration
^^^^^^^^^^^^^^^^^^^^^

Minimal example::

  my_minimal_wmssource:
    type: wms
    req:
      url: http://localhost:8080/service?
      layers: base

Full example::

  my_wmssource:
    type: wms
    wms_opts:
      version: 1.0.0
      featureinfo: True
    supported_srs: ['EPSG:4326', 'EPSG:31467']
    image:
      transparent_color: '#ffffff'
      transparent_color_tolerance: 0
    coverage:
       polygons: GM.txt
       polygons_srs: EPSG:900913
    forward_req_params: ['TIME', 'CUSTOM']
    req:
      url: http://localhost:8080/service?mycustomparam=foo
      layers: roads
      another_param: bar
      transparent: true


.. _arcgis_label:

ArcGIS REST API
"""""""""""""""

.. versionadded: 1.9.0

Use the type ``arcgis`` for ArcGIS MapServer and ImageServer REST server endpoints. This
source is based on :ref:`the WMS source <wms_label>` and most WMS options apply to the
ArcGIS source too.

``req``
^^^^^^^

This describes the ArcGIS source. The only required option is ``url``. You need to set ``transparent`` to ``true`` if you want to use this source as an overlay. You can also add ArcGIS specific parameters to ``req``, for example to set the `interpolation method for ImageServers <http://resources.arcgis.com/en/help/rest/apiref/exportimage.html>`_.


``opts``
^^^^^^^^

.. versionadded: 1.10.0

This option affects what request MapProxy sends to the source ArcGIS server.

``featureinfo``
  If this is set to ``true``, MapProxy will mark the layer as queryable and incoming `GetFeatureInfo` requests will be forwarded as ``identify`` requests to the source server. ArcGIS REST server support only HTML and JSON format. You need to enable support for JSON :ref:`wms_featureinfo_types`.

``featureinfo_return_geometries``
  Whether the source should include the feature geometries.

``featureinfo_tolerance``
  Tolerance in pixel within the ArcGIS server should identify features.

Example configuration
^^^^^^^^^^^^^^^^^^^^^

MapServer example::

  my_minimal_arcgissource:
    type: arcgis
    req:
      layers: show: 0,1
      url: http://example.org/ArcGIS/rest/services/Imagery/MapService
      transparent: true

ImageServer example::

  my_arcgissource:
    type: arcgis
    coverage:
       polygons: GM.txt
       srs: EPSG:3857
    req:
      url: http://example.org/ArcGIS/rest/services/World/MODIS/ImageServer
      interpolation: RSP_CubicConvolution
      bandIds: 2,0,1


.. _tiles_label:

Tiles
"""""

Use the type ``tile`` to request data from from existing tile servers like TileCache and GeoWebCache. You can also use this source cascade MapProxy installations.

``url``
^^^^^^^

This source takes a ``url`` option that contains a URL template. The template format is ``%(key_name)s``. MapProxy supports the following named variables in the URL:

``x``, ``y``, ``z``
  The tile coordinate.
``format``
  The format of the tile.
``quadkey``
  Quadkey for the tile as described in http://msdn.microsoft.com/en-us/library/bb259689.aspx
``tc_path``
  TileCache path like ``09/000/000/264/000/000/345``. Note that it does not contain any format
  extension.
``tms_path``
  TMS path like ``5/12/9``. Note that it does not contain the version, the layername or the format extension.
``arcgiscache_path``
  ArcGIS cache path like ``L05/R00000123/C00000abc``. Note that it does not contain any format
  extension.
``bbox``
  Bounding box of the tile. For WMS-C servers that expect a fixed parameter order.

.. versionadded:: 1.1.0
  ``arcgiscache_path`` and ``bbox`` parameter.


``origin``
^^^^^^^^^^

.. deprecated:: 1.3.0
  Use grid with the ``origin`` option.

The origin of the tile grid (i.e. the location of the 0,0 tile). Supported values are ``sw`` for south-west (lower-left) origin or ``nw`` for north-west (upper-left) origin. ``sw`` is the default.

``grid``
^^^^^^^^
The grid of the tile source. Defaults to ``GLOBAL_MERCATOR``, a grid that is compatible with popular web mapping applications.

``coverage``
^^^^^^^^^^^^
Define the covered area of the source. The source will only be requested if there is an intersection between the incoming request and the coverage. See :doc:`coverages <coverages>` for more information.

``transparent``
^^^^^^^^^^^^^^^

You need to set this to ``true`` if you want to use this source as an overlay.


``http``
^^^^^^^^

You can configure the following HTTP related options for this source:

- ``headers``
- ``client_timeout``
- ``ssl_ca_certs``
- ``ssl_no_cert_checks`` (:ref:`see above <wms_source_ssl_no_cert_checks>`)

See :ref:`HTTP Options <http_ssl>` for detailed documentation.


``seed_only``
^^^^^^^^^^^^^
See :ref:`seed_only <wms_seed_only>`

``min_res``, ``max_res`` or ``min_scale``, ``max_scale``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. versionadded:: 1.5.0

See :ref:`source_minmax_res`.


``on_error``
^^^^^^^^^^^^

.. versionadded:: 1.4.0

You can configure what MapProxy should do when the tile service returns an error. Instead of raising an error, MapProxy can generate a single color tile. You can configure if MapProxy should cache this tile, or if it should use it only to generate a tile or WMS response.

You can configure multiple status codes within the ``on_error`` option. You can also use the catch-all value ``other``. This will not only catch all other HTTP status codes, but also source errors like HTTP timeouts or non-image responses.

Each status code takes the following options:

``response``

  Specify the color of the tile that should be returned in case of this error. Can be either a list of color values (``[255, 255, 255]``, ``[255, 255, 255, 0]``)) or a hex string (``'#ffffff'``, ``'#fa1fbb00'``) with RGBA values, or the string ``transparent``.

``cache``

  Set this to ``True`` if MapProxy should cache the single color tile. Otherwise (``False``) MapProxy will use this generated tile only for this request. This is the default.

You need to enable ``transparent`` for your source, if you use ``on_error`` responses with transparency.

::

  my_tile_source:
    type: tile
    url: http://localhost:8080/tiles/%(tms_path)s.png
    transparent: true
    on_error:
      204:
        response: transparent
        cache: True
      502:
        response: '#ede9e3'
        cache: False
      other:
        response: '#ff0000'
        cache: False


Example configuration
^^^^^^^^^^^^^^^^^^^^^
::

  my_tile_source:
    type: tile
    grid: mygrid
    url: http://localhost:8080/tile?x=%(x)s&y=%(y)s&z=%(z)s&format=%(format)s


.. _mapserver_label:

Mapserver
"""""""""

.. versionadded:: 1.1.0


Use the type ``mapserver`` to directly call the Mapserver CGI executable. This source is based on :ref:`the WMS source <wms_label>` and most options apply to the Mapserver source too.

The only differences are that it does not support the ``http`` option and the ``req.url`` parameter is ignored. The ``req.map`` should point to your Mapserver mapfile.

The mapfile used must have a WMS server enabled, e.g. with ``wms_enable_request`` or ``ows_enable_request`` in the mapfile.

``mapserver``
^^^^^^^^^^^^^

You can also set these options in the :ref:`globals-conf-label` section.

``binary``

  The complete path to the ``mapserv`` executable.

``working_dir``

  Path where the Mapserver should be executed from. It should be the directory where any relative paths in your mapfile are based on.


Example configuration
^^^^^^^^^^^^^^^^^^^^^

::

  my_ms_source:
    type: mapserver
    req:
      layers: base
      map: /path/to/my.map
    mapserver:
      binary: /usr/cgi-bin/mapserv
      working_dir: /path/to


.. _mapnik_label:

Mapnik
""""""

.. versionadded:: 1.1.0
.. versionchanged:: 1.2.0
  New ``layers`` option and support for :ref:`tagged sources <tagged_source_names>`.

Use the type ``mapnik`` to directly call Mapnik without any WMS service. It uses the Mapnik Python API and you need to have a working Mapnik installation that is accessible by the Python installation that runs MapProxy. A call of ``python -c 'import mapnik'`` should return no error.

``mapfile``
^^^^^^^^^^^

The filename of you Mapnik XML mapfile.

``layers``
^^^^^^^^^^

A list of layer names you want to render. MapProxy disables each layer that is not included in this list. It does not reorder the layers and unnamed layers (`Unknown`) are always rendered.

``use_mapnik2``
^^^^^^^^^^^^^^^

.. versionadded:: 1.3.0

Use Mapnik 2 if set to ``true``. This option is now deprecated and only required for Mapnik 2.0.0. Mapnik 2.0.1 and newer are available as ``mapnik`` package.


``transparent``
^^^^^^^^^^^^^^^

Set to ``true`` to render from mapnik sources with background-color="transparent", ``false`` (default) will force a black background color.

``scale_factor``
^^^^^^^^^^^^^^^^

.. versionadded:: 1.8.0

Set the `Mapnik scale_factor <https://github.com/mapnik/mapnik/wiki/Scale-factor>`_ option. Mapnik scales most style options like the width of lines and font sizes by this factor.
See also :ref:`hq_tiles`.

Other options
^^^^^^^^^^^^^

The Mapnik source also supports the ``min_res``/``max_res``/``min_scale``/``max_scale``, ``concurrent_requests``, ``seed_only`` and ``coverage`` options. See :ref:`wms_label`.


Example configuration
^^^^^^^^^^^^^^^^^^^^^

::

  my_mapnik_source:
    type: mapnik
    mapfile: /path/to/mapnik.xml

.. _debug_label:

Debug
"""""

Adds information like resolution and BBOX to the response image.
This is useful to determine a fixed set of resolutions for the ``res``-parameter. It takes no options.

Example::

  debug_source:
    type: debug

