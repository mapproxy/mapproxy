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
    - name: combined_layer
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

Merge tile sources
------------------

.. versionadded:: 1.0.0

You can also merge multiple tile sources. You need to tell MapProxy that all overlay sources are transparent::

  sources:
    tileoverlay:
      type: tile
      url: http://localhost:8080/tile?x=%(x)s&y=%(y)s&z=%(z)s&format=png
      transparent: true

Access local servers
====================

By default MapProxy will request data in the same format it uses to cache the data, if you cache files in PNG MapProxy will request all images from the source WMS in PNG. This encoding is quite CPU intensive for your WMS server but reduces the amount of data than needs to be transfered between you WMS and MapProxy. You can use uncompressed TIFF as the request format, if both servers are on the same host or if they are connected with high bandwidth.

Example::
  
  sources:
    fast_source:
      type: cache_wms
      req:
        url: http://localhost/mapserv/?map=/home/map/roads.map
        layers: roads
        format: image/tiff
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
  

.. _sld_example:

WMS Sources with Styled Layer Description (SLD)
===============================================

You can configure SLDs for your WMS sources.

::

  sources:
    sld_example:
      type: wms
      req:
        url: http://example.org/service?
        sld: http://example.net/mysld.xml


MapProxy also supports local file URLs. MapProxy will use the content of the file as the ``sld_body``.
The path can either be absolute (e.g. ``file:///path/to/sld.xml``) or relative (``file://path/to/sld.xml``) to the mapproxy.yaml file. The file should be UTF-8 encoded.

You can also configure the raw SLD with the ``sld_body`` option. You need to indent whole SLD string.

::

  sources:
    sld_example:
      type: wms
      req:
        url: http://example.org/service?
        sld_body:
          <sld:StyledLayerDescriptor version="1.0.0"
          [snip]
          </sld:StyledLayerDescriptor>


MapProxy will use HTTP POST requests in this case. You can change ``http.method``, if you want to force GET requests.


Add highly dynamic layers
=========================

You have dynamic layers that change constantly and you do not want to cache these. You can use a direct source. See next example. 

Reproject WMS layers
====================

If you do not want to cache data but still want to use MapProxy's ability to reproject WMS layers on the fly, you can use a direct layer. Add your source directly to your layer instead of a cache.

You should explicitly define the SRS the source WMS supports. Requests in other SRS will be reprojected. You should specify at least one geographic and one projected SRS to limit the distortions from reprojection. 
::

  layers:
    - name: direct_layer
      sources: [direct_wms]
  
  sources:
    direct_wms:
      type: wms
      supported_srs: ['EPSG:4326', 'EPSG:25832']
      req:
        url: http://wms.example.org/service?
        layers: layer0,layer1
    

.. _fi_xslt:

FeatureInformation
==================

MapProxy can pass-through FeatureInformation requests to your WMS sources. You need to enable each source::


  sources:
    fi_source:
      type: wms
      wms_opts:
        featureinfo: true
      req:
        url: http://example.org/service?
        layers: layer0


MapProxy will mark all layers that use this source as ``queryable``. It also works for sources that are used with caching.

.. note:: The more advanced features :ref:`require the lxml library <lxml_install>`. 

Concatenation
-------------
Feature information from different sources are concatenated as plain text, that means that XML documents may become invalid. But MapProxy can also do content-aware concatenation when :ref:`lxml <lxml_install>` is available.

HTML
~~~~

.. versionadded:: 1.0.0

Multiple HTML documents are put into the HTML ``body`` of the first document.
MapProxy creates the HTML skeleton if it is missing.
::

  <p>FI1</p>

and
::

  <p>FI2</p>

will result in::

  <html>
    <body>
      <p>FI1</p>
      <p>FI2</p>
   </body>
  </html>


XML
~~~

.. versionadded:: 1.0.0

Multiple XML documents are put in the root of the first document.

::

  <root>
    <a>FI1</a>
  </root>

and
::

  <other_root>
    <b>FI2</b>
  </other_root>

will result in::

  <root>
    <a>FI1</a>
    <b>FI2</b>
  </root>


XSL Transformations
-------------------

.. versionadded:: 1.0.0

MapProxy supports XSL transformations for more control over feature information. This also requires :ref:`lxml <lxml_install>`. You can add an XSLT script for each WMS source (incoming) and for the WMS service (outgoing).

You can use XSLT for sources to convert all incoming documents to a single, uniform format and then use outgoing XSLT scripts to transform this format to either HTML or XML/GML output.

Example
~~~~~~~

Lets assume we have two WMS sources where we have no control over the format of the feature info responses.

One source only offers HTML feature information. The XSLT script extracts data from a table. We force the ``INFO_FORMAT`` to HTML, so that MapProxy will not query another format.

::

    fi_source:
      type: wms
      wms_opts:
        featureinfo: true
        featureinfo_xslt: ./html_in.xslt
        featureinfo_format: text/html
      req: [...]


The second source supports XML feature information. The script converts the XML data to the same format as the HTML script. This service uses WMS 1.3.0 and the format is ``text/xml``.
::

    fi_source:
      type: wms
      wms_opts:
        version: 1.3.0
        featureinfo: true
        featureinfo_xslt: ./xml_in.xslt
        featureinfo_format: text/xml
      req: [...]


We then define two outgoing XSLT scripts that transform our intermediate format to the final result. We can define scripts for different formats. MapProxy chooses the right script depending on the WMS version and the ``INFO_FORMAT`` of the request.

::

  wms:
    featureinfo_xslt:
      html: ./html_out.xslt
      xml: ./xml_out.xslt
    [...]


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
  

.. _paster_urlmap:

Serve multiple MapProxy instances
=================================

Since 0.9.1 it is possible to load multiple MapProxy instances into a single process. Each MapProxy can have a different global configuration and different services and caches. [#f1]_ You can use `Paste's urlmap <http://pythonpaste.org/deploy/#composite-applications>`_ to load multiple MapProxy configurations. If you have multiple MapProxy configurations and what to load them dynamically, then you can also use :ref:`MultiMapProxy`.

Example ``config.ini``::

  [composite:main]
  use = egg:Paste#urlmap
  /proxy1 = proxy1
  /proxy2 = proxy2

  [app:proxy1]
  use = egg:MapProxy#app
  mapproxy_conf = %(here)s/proxy1.yaml

  [app:proxy2]
  use = egg:MapProxy#app
  mapproxy_conf = %(here)s/proxy2.yaml

MapProxy is then available at ``/proxy1`` and ``/proxy2``.

You can reuse parts of the MapProxy configuration with the `base` option. You can put all common options into a single base configuration and reference that file in the actual configuration::

  base: mapproxy.yaml
  layers:
     [...]


.. [#f1] This does not apply to `srs.proj_data_dir`, because it affects the proj4 library directly.
