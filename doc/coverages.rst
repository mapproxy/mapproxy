.. _coverages:

Coverages
=========

With coverages you can define areas where data is available or where data you are interested in is.
MapProxy supports coverages for :doc:`sources <sources>` and in the :doc:`mapproxy-seed tool <seed>`. Refer to the corresponding section in the documentation.


There are three different ways to describe a coverage.

- a simple rectangular bounding box,
- a text file with one or more (multi)polygons in WKT format,
- (multi)polygons from any data source readable with OGR (e.g. Shapefile, GeoJSON, PostGIS)


Requirements
------------

If you want to use polygons to define a coverage, instead of simple bounding boxes, you will also need Shapely and GEOS. For loading polygons from shapefiles you'll also need GDAL/OGR.

MapProxy requires Shapely 1.2.0 or later and GEOS 3.1.0 or later.

On Debian::

  sudo aptitude install libgeos-dev libgdal-dev
  pip install Shapely


Configuration
-------------

All coverages are configured by defining the source of the coverage and the SRS.
The configuration of the coverage depends on the type. The SRS can allways be configured with the ``srs`` option.

.. versionadded:: 1.5.0
    MapProxy can autodetect the type of the coverage. You can now use ``coverage`` instead of the ``bbox``, ``polygons`` or ``ogr_datasource`` option.
    The old options are still supported.

Coverage Types
--------------

Bounding box
""""""""""""

For simple box coverages.

``bbox`` or ``datasource``:
    A simple BBOX as a list, e.g: `[4, -30, 10, -28]` or as a string `4,-30,10,-28`.

Polygon file
""""""""""""

Text files with one WKT polygon or multi-polygon per line.
You can create your own files or use `one of the files we provide for every country <http://mapproxy.org/static/polygons/>`_. Read `the index <http://mapproxy.org/static/polygons/0-fips-codes.txt>`_ to find your country.

``datasource``:
 The path to the polygon file. Should be relative to the proxy configuration or absolute.

OGR datasource
""""""""""""""

Any polygon datasource that is supported by OGR (e.g. Shapefile, GeoJSON, PostGIS).


``datasource``:
  The name of the datasource. Refer to the `OGR format page
  <http://www.gdal.org/ogr/ogr_formats.html>`_ for a list of all supported
  datasources. File paths should be relative to the proxy configuration or absolute.

``where``:
  Restrict which polygons should be loaded from the datasource. Either a simple where
  statement (e.g. ``'CNTRY_NAME="Germany"'``) or a full select statement. Refer to the
  `OGR SQL support documentation <http://www.gdal.org/ogr/ogr_sql.html>`_. If this
  option is unset, the first layer from the datasource will be used.


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
        srs: 'EPSG:4326'


mapproxy-seed
"""""""""""""

To define a seed-area in the ``seed.yaml``, add the coverage directly to the view.

::

  coverages:
    germany:
      datasource: 'shps/world_boundaries_m.shp'
      where: 'CNTRY_NAME = "Germany"'
      srs: 'EPSG:900913'

.. index:: PostGIS, PostgreSQL

Here is the same example with a PostGIS source::

  coverages:
    germany:
      datasource: "PG: dbname='db' host='host' user='user'
    password='password'"
      where: "select * from coverages where country='germany'"
      srs: 'EPSG:900913'


.. index:: GeoJSON

And here is an example with a GeoJSON source::

  coverages:
    germany:
      datasource: 'boundary.geojson'
      srs: 'EPSG:4326'

See `the OGR driver list <http://www.gdal.org/ogr/ogr_formats.html>`_ for all supported formats.
