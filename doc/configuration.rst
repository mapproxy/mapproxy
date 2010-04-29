Configuration
=============

There are a few different configuration files used by MapProxy. Some are required and some are optional.

``services.yaml``
    This file configures which services and layers the proxy should offer. You can
    define from where the proxy should get which data. You can also set metadata like
    contact information for the Capabilities documents.
    
``proxy.yaml``
    This is the main configuration of the proxy. Configure which servers should be
    started, where the cached data should be stored, etc.
    
``seed.yaml``
    This file is the configuration for the proxy_seed tool.
    

``log.ini``
    Configures the logging.

``develop.ini`` and ``config.ini``
    These are the paster configuration files that are used to start the proxy in development or production mode.

``services.yaml``
-----------------

All layers the proxy offers are configured in this file. The configuration uses the YAML format.


.. note:: The indentation is significant and shall only contain space characters. Tabulators are **not** permitted for indentation.

The configuration contains the keys ``service`` and ``layers``.


service
^^^^^^^

Here is an example for the ``service`` part::

    service:
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



attribution
"""""""""""

Adds an attribution (copyright) line to all WMS requests.

``text``
  The text line of the attribution (e.g. some copyright notice, etc).

md
""""
``md`` is for metadata. These fields are used for the WMS ``GetCapabilities`` responses. See the above example for all supported keys.

layers
^^^^^^

Here you can define all layers the proxy should offer. Each layer configuration is a YAML dictionary. The key of each layer is also the name of the layer, i.e. the name used in WMS layers argument. If MapProxy should use the same ordering of the layers for capability responses, you should put the definitions in a list (prepend a ``-`` before the key).
::

  layers:
    - layer1:
      option1: aaa
      option2: bbb
    - layer2:
      option1: xxx
      option2: yyy



Each configuration item contains information about the layer (e.g. name), how the layer is cached (e.g. in which SRS) and where the data comes from (e.g. which WMS-Server).

md
""""
Metadata for this layer. At the moment only ``title`` ist supported. It will be used as the human readable name for WMS layers.

param
""""""

Unter ``param`` werden Parameter für die Datenquelle und den Zwischenspeicher gesetzt.

``format``
    This is the internal image format for the cache. The default is ``image/png``.

``request_format``
    This format is used to request new tiles. If the bandwidth to the WMS server is high
    (e.g. localhost or LAN) you should use ``image/tiff`` here. That prevents unnecessary
    encoding and decoding of the images. If unset ``format`` is used.

``srs``
    The spatial reference system used for the internal cache. You can define multiple SRSs
    here. One cache is created for each.::
    
        srs: EPSG:4326
          or
        srs: ['EPSG:4326', 'EPSG:900913']
 
    MapProxy supports on-the-fly transformation of requests between different SRSs. So
    it is not required to add an extra cache for each supported SRS. For best performance
    only the SRS most requests are in should be used.
    
    There is some special handling layers that need geographical and projected coordinate
    systems. If you set both ``EPSG:4326`` and ``EPSG:900913`` all requests with projected
    SRS will access the ``EPSG:900913`` cache, requests with geographical SRS will use
    ``EPSG:4326``. The distortions from the transformation should be acceptable these to cached SRS.

``res``
    The resolution for which MapProxy should cache tiles.
    For requests with no matching cached resolution the next best resolution is used and MapProxy will transform the result. There are three ways to configure the resolutions.

    
    1. A factor between each resolution. With each step the resolution is multiplied by this
    factor. Defaults to 2.
    
    2. A list with resolutions in units per pixel (degrees or meter per pixel). The units
    from the first configured ``srs`` are used.
    
    3. The term ``sqrt2``. This option is a shorthand for a resolution factor of 1.4142 (i.e.
    square root of two). With this factor the resolution doubles every second level. Compared
    to the default factor 2 you will get another cached level between all standard levels.
    This is suited for free zooming in vector-based layers where the results might look to
    blurry/pixelated in some resolutions.
        

sources
"""""""

You define the data sources of each layer here. The configuration ref:`is explained below
<sources-conf-label>`.

attribution
"""""""""""
Overwrite the system-wide attribution line for this layer.

``inverse``
  If this option is set to ``true``, the colors of the attribution will be inverted. Use this if the normal attribution is hard to on this layer (i.e. on aerial imagery).

watermark
"""""""""""

Add a watermark right into the cached data. The watermark is thus also present in TMS or KML requests.

``text``
    The watermark text. Should be short.

``opacity``
    The opacity of the watermark (from 0 transparent to 255 full opaque).
    Use a value between 3 and 10 for unobtrusive watermarks.


.. _sources-conf-label:

sources
^^^^^^^

Every layer contains one or more sources. The sources define where the proxy should get the data for this layer. Each layer has a type.

MapProxy support the following types:

``direct``
"""""""""""
A ``direct`` source passes all requests to the configured WMS server and does *not* cache any data.
``req`` defines the source WMS URL and the layers that should be requested.

Example::

  - type: direct
    req:
      url: http://servername/service
      layers: poi,roads

``cache_wms``
""""""""""""""

The ``cache_wms`` source passes requests to a WMS server and caches all data for further requests.

``req``
    ``req`` contains the source WMS URL and the layers.
    For transparent layers the option ``transparten`` should be set to ``'true'``.

``wms_opts``
    This option affects what request the proxy sends to the source WMS server.
    
    ``version`` is the WMS version number used for requests (supported: 1.0.0, 1.1.1, 1.3.0).
    If ``featureinfo`` is true, MapProxy will mark the layer as queryable and incoming
    `GetFeatureInfo` requests will be forwarded to the source server.
    

Example::

  - type: cache_wms
    wms_opts:
      version: 1.0.0
      featureinfo: True
    req:
      url: http://localhost:8080/service?
      layers: roads
      transparent: 'true'


``debug``
"""""""""""

Adds information like resolution and bbox to the response image.
This is useful to determine a fixed set of resolutions for the ``res``-parameter.



.. TODO
.. Examples
.. # direct:
.. #     md:
.. #         title: Direct Layer
.. #     sources:
.. #     - req:
.. #         url: http://carl:5000/service
.. #         layers: foo,bar
.. #       type: direct
.. combined:
..     md:
..         title: OSM Mapnik + MapServer WMS (Cached)
..     cache_dir: mapnik_mapserver
..     param:
..         format: image/png
..         srs: EPSG:900913
..     sources:
..     - type: cache_wms
..       wms_opts:
..         featureinfo: True
..         version: 1.1.1
..       req:
..           url: http://burns/mapserv/?map=/home/os/mapserver/mapfiles/osm.map
..           layers: roads
..     - type: cache_wms
..       req:
..           url: http://carl/service?
..           layer: luftbild
.. osm_roads:
..     md:
..         title: OSM Streets
..     attribution:
..         inverse: 'true'
..     param:
..         format: image/png
..         srs: ['EPSG:4326', 'EPSG:900913']
..         # res: 'sqrt2'
..     pngquant: True
..     sources:
..     - type: cache_wms
..       req:
..         url: http://carl/service?
..         layers: roads
..         transparent: 'true'
.. osm_mapnik:
..     md:
..         title: osm.omniscale.net - Open Street Map
..     attribution:
..         text: "Nur zu Testzwecken!"
..     sources:
..     - type: cache_tms
..       ll_origin: True
..       url: http://osm.omniscale.net/proxy/tms/osm_EPSG900913
