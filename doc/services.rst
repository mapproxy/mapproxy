.. _services:

Services
========


The following services are available:

- :ref:`wms_service_label` and :ref:`wmsc_service_label`
- :ref:`tms_service_label`
- :ref:`kml_service_label`
- :ref:`wmts_service_label`
- :ref:`demo_service_label`

You need to add the service to the ``services`` section of your MapProxy configuration to enable it. Some services take additional options.
::

  services:
    tms:
    kml:
    wms:
      wmsoption1: xxx
      wmsoption2: xxx


.. index:: WMS Service
.. _wms_service_label:

Web Map Service (OGC WMS)
-------------------------

The WMS server is accessible at ``/service``, ``/ows`` and ``/wms``  and it supports the WMS versions 1.0.0, 1.1.1 and 1.3.0.

See :doc:`inspire` for configuring INSPIRE metadata.

The WMS service will use all configured :ref:`layers <layers>`.

The service takes the following additional option.

``attribution``
"""""""""""""""

Adds an attribution (copyright) line to all WMS requests.

``text``
  The text line of the attribution (e.g. some copyright notice, etc).

.. _wms_md:

``md``
""""""
``md`` is for metadata. These fields are used for the WMS ``GetCapabilities`` responses. See the example below for all supported keys.

.. versionadded:: 1.8.1

  ``keyword_list``

.. _wms_srs:

``srs``
"""""""

The ``srs`` option defines which SRS the WMS service supports.::

   srs: ['EPSG:4326', 'CRS:84', 'EPSG:900913']

See :ref:`axis order<axis_order>` for further configuration that might be needed for WMS 1.3.0.

``bbox_srs``
""""""""""""

.. versionadded:: 1.3.0

The ``bbox_srs`` option controls in which SRS the BBOX is advertised in the capabilities document. It should only contain SRS that are configured in the ``srs`` option.

You need to make sure that all layer extents are valid for these SRS. E.g. you can't choose a local SRS like UTM if you're using a global grid without limiting all sources with a ``coverage``.

For example, a config with::

  services:
    wms:
      srs: ['EPSG:4326', 'EPSG:3857', 'EPSG:31467']
      bbox_srs: ['EPSG:4326', 'EPSG:3857', 'EPSG:31467']

will show the bbox in the capabilities in EPSG:4326, EPSG:3857 and EPSG:31467.

.. versionadded:: 1.7.0

    You can also define an explicit bbox for specific SRS. This bbox will overwrite all layer extents for that SRS.

The following example will show the actual bbox of each layer in EPSG:4326 and EPSG:3857, but always the specified bbox for EPSG:31467::

  services:
    wms:
      srs: ['EPSG:4326', 'EPSG:3857', 'EPSG:31467']
      bbox_srs:
        - 'EPSG:4326'
        - 'EPSG:3857'
        - srs: 'EPSG:31467'
          bbox: [2750000, 5000000, 4250000, 6500000]

You can use this to offer global datasets with SRS that are only valid in a local region, like UTM zones.

.. _wms_image_formats:

``image_formats``
"""""""""""""""""

A list of image mime types the server should offer.

.. _wms_featureinfo_types:

``featureinfo_types``
"""""""""""""""""""""

A list of feature info types the server should offer. Available types are ``text``, ``html``, ``xml`` and ``json``. The types are advertised in the capabilities with the correct mime type. Defaults to ``[text, html, xml]``.

``featureinfo_xslt``
""""""""""""""""""""

You can define XSLT scripts to transform outgoing feature information. You can define scripts for different feature info types:

``html``
  Define a script for ``INFO_FORMAT=text/html`` requests.

``xml``
  Define a script for ``INFO_FORMAT=application/vnd.ogc.gml`` and ``INFO_FORMAT=text/xml`` requests.

See :ref:`FeatureInformation for more informaiton <fi_xslt>`.

``strict``
""""""""""

Some WMS clients do not send all required parameters in feature info requests, MapProxy ignores these errors unless you set ``strict`` to ``true``.

``on_source_errors``
""""""""""""""""""""

Configure what MapProxy should do when one or more sources return errors or no response at all (e.g. timeout). The default is ``notify``, which adds a text line in the image response for each erroneous source, but only if a least one source was successful. When ``on_source_errors`` is set to ``raise``, MapProxy will return an OGC service exception in any error case.


