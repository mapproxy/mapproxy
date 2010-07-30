Sources
#######

MapProxy supports the following sources:

- :ref:`wms_label`
- :ref:`tiles_label`
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


``wms_opts``
^^^^^^^^^^^^

This option affects what request MapProxy sends to the source WMS server.

``version``
  The WMS version number used for requests (supported: 1.0.0, 1.1.1, 1.3.0). Defaults to 1.1.1.
  
``featureinfo``
  If this is set to ``true``, MapProxy will mark the layer as queryable and incoming `GetFeatureInfo` requests will be forwarded to the source server.


.. _supported_srs-label:

``supported_srs``
^^^^^^^^^^^^^^^^^

A list with SRSs that the WMS source supports. MapProxy will only query the source in these SRSs. It will reproject data if it needs to get data from this layer in any other SRS.

You don't need to configure this if you only use this WMS as a cache source and the WMS supports all SRS of the cache.
    
If MapProxy needs to reproject and the source has multiple ``supported_srs``, then it will use the fist projected SRS for requests in projected SRS, or the fist geographic SRS for requests in geographic SRS. E.g when `supported_srs` is ``['EPSG:4326', 'EPSG:31467']`` caches with EPSG:900913 will use EPSG:32467.
    
  ..  .. note:: For the configuration of SRS for MapProxy see `srs_configuration`_.

``supported_format``
^^^^^^^^^^^^^^^^^^^^

Use this option to specify which image formats you source WMS supports. MapProxy only requests images in one of these formats, and will convert any image if it needs another format. If you do not supply this options, MapProxy assumes that the source supports all formats.


``concurrent_requests``
^^^^^^^^^^^^^^^^^^^^^^^
This limits the number of parallel requests MapProxy will issue to the source server.
It even works across multiple WMS sources as long as all have the same ``concurrent_requests`` and ``req.url`` parameter. 

.. _wms_source-ssl_no_cert_check:

``http.ssl_no_cert_check``
^^^^^^^^^^^^^^^^^^^^^^^^^^
MapProxy checks the SSL server certificates for any ``req.url`` that use HTTPS. You need to supply a file (see) that includes that certificate, otherwise MapProxy will fail to establish the connection. You can set the ``http.ssl_no_cert_check`` options to ``true`` to disable this verification.

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
    req:
      url: http://localhost:8080/service?mycustomparam=foo
      layers: roads
      another_param: bar
      transparent: true


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

Additionally you can specify the origin of the tile grid with the ``origin`` option.
Supported values are ``sw`` for south-west (lower-left) origin or ``nw`` for north-west
(upper-left) origin. ``sw`` is the default.

Example configuration
^^^^^^^^^^^^^^^^^^^^^
::
  
  my_tile_source:
    type: tile
    url: http://localhost:8080/tile?x=%(x)s&y=%(y)s&z=%(z)s&format=%(format)s
    origin: nw


.. _debug_label:

Debug
"""""

Adds information like resolution and BBOX to the response image.
This is useful to determine a fixed set of resolutions for the ``res``-parameter. It takes no options.

Example::

  debug_source:
    type: debug

