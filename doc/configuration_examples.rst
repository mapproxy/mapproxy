.. _configuration_examples:

######################
Configuration examples
######################

This document will show you some usage scenarios of MapProxy and will explain some combinations of configuration options that might be useful for you.

.. _merge_layers:

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

Create WMS from existing tile server
====================================

You can use MapProxy to create a WMS server with data from an existing tile server. That tile server could be a WMTS, TMS or any other tile service where you can access tiles by simple HTTP requests. You always need to configure a cache in MapProxy to get a WMS from a tile source, since the cache is the part that does the tile stitching and reprojection.


Here is a minimal example::

 layers:
  - name: my_layer
    title: WMS layer from tiles
    sources: [mycache]

 caches:
   mycache:
     grids: [GLOBAL_WEBMERCATOR]
     sources: [my_tile_source]

 sources:
   my_tile_source:
     type: tile
     url: http://tileserver/%(tms_path)s.png

You need to modify the ``url`` template parameter to match the URLs of your server. You can use ``x``, ``y``, ``z`` variables in the template, but MapProxy also supports the ``quadkey`` variable for Bing compatible tile service and ``bbox`` for WMS-C services. See the :ref:`tile source documentation <tiles_label>` for all possible template values.

Here is an example of a WMTS source::

 sources:
   my_tile_source:
     type: tile
     url: http://tileserver/wmts?SERVICE=WMTS&REQUEST=GetTile&
        VERSION=1.0.0&LAYER=layername&TILEMATRIXSET=WEBMERCATOR&
        TILEMATRIX=%(z)s&TILEROW=%(y)s&TILECOL=%(x)s&FORMAT=image%%2Fpng

.. note:: You need to escape percent signs (``%``) in the URL by repeating them (``%%``).

.. _osm_tile_conf:

You can use the ``GLOBAL_WEBMERCATOR`` grid for OpenStreetMap or Google Maps compatible sources. Most TMS services should be compatible with the ``GLOBAL_MERCATOR`` definition that is similar to ``GLOBAL_WEBMERCATOR`` but uses a different origin (south west (TMS) instead of north west (OSM/WMTS/Google Maps/etc.)).
Other tile services might use different SRS, bounding boxes or resolutions. You need to check the capabilities of your service and :ref:`configure a compatible grid <grids>`.

You also need to create your own grid when you want to change the name of it, which will appear in the WMTS or TMS URL.

Example configuration for an OpenStreetMap tile service::

  layers:
    - name: my_layer
      title: WMS layer from tiles
      sources: [mycache]

  caches:
    mycache:
      grids: [webmercator]
      sources: [my_tile_source]

  sources:
    my_tile_source:
      type: tile
      grid: GLOBAL_WEBMERCATOR
      url: http://a.tile.openstreetmap.org/%(z)s/%(x)s/%(y)s.png

 grids:
  webmercator:
    base: GLOBAL_WEBMERCATOR

.. note:: Please make sure you are allowed to access the tile service. Commercial tile provider often prohibit the direct access to tiles. The tile service from OpenStreetMap has a strict `Tile Usage Prolicy <http://wiki.openstreetmap.org/wiki/Tile_usage_policy>`_.

.. _overlay_tiles_osm_openlayers:

Overlay tiles with OpenStreetMap or Google Maps in OpenLayers
=============================================================

You need to take care of a few options when you want to overlay your MapProxy tiles in OpenLayers with existing OpenStreetMap or Google Maps tiles.

The basic configuration for this use-case with MapProxy may look like this::

  layers:
    - name: street_layer
      title: TMS layer with street data
      sources: [street_cache]

  caches:
    street_cache:
      sources: [street_tile_source]

  sources:
    street_tile_source:
      type: tile
      url: http://osm.omniscale.net/proxy/tiles/ \
        1.0.0/osm_roads_EPSG900913/%(z)s/%(x)s/%(y)s.png
      transparent: true

All you need to do now is to configure your OpenLayers client.
The first example creates a simple OpenLayers map in webmercator projection, adds an OSM base layer and a TMS overlay layer with our MapProxy tile service.::

  <script src="http://openlayers.org/api/OpenLayers.js"></script>
  <script type="text/javascript">
    var map;
    function init(){
        map = new OpenLayers.Map('map', {
            projection: new OpenLayers.Projection("EPSG:900913")
        });

        var base_layer = new OpenLayers.Layer.OSM();

        var overlay_layer = new OpenLayers.Layer.TMS(
            'TMS street_layer',
            'http://127.0.0.1:8080/tiles/',
            {layername: 'street_layer_EPSG900913',
             type: 'png', isBaseLayer: false}
        );

        map.addLayer(base_layer);
        map.addLayer(overlay_layer);
        map.zoomToMaxExtent();
    };
  </script>

Note that we used the ``/tiles`` service instead of ``/tms`` here. See :ref:`the tile service documentation <open_layers_label>` for more information.

Also remember that OpenStreetMap and Google Maps tiles have the origin in the upper left corner of the map, instead of the lower left corner as TMS does. Have a look at the :ref:`example configuration for OpenStreetMap tiles<osm_tile_conf>` for more information on that topic. The OpenLayers TMS and OSM layers already handle the difference.

You can change how MapProxy calculates the origin of the tile coordinates, if you want to use your MapProxy tile service with the OpenLayers OSM layer class or if you want to use a client that does not have a TMS layer.

The following example uses the class OpenLayers.Layer.OSM::

    var overlay_layer = new OpenLayers.Layer.OSM("OSM osm_layer",
        "http://x.osm.omniscale.net/proxy/tiles/ \
        osm_roads_EPSG900913/${z}/${x}/${y}.png?origin=nw",
        {isBaseLayer: false, tileOptions: {crossOriginKeyword: null}}
    );

The origin parameter at the end of the URL tells MapProxy that the client expects the origin in the upper left corner (north/west).
You can change the default origin of all MapProxy tile layers by using the ``origin`` option of the ``tms`` service. See the :ref:`TMS standard tile origin<google_maps_label>` for more informations.

.. _using_existing_caches:

Using existing caches
=====================

.. versionadded:: 1.5.0

In some special use-cases you might want to use a cache as the source of another cache. For example, you might need to change the grid of an existing cache
to cover a larger bounding box, or to support tile clients that expect a different grid, but you don't want to seed the data again.

Here is an example of a cache in UTM that uses data from an existing cache in web-mercator projection.

::

    layers:
      - name: lyr1
        title: Layer using data from existing_cache
        sources: [new_cache]

    caches:
      new_cache:
        grids: [utm32n]
        sources: [existing_cache]

      existing_cache:
        grids: [GLOBAL_WEBMERCATOR]
        sources: [my_source]

    grids:
      utm32n:
        srs: 'EPSG:25832'
        bbox: [4, 46, 16, 56]
        bbox_srs: 'EPSG:4326'
        origin: 'nw'
        min_res: 5700


Reprojecting Tiles
==================

.. versionadded:: 1.5.0

When you need to access tiles in a projection that is different from your source tile server, then you can use the *cache as cache source* feature from above.
Here is an example that uses OSM tiles as a source and offers them in UTM projection. The `disable_storage` option prevents MapProxy from building up two caches. The `meta_size` makes MapProxy to reproject multiple tiles at once.


Here is an example that makes OSM tiles available as tiles in UTM. Note that reprojecting vector data results in quality loss. For better results you need to find similar resolutions between both grids.

::

    layers:
      - name: osm
        title: OSM in UTM
        sources: [osm_cache]

    caches:
      osm_cache:
        grids: [utm32n]
        meta_size: [4, 4]
        sources: [osm_cache_in]

      osm_cache_in:
        grids: [GLOBAL_WEBMERCATOR]
        disable_storage: true
        sources: [osm_source]

    sources:
      osm_source:
        type: tile
        grid: GLOBAL_WEBMERCATOR
        url: http://a.tile.openstreetmap.org/%(z)s/%(x)s/%(y)s.png

    grids:
      utm32n:
        srs: 'EPSG:25832'
        bbox: [4, 46, 16, 56]
        bbox_srs: 'EPSG:4326'
        origin: 'nw'
        min_res: 5700


Create grayscale images
=======================

.. versionadded:: 1.9.0

You can create a grayscale layer from an existing source by creating a cache that merges multiple bands into a single band.
The band sources can come from caches, but also from any direct source. You can ``disable_storage`` to make this conversion on-the-fly.
The following example mixes the RGB bands of a source with factors that matches the intensity perception of most humans::

  caches:
   grayscale_cache:
       disable_storage: true
       sources:
           l: [
               {source: dop, band: 0, factor: 0.21},
               {source: dop, band: 1, factor: 0.72},
               {source: dop, band: 2, factor: 0.07},
           ]


Cache raster data
=================

You have a WMS server that offers raster data like aerial images. By default MapProxy uses PNG images as the caching format. The encoding process for PNG files is very CPU intensive and thus the caching process itself takes longer. For aerial images the quality of loss-less image formats like PNG is often not required. For best performance you should use JPEG as the cache format.

By default MapProxy uses `bicubic` resampling. This resampling method also sharpens the image which is important for vector images. Aerial images do not need this, so you can use `bilinear` or even Nearest Neighbor (`nearest`) resampling.
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


Mixed mode
----------

You need to store images with transparency when you want to overlay them over other images, e.g. at the boundaries of your aerial image coverage. PNG supports transparency but it is not efficient with arial images, while JPEG is efficient for aerial images but doesn't support transparency.

MapProxy :ref:`has a mixed image format <mixed_image_format>` for this case. With the ``mixed`` format, MapProxy stores tiles as either PNG or JPEG, depending on the transparency of each tile. Images with transparency will be stored as PNG, fully opaque images as JPEG.

.. note:: The source of your cache must support transparent images and you need to set the corresponding options.

::

  caches:
    mixed_cache:
      format: mixed
      sources: [wms_source]
      request_format: image/png

  sources:
    wms_source:
      type: wms
      req:
        url: http://localhost:42423/service
        layers: aerial
        transparent: true

You can now use the cache in all MapProxy services. WMS GetMap requests will return the image with the requested format.
With TMS or WMTS you can only request PNG tiles, but the actual response image is either PNG or JPEG. The HTTP `content-type` header is set accordingly. This is supported by all web browsers.

Cache vector data
=================

You have a WMS server that renders vector data like road maps.

.. _cache_resolutions:

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

The third options is a convenient variation of the previous option. A factor of 1.41421, the square root of two, would get resolutions of 10, 7.07, 5, 3.54, 2.5,…. Notice that every second resolution is identical to the power-of-two resolutions. This comes in handy if you use the layer not only in classic WMS clients but also want to use it in tile-based clients like OpenLayers, which only request in these resolutions.

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

.. _direct_source:

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

FeatureInfo support is enabled by default for WMS. For :ref:`WMTS you need to enable FeatureInfo queries by configuring the supported formats <wmts_feature_info>`.


.. note:: The more advanced features :ref:`require the lxml library <lxml_install>`.

Concatenation
-------------
Feature information from different sources are concatenated as plain text, that means that XML documents may become invalid. But MapProxy can also do content-aware concatenation when :ref:`lxml <lxml_install>` is available.

HTML
~~~~

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

MapProxy supports XSL transformations for more control over feature information. This also requires :ref:`lxml <lxml_install>`. You can add an XSLT script for each WMS source (incoming) and for the WMS service (outgoing).

You can use XSLT for sources to convert all incoming documents to a single, uniform format and then use outgoing XSLT scripts to transform this format to either HTML or XML/GML output.

Example
~~~~~~~

Lets assume we have two WMS sources where we have no control over the format of the feature info responses.

One source only offers HTML feature information. The XSLT script extracts data from a table. We force the WMS ``INFO_FORMAT`` to HTML with the ``featureinfo_format`` option, so that MapProxy will not query another format. The XSLT script returns XML and not HTML. We configure this with the ``featureinfo_out_format`` option.

::

    fi_source:
      type: wms
      wms_opts:
        featureinfo: true
        featureinfo_xslt: ./html_in.xslt
        featureinfo_format: text/html
        featureinfo_out_format: text/xml
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


.. _wmts_dimensions:

WMTS service with dimensions
============================

.. versionadded:: 1.6.0

The dimension support in MapProxy is still limited, but you can use it to create a WMTS front-end for a multi-dimensional WMS service.