``max_output_pixels``
"""""""""""""""""""""

.. versionadded:: 1.3.0

The maximum output size for a WMS requests in pixel. MapProxy returns an WMS exception in XML format for requests that are larger. Defaults to ``[4000, 4000]`` which will limit the maximum output size to 16 million pixels (i.e. 5000x3000 is still allowed).

See also :ref:`globals.cache.max_tile_limit <max_tile_limit>` for the maximum number of tiles MapProxy will merge together for each layer.

``versions``
""""""""""""

.. versionadded:: 1.7.0

A list of WMS version numbers that MapProxy should support. Defaults to ``['1.0.0', '1.1.0', '1.1.1', '1.3.0']``.

Full example
""""""""""""
::

  services:
    wms:
      srs: ['EPSG:4326', 'CRS:83', 'EPSG:900913']
      versions: ['1.1.1']
      image_formats: ['image/png', 'image/jpeg']
      attribution:
        text: "© MyCompany"
      md:
        title: MapProxy WMS Proxy
        abstract: This is the fantastic MapProxy.
        online_resource: http://mapproxy.org/
        contact:
          person: Your Name Here
          position: Technical Director
          organization:
          address: Fakestreet 123
          city: Somewhere
          postcode: 12345
          state: XYZ
          country: Germany
          phone: +49(0)000-000000-0
          fax: +49(0)000-000000-0
          email: you@example.org
        access_constraints: This service is intended for private and evaluation use only.
        fees: 'None'
        keyword_list:
         - vocabulary: GEMET
           keywords:   [Orthoimagery]
         - keywords:   ["View Service", MapProxy]


.. index:: WMS-C Service
.. _wmsc_service_label:


WMS-C
"""""

The MapProxy WMS service also supports the `WMS Tiling Client Recommendation <http://wiki.osgeo.org/wiki/WMS_Tiling_Client_Recommendation>`_ from OSGeo.

If you add ``tiled=true`` to the GetCapabilities request, MapProxy will add metadata about the internal tile structure to the WMS capabilities document. Clients that support WMS-C can use this information to request tiles at the exact tile boundaries. MapProxy can return the tile as-it-is for these requests, the performace is on par with the TMS service.

MapProxy will limit the WMS support when ``tiled=true`` is added to the `GetMap` requests and it will return WMS service exceptions for requests that do not match the exact tile boundaries or if the requested image size or format differs.


.. index:: TMS Service, Tile Service
.. _tms_service_label:

Tiled Map Services (TMS)
------------------------

MapProxy supports the `Tile Map Service Specification`_ from the OSGeo. The TMS is available at ``/tms/1.0.0``.

The TMS service will use all configured :ref:`layers <layers>` that have a name and single cached source. Any layer grouping will be flattened.

Here is an example TMS request: ``/tms/1.0.0/base/EPSG900913/3/1/0.png``. ``png`` is the internal format of the cached tiles. ``base`` is the name of the layer and ``EPSG900913`` is the SRS of the layer. The tiles are also available under the layer name ``base_EPSG900913`` when ``use_grid_names`` is false or unset.

A request to ``/tms/1.0.0`` will return the TMS metadata as XML. ``/tms/1.0.0/layername`` will return information about the bounding box, resolutions and tile size of this specific layer.


``use_grid_names``
""""""""""""""""""

.. versionadded:: 1.5.0

When set to `true`, MapProxy uses the actual name of the grid as the grid identifier instead of the SRS code.
Tiles will then be available under ``/tms/1.0.0/mylayer/mygrid/`` instead of ``/tms/1.0.0/mylayer/EPSG1234/`` or ``/tms/1.0.0/mylayer_EPSG1234/``.

Example
"""""""

::

  services:
    tms:
      use_grid_names: true


.. index:: OpenLayers
.. _open_layers_label:

OpenLayers
""""""""""
When you create a map in OpenLayers with an explicit ``mapExtent``, it will request only a single tile for the first (z=0) level.
TMS begins with two or four tiles by default, depending on the SRS. MapProxy supports a different TMS mode to support this use-case. MapProxy will start with a single-tile level if you request ``/tiles`` instead of ``/tms``.

Alternatively, you can use the OpenLayers TMS option ``zoomOffset`` to compensate the difference. The option is available since OpenLayers 2.10.

There is an example available at :ref:`the configuration-examples section<overlay_tiles_osm_openlayers>`, which shows the use of OpenLayers in combination with an overlay of tiles on top of OpenStreetMap tiles.

.. index:: Google Maps
.. _google_maps_label:

Google Maps
"""""""""""
The TMS standard counts tiles starting from the lower left corner of the tile grid, while Google Maps and compatible services start at the upper left corner. The ``/tiles`` service accepts an ``origin`` parameter that flips the y-axis accordingly. You can set it to either ``sw`` (south-west), the default, or to ``nw`` (north-west), required for Google Maps.

Example::

  http://localhost:8080/tiles/osm_EPSG900913/1/0/1.png?origin=nw

.. versionadded:: 1.5.0
  You can use the ``origin`` option of the TMS service to change the default origin of the tiles service. If you set it to ``nw`` then you can leave the ``?origin=nw`` parameter from the URL. This only works for the tiles service at ``/tiles``, not for the TMS at ``/tms/1.0.0/``.

  Example::

    services:
      tms:
        origin: 'nw'

.. _`Tile Map Service Specification`: http://wiki.osgeo.org/wiki/Tile_Map_Service_Specification


.. index:: KML Service, Super Overlay
.. _kml_service_label:


Keyhole Markup Language (OGC KML)
---------------------------------

MapProxy supports KML version 2.2 for integration into Google Earth. Each layer is available as a Super Overlay – image tiles are loaded on demand when the user zooms to a specific region. The initial KML file is available at ``/kml/layername/EPSG1234/0/0/0.kml``. The tiles are also available under the layer name ``layername_EPSG1234`` when ``use_grid_names`` is false or unset.

.. versionadded:: 1.5.0

  The initial KML is also available at ``/kml/layername_EPSG1234`` and ``/kml/layername/EPSG1234``.

``use_grid_names``
""""""""""""""""""

.. versionadded:: 1.5.0

When set to `true`, MapProxy uses the actual name of the grid as the grid identifier instead of the SRS code.
Tiles will then be available under ``/kml/mylayer/mygrid/`` instead of ``/kml/mylayer/EPSG1234/``.

Example
"""""""

::

  services:
    kml:
      use_grid_names: true


.. index:: WMTS Service, Tile Service
.. _wmts_service_label:

Web Map Tile Services (WMTS)
----------------------------

.. versionadded:: 1.1.0


MapProxy supports the OGC WMTS 1.0.0 specification.

The WMTS service is similar to the TMS service and will use all configured :ref:`layers <layers>` that have a name and single cached source. Any layer grouping will be flattened.

There are some limitations depending on the grid configuration you use. Please refer to :ref:`grid.origin <grid_origin>` for more information.

The metadata (ServiceContact, etc. ) of this service is taken from the WMS configuration. You can add ``md`` to the ``wmts`` configuration to replace the WMS metadata. See :ref:`WMS metadata <wms_md>`.

WMTS defines different access methods and MapProxy supports KVP and RESTful access. Both are enabled by default.


KVP
"""

MapProxy supports ``GetCapabilities`` and ``GetTile`` KVP requests.
The KVP service is available at ``/service`` and ``/ows``.

You can enable or disable the KVP service with the ``kvp`` option. It is enabled by default and you need to enable ``restful`` if you disable this one.

::

  services:
    wmts:
      kvp: false
      restful: true


RESTful
"""""""

.. versionadded:: 1.3.0

MapProxy supports RESTful WMTS requests with custom URL templates.
The RESTful service capabilities are available at ``/wmts/1.0.0/WMTSCapabilities.xml``.

You can enable or disable the RESTful service with the ``restful`` option. It is enabled by default and you need to enable ``kvp`` if you disable this one.

::

  services:
    wmts:
      restful: false
      kvp: true


URL Template
~~~~~~~~~~~~

WMTS RESTful services supports custom tile URLs. You can configure your own URL template with the ``restful_template`` option.

The default template is ``/{Layer}/{TileMatrixSet}/{TileMatrix}/{TileCol}/{TileRow}.{Format}``

The template variables are identical with the WMTS specification. ``TileMatrixSet`` is the grid name, ``TileMatrix`` is the zoom level, ``TileCol`` and ``TileRow`` are the x and y of the tile.


You can access the tile x=3, y=9, z=4 at ``http://example.org//1.0.0/mylayer-mygrid/4-3-9/tile``
with the following configuration::

  services:
    wmts:
      restful: true
      restful_template:
          '/1.0.0/{Layer}-{TileMatrixSet}/{TileMatrix}-{TileCol}-{TileRow}/tile'


.. index:: Demo Service, OpenLayers
.. _demo_service_label:

MapProxy Demo Service
---------------------

MapProxy comes with a demo service that lists all configured WMS and TMS layers. You can test each layer with a simple OpenLayers client.

The service is available at ``/demo/``.

This service takes no further options::

  services:
      demo:
