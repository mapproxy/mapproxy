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

Axis ordering
^^^^^^^^^^^^^

The axis ordering defines in which order coordinates are given, i.e. lon/lat or lat/lon. The ordering is dependent to the SRS. Most clients and servers did not respected the ordering and everyone used lon/lat ordering. With the WMS 1.3.0 specification the OGC emphasized that the axis ordering of the SRS should be used. MapProxy must know the axis ordering of each enabled SRS for 1.3.0 support. The axis orderings are already defined for all default SRS. If you add you own SRS to the WMS configuration, you have to define the ordering with the `srs` options.
::

 srs:
   # for North/East ordering
   axis_order_ne: ['EPSG:9999', 'EPSG:9998']
   # for East/North ordering
   axis_order_en: ['EPSG:0000', 'EPSG:0001']


Tiled Map Services (TMS)
------------------------

MapProxy supports the `Tile Map Service Specification`_ from the OSGeo. The TMS is available at `/tms/1.0.0`. A request to this URL will return some metadata in XML format.

Here is an example TMS request: ``/tms/1.0.0/base_EPSG900913/3/1/0.png``. ``png`` is the internal format of the cached tiles. ``base`` is name of the layer and ``EPSG900913`` is the SRS of the layer. You can only select a SRS that your layer is caching. You can omit the SRS for EPSG900913.


OpenLayers
""""""""""
When you create a map in OpenLayers with an explicit ``mapExtend``, it will request only a single tile for the first (z=0) level.
TMS begins with two or four tiles by default, depending on the SRS. MapProxy supports a different TMS mode to support this use-case. MapProxy will start with a single-tile level if you request ``/tiles`` instead of ``/tms``.


.. _`Tile Map Service Specification`: http://wiki.osgeo.org/wiki/Tile_Map_Service_Specification