MapProxy 2.0
############

MapProxy will change a few defaults in the configuration between 1.8 and 2.0. You might need to adapt your configuration to have MapProxy 2.0 work the same as MapProxy 1.8 or 1.7.

Most changes are made to make things more consistent, to make it easier for new users and to discourage a few deprecated things.

.. warning:: Please read this document carefully. Also check all warnings that the latest 1.8 version of `mapproxy-util serve-develop` will generate with your configuration before upgrading to 2.0.


Grids
=====

New default tile grid
---------------------

MapProxy now uses GLOBAL_WEBMERCATOR as the default grid, when no grids are configured for a cache or a tile source. This grid is compatible with Google Maps and OpenStreetMap, and uses the same tile origin as the WMTS standard.

The old default GLOBAL_MERCATOR uses a different tile origin (lower-left instead of upper-left) and you need to set this grid if you upgrade from MapProxy 1 and have caches or tile sources without an explicit grid configured.


MapProxy used the lower-left tile in a tile grid as the origin. This is the same origin as the TMS standard uses. Google Maps, OpenStreetMap and now also WMTS are counting tiles from the upper-left tile. MapProxy changes


Default origin
--------------

The default origin changes from 'll' (lower-left) to 'ul' (upper-left). You need to set the origin explicitly if you use custom grids. The origin will stay the same if your custom grid is `base`d on the `GLOBAL_*` grids.

WMS
===

SRS
---

The WMS does not support EPSG:900913 by default anymore to discourage the use of this deprecated EPSG code. Please use EPSG:3857 instead or add it back to the WMS configuration (see :ref:`wms_srs`).

Image formats
-------------

PNG and JPEG are the right image formats for almost all use cases. GIF and TIFF are therefore no longer enabled by default. You can enable them back in the WMS configuration if you need them (:ref:`wms_image_formats`)


Other
=====

This document will be extended.
