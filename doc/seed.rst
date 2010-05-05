Seeding
=======

The MapProxy creates all tiles on demand. To improve the performance for commonly
requested views it is possible to pre-generate these tiles. The ``mapproxy-seed`` script does
this task.

.. note:: ``mapproxy-seed`` is a new version of the seed tool. The old ``proxy_seed`` tool is deprecated and will be removed in 0.9.0. The configuration is upward compatible.

mapproxy-seed
----------

The command line script expects a seed configuration that describes which tiles from which layer should be generated. See `configuration`_ for the format of the file.

Use the ``-f`` option to specify the proxy configuration.
::

    mapproxy-seed -f etc/proxy.yaml etc/seed.yaml

Configuration
--------------

The configuration contains two keys: ``views`` and ``seeds``. ``views`` describes
geographical extends that should be seeded. ``seeds`` links actual layers with
those ``views``.


Seeds
^^^^^

Contains a dictionary with layer/view mapping.::

    seeds:
        cache1:
            views: ['world', 'germany', 'oldb']
        cache2:
            views: ['world', 'germany']
            remove_before:
                time: '2009-04-01T14:45:00'
                # or 
                minutes: 15
                hours: 4
                days: 9
                weeks: 8

`remove_before`:
    If present, recreate tiles if they are older than the date or time delta. At the
    end of the seeding process all tiles that are older will be removed.
    
    You can either define a fixed time or a time delta. The `time` is a ISO-like date
    string (no time-zones, no abbreviations). To define time delta use one or more
    `minutes`, `hours`, `days`, `weeks` entries.

Views
^^^^^

Contains a dictionary with all views. Each view describes a geographical extend.

Geographical extend
*******************

There are three different ways to describe the extend of the seed view.

 - a simple rectangular bounding box,
 - a text file with one or more polygons in WKT format,
 - polygons from any data source readable with OGR (e.g. Shapefile, PostGIS)

.. note:: The last two variants require `Shapely <http://pypi.python.org/pypi/Shapely>`_. Make sure it is available (e.g. ``pip install Shapely``). Shapely itself needs GEOS and the OGR reader needs GDAL/OGR. On Debian/Ubuntu these libraries are in the ``libgeos-dev`` and ``libgdal-dev`` packages.

Bounding box
""""""""""""

``bbox``:
    The BBOX that should be cached. If omitted, the whole BBOX of the layer is used.

``bbox_srs``:
    The SRS of the BBOX.

Polygon file
""""""""""""

.. versionadded:: 0.8.3

``polygons``:
  Path to a text file with one WKT polygon per line. The path should be relative to
  the proxy configuration or absolute. `We provide polygons for every country <http://mapproxy.org/static/polygons/>`_. `Read the index <http://mapproxy.org/static/polygons/0-fips-codes.txt>`_ to find your country. You can use these or create your own. 

``polygons_srs``:
  The SRS of the polygons.

OGR datasource
""""""""""""""

.. versionadded:: 0.8.3

``ogr_datasource``:
  The name of the datasource. Refer to the `OGR format page
  <http://www.gdal.org/ogr/ogr_formats.html>`_ for a list of all supported
  datasources. File paths should be relative to the proxy configuration or absolute.

``ogr_where``:
  Restrict which polygons should be loaded from the datasource. Either a simple where
  statement (e.g. 'CNTRY_NAME="Germany"') or a full select statement. Refer to the
  `OGR SQL support documentation <http://www.gdal.org/ogr/ogr_sql.html>`_. If this
  option is unset, the first layer from the datasource will be used.

``ogr_srs``:
  The SRS of the polygons.

Other options
*************

``srs``:
    A list with SRSs. If the layer contains caches for multiple SRS, only the caches
    that match one of the SRS in this list will be seeded.

``res``:
    Seed until this resolution is cached.

or

``level``:
    A number until which this layer is cached, or a tuple with a range of
    levels that should be cached.

Example::
    
    views:
        world: # cache whole layer from level 0 to 3
            level: 3
        germany: # seed a fixed bbox, from level 4 to 10
            bbox:  [5.40731, 46.8447, 15.5072, 55.4314]
            bbox_srs: EPSG:4326
            level: (4, 10)
        oldb: # seed around bbox until resolution of 4m/px
            bbox: [904500, 7000800, 925700, 7020400]
            bbox_srs: EPSG:900913
            srs: ['EPSG:4326', 'EPSG:900913']
            res: 4