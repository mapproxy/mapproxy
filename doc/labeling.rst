WMS Labeling
============

The tiling of rendered vector maps often results in issues with truncated or repeated labels. Some of these issues can be reduced with a proper configuration of MapProxy, but some require changes to the configuration of the source WMS server.

This document describes settings for MapProxy and MapServer, but the problems and solutions are also valid for other WMS servers. Refer to their documentations on how to configure these settings.

The Problem
-----------

MapProxy always uses small tiles for caching. MapProxy does not pass through incoming requests to the source WMS [#]_, but it always requests images/tiles that are aligned to the internal grid. MapProxy combines, scales and reprojects these tiles for WMS requests and for tiled requests (TMS/KML) the tiles are combined by the client (OpenLayers, etc).

.. [#] Except for uncached, cascaded WMS requests.

When tiles are combined, the text labels at the boundaries need to be present at both tiles and need to be placed at the exact same (geographic) location.

There are three common problems here.

No placement outside the BBOX
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
WMS servers do not draw features that are outside of the map bounds. For example, a city label that extends into the neighboring map tile will not be drawn in that other tile, because the geographic feature of the city (a single point) is only present in one tile.

.. image:: imgs/labeling-no-placement.png

Dynamic label placement
~~~~~~~~~~~~~~~~~~~~~~~
WMS servers can adjust the position of labels so that more labels can fit on a map. For example, a city label is not always displayed at the same geographic location, but moved around to fit in the requested map or to make space for other labels.

.. image:: imgs/labeling-dynamic.png

Repeated labels
~~~~~~~~~~~~~~~
WMS servers render labels for polygon areas in each request. Labels for large areas will apear multiple times, once in each tile.

.. image:: imgs/labeling-repeated.png 


MapProxy Options
----------------

There are two options that help with these issues.

.. _meta_tiles:

Meta Tiles
~~~~~~~~~~

You can use meta tiles to reduce the labeling issues. A meta tile is a collection of multiple tiles. Instead of requesting each tile with a single request, MapProxy requests a single image that covers the area of multiple tiles and then splits that response into the actual tiles.

The following image demonstrates that:

.. image:: imgs/labeling-metatiling.png

The thin lines represent the tiles. The WMS request (inner box) consists of 20 tiles and without metatiling each tile results in a request to the WMS source. With a meta tile size of 4x4, only two larger requests to the source WMS are required (thick black box).

Because you are requesting less images, you have less boundaries where labeling issues can appear. In this case it reduces the number of tile/image boundaries from 31 to only one.

But, it only reduces the problem and does not solve it. Nonetheless, it should be used because it also reduces the load on the source WMS server.

You can configure the meta tile size in the ``globals.cache`` section and for each ``cache``. It defaults to ``[4, 4]``.

::

  globals:
    cache:
      meta_size: [6, 6]
  
  caches:
    mycache:
      sources: [...]
      grids: [...]
      meta_size: [8, 8]


This does also work for tiles services. When a client like OpenLayers requests the 20 tiles from the example above in parallel, MapProxy will still requests the two meta tiles. Locking ensures that each meta tile will be requested only once.

.. _meta_buffer:

Meta Buffer
~~~~~~~~~~~

In addition to meta tiles, MapProxy implements a meta buffer. The meta buffer adds extra space at the edges of the requested area. With this buffer, you can solve the first issue: no placement outside the BBOX.

.. image:: imgs/labeling-meta-buffer.png

You can combine meta tiling and meta buffer. MapProxy then extends the whole meta tile with the configured buffer.

A meta buffer of 100 will add 100 pixels at each edge of the request. With a meta size of 4x4 and a tile size of 256x256, the requested image is extended from 1024x1024 to 1224x1224. The BBOX is also extended to match the new geographical extent.

.. image:: imgs/labeling-metatiling-buffer.png

To solve the first issue, the value should be at least half of your longest labels: If you have text labels that are up to 200 pixels wide, than you should use a meta buffer of around 120 pixels.

You can configure the size of the meta buffer in the ``globals.cache`` section and for each ``cache``. It defaults to ``80``.
::

  globals:
    cache:
      meta_buffer: 100
  
  caches:
    mycache:
      sources: [...]
      grids: [...]
      meta_buffer: 150



WMS Server Options
------------------

You can reduce some of the labeling issues with meta tiling, and solve the first issue with the meta buffer. The issues with dynamic and repeated labeling requires some changes to your WMS server. 

In general, you need to disable the dynamic position of labels and you need to allow the rendering of partial labels.


MapServer Options
-----------------

MapServer has lots of settings that affect the rendering. The two most important settings are

``PROCESSING "LABEL_NO_CLIP=ON"`` from the ``LAYER`` configuration.
  With this option the labels are fixed to the whole feature and not only the part of the feature that is visible in the current map request. Default is off.

and 

``PARTIALS`` from the ``LABEL`` configuration.
  If this option is true, then labels are rendered beyond the boundaries of the map request. Default is true. 


``PARTIAL FALSE``
~~~~~~~~~~~~~~~~~

The easiest option to solve all issues is ``PARTIAL FALSE`` with a meta buffer of 0. This prevents any label from truncation, but it comes with a large downside: Since no labels are rendered at the boundaries of the meta tiles, you will have areas with no labels at all. These areas form a noticeable grid pattern on your maps.

The following images demonstrates a WMS request with a meta tile boundary in the center.

.. image:: imgs/labeling-partial-false.png

You can improve that with the right set of configuration options for each type of geometry.

Points
~~~~~~

As described above, you can use a meta buffer to prevent missing labels. You need to set ``PARTIALS TRUE`` (which is the default), and configure a large enough meta buffer. The labels need to be placed at the same position with each request. You can configure that with the ``POSITION`` options. The default is ``auto`` and you should set this to an explicit value, ``cc`` or ``uc`` for example.


``example.map``::

  LABEL
    [...]
    POSITION cc
    PARTIALS TRUE
  END


``mapproxy.yaml``::

  caches:
    mycache:
      meta_buffer: 150
      [...]

.. 
.. ``PARTIALS TRUE``:
..   .. image:: imgs/mapserver_points_partials_true.png
.. 
.. ``PARTIALS FALSE``:
..   .. image:: imgs/mapserver_points_partials_false.png

Polygons
~~~~~~~~

Meta tiling reduces the number of repeated labels, but they can still apear at the border of meta tiles.

You can use the ``PROCESSING "LABEL_NO_CLIP=ON"`` option to fix this problem.
With this option, MapServer places the label always at a fixed position, even if that position is outside the current map request.

.. image:: imgs/labeling-no-clip.png

If the ``LABEL_NO_CLIP`` option is used, ``PARTIALS`` should be ``TRUE``. Otherwise label would not be rendered if they overlap the map boundary. This options also requires a meta buffer.

``example.map``::
  
  LAYER
    TYPE POLYGON
    PROCESSING "LABEL_NO_CLIP=ON"
    [...]
    LABEL
      [...]
      POSITION cc
      PARTIALS TRUE
    END
  END

``mapproxy.yaml``::

  caches:
    mycache:
      meta_buffer: 150
      [...]

.. ``PROCESSING  "LABEL_NO_CLIP=ON"`` and ``PARTIALS TRUE``:
..   .. image:: imgs/mapserver_area_with_labelclipping.png
.. 
.. ``PARTIALS FALSE``:
..   .. image:: imgs/mapserver_area_without_labelclipping.png

Lines
~~~~~

By default, labels are repeated on longer line strings. Where these labels are repeated depends on the current view of that line. That placement might differ in two neighboring image requests for long lines.

Most of the time, the labels will match at the boundaries of the meta tiles, when you use ``PARTIALS TRUE`` and a meta buffer. But, you might notice truncated labels on long line strings. In practice these issues are rare, though.


``example.map``::

  LAYER
    TYPE LINE
    [...]
    LABEL
      [...]
      PARTIALS TRUE
    END
  END

``mapproxy.yaml``::

  caches:
    mycache:
      meta_buffer: 150
      [...]

You can disable repeated labels with ``PROCESSING LABEL_NO_CLIP="ON"``, if don't want to have any truncated labels. Like with polygons, you need set ``PARTIALS TRUE`` and use a meta buffer. The downside of this is that each lines will only have one label in the center of that line.


``example.map``::
  
  LAYER
    TYPE LINE
    PROCESSING "LABEL_NO_CLIP=ON"
    [...]
    LABEL
      [...]
      PARTIALS TRUE
    END
  END

``mapproxy.yaml``::

  caches:
    mycache:
      meta_buffer: 150
      [...]

There is a third option. If you want repeated labels but don't want any truncated labels, you can set ``PARTIALS FALSE``. Remember that you will get the same grid pattern as mentioned above, but it might not be noted if you mix this layer with other point and polygon layers where ``PARTIALS`` is enabled.

You need to compensate the meta buffer when you use ``PARTIALS FALSE`` in combination with other layers that require a meta buffer. You need to set the option ``LABELCACHE_MAP_EDGE_BUFFER`` to the negative value of your meta buffer.

::

  WEB
    [...]
    METADATA
      LABELCACHE_MAP_EDGE_BUFFER "-100"
    END
  END

  LAYER
    TYPE LINE
    [...]
    LABEL
      [...]
      PARTIALS FALSE
    END
  END

``mapproxy.yaml``::

  caches:
    mycache:
      meta_buffer: 100
      [...]

.. It has to be evaluated which solution is the best for each application: some cropped or missing labels.
.. 
.. ``PROCESSING  "LABEL_NO_CLIP=ON"`` and ``PARTIALS TRUE``:
..   .. image:: imgs/mapserver_road_with_labelclipping.png
.. 
.. ``PROCESSING  "LABEL_NO_CLIP=OFF"`` and ``PARTIALS FALSE``:
..   .. image:: imgs/mapserver_road_without_labelclipping.png


Other WMS Servers
-----------------

The most important step for all WMS servers is to disable to dynamic placement of labels. Look into the documentation how to do this for you WMS server.

If you want to contribute to this document then join our `mailing list <http://lists.osgeo.org/mailman/listinfo/mapproxy>`_ or use our `issue tracker <https://github.com/mapproxy/mapproxy/issues/>`_.
