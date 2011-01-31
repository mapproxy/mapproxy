Labeling
==========

Caching from dynamically drawn maps often leads problems with the labeling. Labels are cut or areas get multiple labels.

MapProxy has some settings to reduce these problems. But as well, map servers have several settings which should be considered.

Metatiles and Metabuffer
---------------------------------------

MapProxy uses Metatiles. A Metatile is composed by several tiles. The squares limited by the thick black lines (figure 1) symbolize the Metatiles. The squares limited by the thin lines inside are the cached tiles. 

When the MapProxy gets a map request (green square), a bigger area (red square) is requested from the map server. Then MapProxy calculates the map from the Metatiles. The figure shows Metatiles containing 16 regular tiles.

The usage of Metatiles brings advantage for labeling: fewer requests will be send to the  map server. This way the sources of wrong labeling will be minimized. For example, labels in features are displayed only once and not in every tile.

``figure 1:``
  .. image:: imgs/metatiling.png

In addition to Metatiles, MapProxy implements the Metabuffer. The Metabuffer adds pixels at the edge of the requested area (red square). This way labels positioned at the edge will be included in the request.

Metatiles and Metabuffer can be configured in the settings:

::

  # add a buffer on all sides (in pixel)
  meta_buffer: 80 
  
  # size of the meta_tiling
  meta_tiling: [4,4]

To get optimal results, it is also important to adjust the map server. The fonts have to be positioned statically and shall not be drawn for each request to a new location. In almost all map servers you can disable the option for dynamic font positioning.


Some tipps and tricks for MapServer settings
--------------------------------------------

In our example we are working with the MapServer (http://mapserver.org). To achieve the best results for interaction between MapServer and MapProxy, there are some things you should consider. 

Some useful options in the MapServer:

``PROCESSING "LABEL_NO_CLIP"``
  With this option the labels are fixed to a feature. Default is off.


``FORCE``
  Draw every label regardless of collisions. Default is false.


``PARTIALS``
  If this option is true a label can run beyond the edge of a map. Default is true. 

Lets have a look at some examples for using this options. In our examples we use different settings, for different features:

Points
--------
Every point has only one label. For showing a lot of labels on a map it is useful to activate the option ``PARTIALS``. This way labels are drawn even if they run beyond the edge of the map. For not cutting the labels the Metabuffer from MapProxy is needed, too.

On the right side fewer labels are drawn, because ``PARTIALS`` is set to ``FALSE``

``PARTIALS TRUE``:
  .. image:: imgs/mapserver_points_partials_true.png

``PARTIALS FALSE``:
  .. image:: imgs/mapserver_points_partials_false.png

Areas
------
In areas only one label in each feature is useful. In many cases there are already good results by using Metatiles from MapProxy. But in the following example there are two labels in one area. This is because the border of a Metatile crosses the area.

In addition to the possibility of enlarging the meta_size, one can use the ``PROCESSING  "LABEL_NO_CLIP=ON"`` option in the MapServer to fix this problem. So the area has only one label that is attributed to the feature. If the ``PROCESSING LABEL_NO_CLIP`` option is used, ``PARTIALS`` has to be set ``TRUE``. Otherwise – assuming the requested area is at the edge of a Metatile - the label of the area is lost. Additional an according Metabuffer has to be set in the configuration of the MapProxy.

``PROCESSING  "LABEL_NO_CLIP=ON"`` and ``PARTIALS TRUE``:
  .. image:: imgs/mapserver_area_with_labelclipping.png

``PROCESSING  "LABEL_NO_CLIP=OFF"`` and ``PARTIALS FALSE``:
  .. image:: imgs/mapserver_area_without_labelclipping.png

LineString
----------

For labels on streets like in a printed road atlas, the labels repeat depending on the length of the street. If this is intended, the ``PROCESSING LABEL_NO_CLIP`` option of the MapServer cannot be used. For good results a big Metabuffer in the MapProxy is needed. Also ``PARTIALS`` has to be set ``TRUE`` so that a lot of labels are drawn. In general these options generate good results, but some features have artifacts like cropped labels.

Another option to be sure that no labels are cropped the settings can be changed – accepting that some labels get lost. The ``PROCESSING LABEL_NO_CLIP`` option can be used, but zooming into the map one cannot see the label anymore. In this case the following options have to be set:

::
  
  PARTIALS FALSE
  PROCESSING "LABEL_NO_CLIP=ON" 
  meta_buffer: 0

Is a Metabuffer set in MapProxy and shouldn't or cannot be changed, it can be balanced by using the option ``LABELCACHE_MAP_EDGE_BUFFER`` in MapServer. The value of ``LABELCACHE_MAP_EDGE_BUFFER`` has to be the negative meta_buffer.

::

  METADATA
    LABELCACHE_MAP_EDGE_BUFFER "-80"
  END

It has to be evaluated which solution is the best for each application: some cropped or missing labels.

``PROCESSING  "LABEL_NO_CLIP=ON"`` and ``PARTIALS TRUE``:
  .. image:: imgs/mapserver_road_with_labelclipping.png

``PROCESSING  "LABEL_NO_CLIP=OFF"`` and ``PARTIALS FALSE``:
  .. image:: imgs/mapserver_road_without_labelclipping.png