First you need to add the WMS source and configure all dimensions that MapProxy should forward to the service::

  temperature_source:
    type: wms
    req:
      url: http://example.org/service?
      layers: temperature
    forward_req_params: ['time', 'elevation']


We need to create a cache since we want to access the source from a tiled service (WMTS). Actual caching is not possible at the moment, so it is necessary to disable it with ``disable_storage: true``.

::

    caches:
      temperature:
        grids: [GLOBAL_MERCATOR]
        sources: [temperature_source]
        disable_storage: true
        meta_size: [1, 1]
        meta_buffer: 0

Then we can add a layer with all available dimensions::

    layers:
      - name: temperature
        title: Temperature
        sources: [temperature]
        dimensions:
          time:
            values:
              - "2012-11-12T00:00:00"
              - "2012-11-13T00:00:00"
              - "2012-11-14T00:00:00"
              - "2012-11-15T00:00:00"
          elevation:
            values:
              - 0
              - 1000
              - 3000
            default: 0

You can now access this layer with the elevation and time dimensions via the WMTS KVP service.
The RESTful service requires a custom URL template that contains the dimensions. For example::

    services:
      wmts:
        restful_template: '/{Layer}/{Time}/{Elevation}/{TileMatrixSet}
            /{TileMatrix}/{TileCol}/{TileRow}.{Format}'


Tiles are then available at ``/wmts/temperature/GLOBAL_MERCATOR/1000/2012-11-12T00:00Z/6/33/22.png``.
You can use ``default`` for missing dimensions, e.g. ``/wmts/map/GLOBAL_MERCATOR/default/default/6/33/22.png``.


WMS layers with HTTP Authentication
===================================

You have a WMS source that requires authentication. MapProxy has support for HTTP Basic
Authentication and HTTP Digest Authentication. You just need to add the username and password to the URL. Since the Basic and Digest authentication
are not really secure, you should use this feature in combination with HTTPS.
You need to configure the SSL certificates to allow MapProxy to verify the HTTPS connection. See :ref:`HTTPS configuration for more information <http_ssl>`.
::

  secure_source:
    type: wms
    req:
      url: https://username:mypassword@example.org/service?
      layers: securelayer

MapProxy removes the username and password before the URL gets logged or inserted into service exceptions.

You can disable the certificate verification if you you don't need it.
::

  secure_source:
    type: wms
    http:
      ssl_no_cert_checks: True
    req:
      url: https://username:mypassword@example.org/service?
      layers: securelayer

.. note:: If the source requires session handling through cookies, have a look at the ``manage_cookies`` configuration option.

.. _http_proxy:

Access sources through HTTP proxy
=================================

MapProxy can use an HTTP proxy to make requests to your sources, if your system does not allow direct access to the source. You need to set the ``http_proxy`` and ``https_proxy`` environment variable to the proxy URL. This also applies if you install MapProxy with ``pip``.

On Linux/Unix::

  $ export http_proxy="http://example.com:3128" https_proxy="http://example.com:3128"
  $ mapproxy-util serve-develop mapproxy.yaml

On Windows::

  c:\> set http_proxy="http://example.com:3128" https_proxy="http://example.com:3128"
  c:\> mapproxy-util serve-develop mapproxy.yaml


You can also set this in your :ref:`server script <server_script>`::

  import os
  os.environ["http_proxy"] = "http://example.com:3128"
  os.environ["https_proxy"] = "http://example.com:3128"

Add a username and password to the URL if your HTTP proxy requires authentication. For example ``http://username:password@example.com:3128``.

.. note:: If the source requires session handling through cookies, have a look at the ``manage_cookies`` configuration option.

You can use the ``no_proxy`` environment variable if you need to bypass the proxy for some hosts::

  $ export no_proxy="localhost,127.0.0.1,196.168.1.99"


Cookie Management
=================

MapProxy can handle server cookies of HTTP sources, like browsers do. That is, MapProxy accepts cookies and passes them back
on subsequent calls. This is useful for sources that use cookie for session management or rate-limiting for example::

  sources:
    wms_with_session_management:
      type: wms
      http:
        manage_cookies: True
      req:
        url: http://example.org/service?
        layers: layer0

.. _paster_urlmap:

Serve multiple MapProxy instances
=================================

It is possible to load multiple MapProxy instances into a single process. Each MapProxy can have a different global configuration and different services and caches. [#f1]_  You can use :ref:`MultiMapProxy` to load multiple MapProxy configurations on-demand.

Example ``config.py``::

    from mapproxy.multiapp import make_wsgi_app
    application = make_wsgi_app('/path/to/projects', allow_listing=True)


The MapProxy configuration from ``/path/to/projects/app.yaml`` is then available at ``/app``.

You can reuse parts of the MapProxy configuration with the `base` option. You can put all common options into a single base configuration and reference that file in the actual configuration::

  base: mapproxy.yaml
  layers:
     [...]


.. [#f1] This does not apply to `srs.proj_data_dir`, because it affects the proj4 library directly.

.. _quadkey_cache:

Generate static quadkey / virtual earth cache for use on Multitouch table
=========================================================================

Some software running on Microsoft multitouch tables need a static quadkey generated cache. Mapproxy understands quadkey both as a client and as a cache option.

Example part of ``mapproxy.yaml`` to generate a quadkey cache::

  caches:
    osm_cache:
      grids: [GLOBAL_WEBMERCATOR]
      sources: [osm_wms]
      cache:
        type: file
        directory_layout: quadkey


.. _hq_tiles:

HQ/Retina tiles
===============

MapProxy has no native support for delivering high-resolution tiles, but you can create a second tile layer with HQ tiles, if your source supports rendering with different scale-factor or DPI.

At first you need two grids. One regular grid and one with half the resolution but twice the tile size. The following example configures two webmercator compatible grids::

  grids:
    webmercator:
      srs: "EPSG:3857"
      origin: nw
      min_res: 156543.03392804097
    webmercator_hq:
      srs: "EPSG:3857"
      origin: nw
      min_res: 78271.51696402048
      tile_size: [512, 512]

Then you need two layers and two caches::

  layers:
    - name: map
      title: Regular map
      sources: [map_cache]
    - name: map_hq
      title: HQ map
      sources: [map_hq_cache]

  caches:
    map_cache:
      grids: [webmercator]
      sources: [map_source]
    map_hq_cache:
      grids: [webmercator_hq]
      sources: [map_hq_source]

And finally two sources. The source for the HQ tiles needs to render images with a higher scale/DPI setting. The ``mapnik`` source supports this with the ``scale_factor`` option. MapServer for example supports a ``map_resolution`` request parameter.

::

  sources:
    map_source:
      type: mapnik
      mapfile: ./mapnik.xml
      transparent: true

    map_hq_source:
      type: mapnik
      mapfile: ./mapnik.xml
      transparent: true
      scale_factor: 2


With that configuration ``/wmts/mapnik/webmercator/0/0/0.png`` returns a regular webmercator tile:

.. image:: imgs/mapnik-webmerc.png

``/wmts/mapnik_hq/webmercator_hq/0/0/0.png`` returns the same tile with 512x512 pixel:

.. image:: imgs/mapnik-webmerc-hq.png


Serve multiple caches for a single layer
========================================

.. versionadded:: 1.8.2

You have a data set that you need to serve with different grids (i.e. WMTS tile matrix sets).

You can create a cache with multiple grids and use this as a layers source::

  layers:
    - name: map
      title: Layer with multiple grids
      sources: [cache]

  caches:
    cache:
      grids: [full_grid, sub_grid]
      sources: [source]

This `map` layer is available in WMS and in tile services. The grids are available as separate tile matrix sets in the WMTS.
However, this is limited to a single cache for each layer. You can't reuse the tiles from the `full_grid` for the `sub_grid`.

You need to use ``tile_sources`` to make multiple caches available as a single layer.
``tile_sources`` allows you to override ``sources`` for tile services. This allows you to `use caches that build up on other caches  <using_existing_caches>`_.

For example::

  layers:
    - name: map
      title: Layer with sources for tile services and for WMS
      tile_sources: [full_cache, inspire_cache]
      sources: [full_cache]

  caches:
    full_cache:
      grids: [full_grid]
      sources: [source]
    inspire_cache:
      grids: [sub_grid]
      sources: [full_cache]
      disable_storage: true


