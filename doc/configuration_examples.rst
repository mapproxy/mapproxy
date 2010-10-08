######################
Configuration examples
######################

This document will show you some usage scenarios of MapProxy and will explain some combinations of configuration options that might be useful for you.


Merge multiple layers
=====================

You have two WMS and want to offer a single layer with data from both servers. Each MapProxy cache can have more than one data source. MapProxy will combine the results from the sources before it stores the tiles on disk. These combined layers can also be requested via tiled services.

The sources should be defined from bottom to top. All sources except the bottom source needs to be transparent.

Example::

  layers:
    combined_layer:
      title: Aerial image + roads overlay
      sources: [combined_cache]
  
  caches:
    combined_cache:
      sources: [base, aerial]
  
  sources:
    base:
      type: wms
      wms_opts:
        featureinfo: True
        version: 1.1.1
      req:
          url: http://one.example.org/mapserv/?map=/home/map/roads.map
          layers: roads
          transparent: true
    aerial:
      type: wms
      req:
          url: http://two.example.org/service?
          layers: aerial


.. note:: If the layers come from the same WMS server, then you can add them direct to the ``layers`` parameter. E.g. ``layers: water,railroads,roads``.


Access local servers
====================

By default MapProxy will request data in the same format it uses to cache the data, if you cache files in PNG MapProxy will request all images from the source WMS in PNG. This encoding is quite CPU intensive for your WMS server but reduces the amount of data than needs to be transfered between you WMS and MapProxy. You can use uncompressed TIFF as the request format, if both servers are on the same host or if they are connected with high bandwidth.

Example::
  
  sources:
    fast_source:
      request_format: image/tiff
      type: cache_wms
      req:
        url: http://localhost/mapserv/?map=/home/map/roads.map
        layers: roads
        transparent: true


Cache raster data
=================

You have a WMS server that offers raster data like aerial images. By default MapProxy uses PNG images as the caching format. The encoding process for PNG files is very computing intensive and thus the caching process itself takes longer. For aerial images the quality of lose-less image formats like PNG is often not required. For best performance you should use JPEG as the cache format.

By default MapProxy uses `bicubic` resampling. This resampling method also sharpens the image wich is important for vector images. Arial images do not need this, so you can use `bilinear` or even Nearest Neighbor (`nearest`) resampling.
::

  caches:
    aerial_images_cache:
      format: image/jpeg
      image:
        resampling_method: nearest
      sources: [aerial_images]


You might also want to experiment with different compression levels of JPEG. A higher value of ``jpeg_quality`` results in better image quality at the cost of slower encoding and lager file sizes. See :ref:`mapproxy.yaml configuration <jpeg_quality>`.

::

  globals:
    jpeg_quality: 80


Cache vector data
=================

You have a WMS server that renders vector data like road maps. 

Cache resolutions
-----------------

By default MapProxy caches traditional power-of-two image pyramids, the resolutions between each pyramid level doubles. For example if the first level has a resolution of 10km, it would also cache resolutions of 5km, 2.5km, 1.125km etc. Requests with a resolution of 7km would be generated from cached data with a resolution of 10km. The problem with this approach is, that everything needs to be scaled down, lines will get thin and text labels will become unreadable. The solution is simple: Just add more levels to the pyramid. There are three options to do this.


You can set every cache resolution in the ``res`` option of a layer.
::

  caches:
    custom_res_cache:
      grids: [custom_res]
      sources: [vector_source]
  
  grids:
    custom_res_cache:
      srs: 'EPSG:31467'
      res: [10000, 7500, 5000, 3500, 2500]
  
You can specify a different factor that is used to calculate the resolutions. By default a factor of 2 is used (10, 5, 2.5,…) but you can set smaller values like 1.6 (10, 6.25, 3.9,…)::

  grids:
    custom_factor:
      res_factor: 1.6

The third options is a convenient variation of the previous option. A factor of 1.41421, the square root of two, would get resolutions of 10, 7.07, 5, 3.54, 2.5,…. Notice that every second resolution is identical to the power-of-two resolutions. This comes in handy if you use the layer not only in classic WMS clients but also want to use it in tile-based clients like OpenLayers, wich only request in these resolutions.
::

  grids:
    sqrt2:
      res_factor: sqrt2
    
.. note:: This does not improve the quality of aerial images or scanned maps, so you should avoid it for these images.

Resampling method
-----------------

You can configure the method MapProxy uses for resampling when it scales or transforms data. For best results with vector data – from a viewers perspective – you should use bicubic resampling. You can configure this for each cache or in the globals section::

  caches:
    vector_cache:
      image:
        resampling: bicubic
      # [...]

  # or
  
  globals:
    image:
      resampling: bicubic
  

Add highly dynamic layers
=========================

You have dynamic layers that change constantly and you do not want to cache these. You can use a direct source. See next example. 

Reproject WMS layers
====================

If you do not want to cache data but still want to use MapProxy's ability to reproject WMS layers on the fly, you can use a direct layer. Add your source directly to your layer instead of a cache.

You should explicitly define the SRS the source WMS supports. Requests in other SRS will be reprojected. You should specify at least one geographic and one projected SRS to limit the distortions from reprojection. 
::

  layers:
    direct_layer:
      sources: [direct_wms]
  
  sources:
    direct_wms:
      type: direct
      supported_srs: ['EPSG:4326', 'EPSG:25832']
      req:
        url: http://wms.example.org/service?
        layers: layer0,layer1
    


WMS layers with HTTP Basic Authentication
=========================================

You have a WMS source that requires authentication. MapProxy has support for HTTP Basic
Authentication. You just need to add the username and password to the URL. Since the
password is sent in plaintext, you should use this feature in combination with HTTPS.
You need to configure the SSL certificates to allow MapProxy to verify the HTTPS connection. See :ref:`HTTPS configuration for more information <http_ssl>`.
::

  secure_source:
    type: wms
    req:
      url: https://username:mypassword@example.org/service?
      layers: securelayer


You can disable the certificate verification if you you don't need it.
::

  secure_source:
    type: wms
    http:
      ssl_no_cert_check: True
    req:
      url: https://username:mypassword@example.org/service?
      layers: securelayer
  

