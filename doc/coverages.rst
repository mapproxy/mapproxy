.. _coverages:

Coverages
=========

.. versionadded:: 0.9.1

With coverages you can define areas where data is available or where data you are interested in is.
MapProxy supports coverages for :doc:`sources <sources>` and in the :doc:`mapproxy-seed tool <seed>`. Refer to the corresponding section in the documentation.


There are three different ways to describe a coverage.

- a simple rectangular bounding box,
- a text file with one or more (multi)polygons in WKT format,
- (multi)polygons from any data source readable with OGR (e.g. Shapefile, PostGIS)


Requirements
------------

If you want to use polygons to define a coverage, instead of simple bounding boxes, you will also need Shapely and GEOS. For loading polygons from shapefiles you'll also need GDAL/OGR.

MapProxy requires Shapely 1.2.0 or later and GEOS 3.1.0 or later.

On Debian::

  sudo aptitude install libgeos-dev libgdal-dev
  pip install Shapely


Coverage Types
--------------

Bounding box
""""""""""""

``bbox``:
    A simple BBOX as a list, e.g: `[4, -30, 10, -28]`.

``bbox_srs``:
    The SRS of the BBOX.

Polygon file
""""""""""""

``polygons``:
  Path to a text file with one WKT polygon or multi-polygon per line. The path should be relative to
  the proxy configuration or absolute. You can create your own files or use `one of the files we provide for every country <http://mapproxy.org/static/polygons/>`_. Read `the index <http://mapproxy.org/static/polygons/0-fips-codes.txt>`_ to find your country. 

``polygons_srs``:
  The SRS of the polygons.

OGR datasource
""""""""""""""

``ogr_datasource``:
  The name of the datasource. Refer to the `OGR format page
  <http://www.gdal.org/ogr/ogr_formats.html>`_ for a list of all supported
  datasources. File paths should be relative to the proxy configuration or absolute.

``ogr_where``:
  Restrict which polygons should be loaded from the datasource. Either a simple where
  statement (e.g. ``'CNTRY_NAME="Germany"'``) or a full select statement. Refer to the
  `OGR SQL support documentation <http://www.gdal.org/ogr/ogr_sql.html>`_. If this
  option is unset, the first layer from the datasource will be used.

``ogr_srs``:
  The SRS of the polygons.


Examples
--------

sources
"""""""

Use the ``coverage`` option to define a coverage for a WMS or tile source.

::

  sources:
    mywms:
      type: wms
      req:
        url: http://example.com/service?
        layers: base
      coverage:
        bbox: [5, 50, 10, 55]
        bbox_srs: 'EPSG:4326'


mapproxy-seed
"""""""""""""

To define a seed-area in the ``seed.yaml``, add the coverage directly to the view.

::

  views:
    germany:
      ogr_datasource: 'shps/world_boundaries_m.shp'
      ogr_where: 'CNTRY_NAME = "Germany"'
      ogr_srs: 'EPSG:900913'
      level: [0, 14]
      srs: ['EPSG:900913', 'EPSG:4326']

.. index:: PostGIS, PostgreSQL

And here is the same example with a PostGIS source::

  views:
    germany:
      ogr_datasource: "PG: dbname='db' host='host' user='user'
    password='password'"
      ogr_where: "select * from coverages where country='germany'"
      ogr_srs: 'EPSG:900913'
      level: [0, 14]
      srs: ['EPSG:900913', 'EPSG:4326']

