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
          layer: aerial


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
