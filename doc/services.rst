Services
========

By default MapProxy handles WMS, TMS and KML requests. To change which services should be started you can change your proxy configuration (``proxy.yaml``). For a WMS and TMS server::

 server: ['wms', 'tms']


Web Map Service (OGC WMS)
-------------------------

The WMS server is accessible at `/service`. The server supports the WMS versions 1.0.0, 1.1.1 and 1.3.0.

SRS
"""

The `wms.srs` option defines which SRS the WMS service supports. If you need other systems than the default, uncomment the lines in the proxy configuration and add all your EPSG codes::

 wms:
   srs: ['EPSG:4326', 'CRS:84', 'EPSG:900913']

See :ref:`axis order<axis_order>` for further configuration that might be needed for WMS 1.3.0.

Tiled Map Services (TMS)
------------------------

MapProxy supports the `Tile Map Service Specification`_ from the OSGeo. The TMS is available at `/tms/1.0.0`. A request to this URL will return some metadata in XML format.

Here is an example TMS request: ``/tms/1.0.0/base_EPSG900913/3/1/0.png``. ``png`` is the internal format of the cached tiles. ``base`` is the name of the layer and ``EPSG900913`` is the SRS of the layer. You can only select a SRS that your layer is caching. You can omit the SRS for EPSG900913.


OpenLayers
""""""""""
When you create a map in OpenLayers with an explicit ``mapExtend``, it will request only a single tile for the first (z=0) level.
TMS begins with two or four tiles by default, depending on the SRS. MapProxy supports a different TMS mode to support this use-case. MapProxy will start with a single-tile level if you request ``/tiles`` instead of ``/tms``.


.. _`Tile Map Service Specification`: http://wiki.osgeo.org/wiki/Tile_Map_Service_Specification


Keyhole Markup Language (OGC KML)
---------------------------------

MapProxy supports KML version 2.2 for integration into Google Earth. Each layer is available as a Super Overlay – image tiles are loaded on demand when the user zooms to a specific region. The initial KML file  is available at `/kml/layername/0/0/0.kml`.

To start the KML server, you have to add it to your `proxy.yaml`::

 server: ['kml']


