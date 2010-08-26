Services
========


The following services are available:

- :ref:`wms_service_label` and :ref:`wmsc_service_label`
- :ref:`tms_service_label`
- :ref:`kml_service_label`


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

The WMS server is accessible at ``/service`` and it supports the WMS versions 1.0.0, 1.1.1 and 1.3.0. The service takes the following additional option.

``attribution``
"""""""""""""""

Adds an attribution (copyright) line to all WMS requests.

``text``
  The text line of the attribution (e.g. some copyright notice, etc).

``md``
""""""
``md`` is for metadata. These fields are used for the WMS ``GetCapabilities`` responses. See the example below for all supported keys.


``srs``
"""""""

The ``srs`` option defines which SRS the WMS service supports.::

   srs: ['EPSG:4326', 'CRS:84', 'EPSG:900913']

See :ref:`axis order<axis_order>` for further configuration that might be needed for WMS 1.3.0.


``image_formats``
"""""""""""""""""

A list of image mime types the server should support.



Full example
""""""""""""
::
  
  services:
    wms:
      srs: ['EPSG:4326', 'CRS:83', 'EPSG:900913']
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
          country: Germany
          phone: +49(0)000-000000-0
          fax: +49(0)000-000000-0
          email: you@example.org
        access_constraints: This service is intended for private and evaluation use only.
        fees: 'None'
            


.. index:: WMS-C Service
.. _wmsc_service_label:


WMS-C
"""""

The MapProxy WMS service also supports the `WMS Tiling Client Recommendation <http://wiki.osgeo.org/wiki/WMS_Tiling_Client_Recommendation>`_ from OSGeo.

If you add ``tiled=true`` to the GetCapabilities request, MapProxy will add metadata about the internal tile structure to the WMS capabilities document. Clients that support WMS-C can use this information to request tiles at the exact tile boundaries. MapProxy can return the tile as-it-is for these requests, the performace is on par with the TMS service.

MapProxy will limit the WMS support when ``tiled=true`` is added to the `GetMap` requests and it will return WMS service exceptions for requests that do not match the exact tile boundaries.


.. index:: TMS Service, Tile Service
.. _tms_service_label:

Tiled Map Services (TMS)
------------------------

MapProxy supports the `Tile Map Service Specification`_ from the OSGeo. The TMS is available at ``/tms/1.0.0``. 

Here is an example TMS request: ``/tms/1.0.0/base_EPSG900913/3/1/0.png``. ``png`` is the internal format of the cached tiles. ``base`` is the name of the layer and ``EPSG900913`` is the SRS of the layer. You can only select a SRS that your layer is caching.

A request to ``/tms/1.0.0`` will return the TMS metadata as XML. ``/tms/1.0.0/layername`` will return information about the bounding box, resolutions and tile size of this specific layer.

This service takes no further options::

  services:
    tms:


.. index:: OpenLayers

OpenLayers
""""""""""
When you create a map in OpenLayers with an explicit ``mapExtend``, it will request only a single tile for the first (z=0) level.
TMS begins with two or four tiles by default, depending on the SRS. MapProxy supports a different TMS mode to support this use-case. MapProxy will start with a single-tile level if you request ``/tiles`` instead of ``/tms``.


.. index:: Google Maps

Google Maps
"""""""""""
The TMS standard counts tiles starting from the lower left corner of the tile grid, while Google Maps starts at the upper left corner. The ``/tiles`` service accepts an ``origin`` parameter that flips the y-axis accordingly. You can set it to either ``sw`` (south-west), the default, or to ``nw`` (north-west), required for Google Maps.

Example::
  
  http://localhost:8080/tiles/osm_EPSG900913/1/0/1.png?origin=nw

.. _`Tile Map Service Specification`: http://wiki.osgeo.org/wiki/Tile_Map_Service_Specification


.. index:: KML Service, Super Overlay
.. _kml_service_label:

Keyhole Markup Language (OGC KML)
---------------------------------

MapProxy supports KML version 2.2 for integration into Google Earth. Each layer is available as a Super Overlay – image tiles are loaded on demand when the user zooms to a specific region. The initial KML file is available at ``/kml/layername/0/0/0.kml``.

  This service takes no further options::

    services:
      tms:


