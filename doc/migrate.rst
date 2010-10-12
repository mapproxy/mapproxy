Migration from 0.8.x to 0.9.x
#############################


MapProxy changed the configuration format with the 0.9.0 release in a backwards incompatible way. The format still uses YAML/JSON syntax but it is now more structured and more flexible.

This guide should help you to migrate your existing MapProxy configuration to the new format.

.. note:: You can skip this document if you create a new project with ``paster create -t mapproxy_conf``.


develop.ini and config.ini
""""""""""""""""""""""""""

We removed the distinction between the services (``service.yaml``) and global (``proxy.yaml``) configuration. There is now a single configuration file wich is named ``mapproxy.yaml`` by default.

You need to update your ``develop.ini`` and ``config.ini`` if you use ``paster serve`` for deployment or testing and point MapProxy to the new configuration.

::

  [app:main]
  use = egg:MapProxy#app
  mapproxy_conf = %(here)s/mapproxy.yaml
  

proxy.yaml
""""""""""

Most options from the ``proxy.yaml`` defined global settings of MapProxy. These global options are now placed in the `globals` section of the ``mapproxy.yaml``. See :ref:`globals configuration <globals-conf-label>` for all available options.

.. note:: Some of the global options are know also available on cache/layer/grid level (e.g. ``image.resampling_method`` or ``cache.meta_size``). Refer to the :doc:`configuration documentation <configuration>`.

The services (WMS/TMS/KML) are know configured in the ``services`` section. See :doc:`services documentation <services>`.

services.yaml
"""""""""""""

With 0.8.x you had to configure each layer independently and you could not reuse anything. The new configuration separates the source, grid, cache and layers configuration.

You now only need to define you grids once. It is also possible to define complete different grids (``srs``, ``bbox``, ``tile_size``, etc.) and use them within the same cache. All sources and caches can also be used in multiple layers.


Example
-------

Here is a configuration example from 0.8::
  
  layers:
    - osm:
        md:
            title: Omniscale OSM WMS - osm.omniscale.net
        param:
            # cache tiles in format:
            format: image/png
          
            # cache projected and geographical SRS
            srs: ['EPSG:4326', 'EPSG:900913']
          
            # request all data in this format:
            request_format: image/tiff
          
            # use a tile size of:
            tile_size: [256, 256]
        sources:
        - type: cache_wms
          req:
            url: http://osm.omniscale.net/proxy/service?
            layers: osm


Enhanced with some more options this becomes::

  layers:
    - osm:
      title: Omniscale OSM WMS - osm.omniscale.net
      sources: [osm_cache]
  
  caches:
    osm_cache:
      grids: [GLOBAL_MERCATOR, GLOBAL_GEODETIC]
      sources: [osm_wms]
      format: image/png
      request_format: image/tiff
      meta_size: [6, 6]
      meta_buffer: 100
      
  sources:
    osm_wms:
      type: wms
      req:
        url: http://osm.omniscale.net/proxy/service?
        layers: osm


We used the predefined grids ``GLOBAL_GEODETIC`` (EPSG:4326) and ``GLOBAL_MERCATOR`` (EPSG:900913) in this case, but it is easy to define custom grids::

  grids:
    my_grid_4326:
      bbox: [5, 50, 10, 55]
      bbox_srs: 'EPSG:4326'
      srs: 'EPSG:4326'
      num_levels: 10
      tile_size: [512, 512]
    my_grid_900913:
      base: my_grid_4326
      srs: 'EPSG:900913'


The default configuration of MapProxy contains more examples. To create a new one::

  paster create -t mapproxy_conf /tmp/mapproxy_example

