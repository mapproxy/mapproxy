######################
Configuration examples
######################


This document will show you some usage scenarios of MapProxy and will explain some combinations of configuration options that might be useful for you.


Merge multiple layers
=====================

You have two WMS and want to offer a single layer with data from both servers. Each MapProxy layer can have more than one data source. MapProxy will combine the results from the sources before it stores the cached tiles. These combined layers can also be requested via tiled services.

The layers should be defined from top to bottom. Top layers should be transparent.

Example::

  combined_layer:
    md:
      title: Aerial image + roads overlay
    sources:
    - type: cache_wms
      wms_opts:
        featureinfo: True
        version: 1.1.1
      req:
          url: http://one.example.org/mapserv/?map=/home/map/roads.map
          layers: roads
          transparent: true
    - type: cache_wms
      req:
          url: http://two.example.org/service?
          layers: aerial


.. note:: If the layers come from the same WMS server, you can just them to the ``layers`` parameter. E.g. ``layers: water,railroads,roads``.


Access local servers
====================

If a source is on the same host or connected with high bandwidth (i.e. LAN), you can use an uncompressed image format for requests to the source WMS. By default MapProxy will request data in the same format it uses to cache the data. For example, if you cache files in PNG MapProxy will request all images from the source WMS in PNG too. This compression is quite CPU intensive and can be avoided if you have plenty of bandwidth. Your source WMS should respond faster if you use uncompressed TIFF.

Example::

  fast_source:
    md:
      title: Map from local server
    params:
      request_format: image/tiff
    sources:
    - type: cache_wms
      req:
        url: http://localhost/mapserv/?map=/home/map/roads.map
        layers: roads
        transparent: true


Cache raster data
=================

You have a WMS server that offers raster data like aerial images. By default MapProxy uses PNG images as the caching format. The encoding process for PNG files is very computing intensive and thus the caching process itself takes longer. For aerial images the quality of lose-less image formats like PNG is often not required. For best performance you should use JPEG as the cache format::

  aerial_images:
    params:
      format: image/jpeg
    [sources and md omitted]


By default MapProxy uses `bicubic` resampling. This resampling method also sharpens the image wich is important for vector images. Arial images do not need this, so you can use `bilinear` or even Nearest Neighbor (`nearest`) resampling.

You might also want to experiment with different compression levels of JPEG. A higher value of ``jpeg_quality`` results in better image quality at the cost of slower encoding and lager file sizes. See :ref:`proxy.yaml configuration <jpeg_quality>`.

Example ``proxy.yaml``::

  image:
    jpeg_quality: 80
    resampling: bilinear


Cache vector data
=================

You have a WMS server that renders vector data like road maps. 

Cache resolutions
-----------------

By default MapProxy caches traditional power-of-two image pyramids, the resolutions between each pyramid level doubles. For example if the first level has a resolution of 10km, it would also cache resolutions of 5km, 2.5km, 1.125km etc. Requests with a resolution of 7km would be generated from cached data with a resolution of 10km. The problem with this approach is, that everything needs to be scaled down, lines will get thin and text labels will become unreadable. The solution is simple: Just add more levels to the pyramid. There are three options to do this.


You can set every cache resolution in the ``res`` option of a layer.
::

  custom_res:
    params:
      res: [10000, 7500, 5000, 3500, 2500]
    [sources and md omitted]

You can specify a different factor that is used to calculate the resolutions. By default a factor of 2 is used (10, 5, 2.5,…) but you can set smaller values like 1.6 (10, 6.25, 3.9,…)::

  custom_factor:
    params:
      res: 1.6
    [sources and md omitted]

The third options is a convenient variation of the previous option. A factor of 1.41421, the square root of two, would get resolutions of 10, 7.07, 5, 3.54, 2.5,…. Notice that every second resolution is identical to the power-of-two resolutions. This comes in handy if you use the layer not only in classic WMS clients but also want to use it in tile-based clients like OpenLayers, wich only request in these resolutions.
::

  sqrt2:
    params:
      res: sqrt2
    [sources and md omitted]
    
.. note:: The quality of aerial images or scanned maps are unaffected from these options.

Resampling method
-----------------

You can configure the method MapProxy uses for resampling when it scales or transforms data. For best results with vector data – from a viewers perspective – you should use bicubic resampling. Your ``proxy.yaml`` should contain::

  image:
    resampling: bicubic


Add highly dynamic layers
=========================

You have dynamic layers that change constantly and you do not want to cache these. You can use the ``direct`` source type. See next example. 

Reproject WMS layers
====================

If you do not want want to cache data but still want to use MapProxy's ability to reproject WMS layers on the fly, you can add the layers as a ``direct`` layer.
You should explicitly define the SRS the source WMS supports. Requests in other SRS will be reprojected. You should specify at least one geographic and one projected SRS to limit the distortions from reprojection. 
::

  direct_example:
    [md and params omitted]
    sources:
    - type: direct
      supported_srs: ['EPSG:4326', 'EPSG:25832']
      req:
        url: http://wms.example.org/service?
        layers: layer0,layer1
    


.. osm_mapnik:
..     md:
..         title: osm.omniscale.net - Open Street Map
..     attribution:
..         text: "Nur zu Testzwecken!"
..     sources:
..     - type: cache_tms
..       ll_origin: True
..       url: http://osm.omniscale.net/proxy/tms/osm_EPSG900913
