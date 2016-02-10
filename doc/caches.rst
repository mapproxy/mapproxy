Caches
######

.. versionadded:: 1.2.0

MapProxy supports multiple backends to store the internal tiles. The default backend is file based and does not require any further configuration.

Configuration
=============

You can configure a backend for each cache with the ``cache`` option.
Each backend has a ``type`` and one or more options.

::

  caches:
    mycache:
      sources: [...]
      grids: [...]
      cache:
        type: backendtype
        backendoption1: value
        backendoption2: value


The following backend types are available.

``file``
========

This is the default cache type and it uses a single file for each tile. Available options are:

``directory_layout``:
  The directory layout MapProxy uses to store tiles on disk. Defaults to ``tc`` which uses a TileCache compatible directory layout (``zz/xxx/xxx/xxx/yyy/yyy/yyy.format``). ``mp`` uses a directory layout with less nesting (``zz/xxxx/xxxx/yyyy/yyyy.format```). ``tms`` uses TMS compatible directories (``zz/xxxx/yyyy.format``). ``quadkey`` uses Microsoft Virtual Earth or quadkey compatible directories (see http://msdn.microsoft.com/en-us/library/bb259689.aspx). ``arcgis`` uses a directory layout with hexadecimal row and column numbers that is compatible to ArcGIS exploded caches (``Lzz/Rxxxxxxxx/Cyyyyyyyy.format``).

  .. note::
    ``tms``, ``quadkey`` and ``arcgis`` layout are not suited for large caches, since it will create directories with thousands of files, which most file systems do not handle well.

``use_grid_names``:
  When ``true`` MapProxy will use the actual grid name in the path instead of the SRS code. E.g. tiles will be stored in ``./cache_data/mylayer/mygrid/`` instead of ``./cache_data/mylayer/EPSG1234/``.

  .. versionadded:: 1.5.0

.. _cache_file_directory:

``directory``:
  Directory where MapProxy should directly store the tiles. This will not add the cache name or grid name (``use_grid_name``) to the path. You can use this option to point MapProxy to an existing tile collection (created with ``gdal2tiles`` for example).

  .. versionadded:: 1.5.0

``tile_lock_dir``:
  Directory where MapProxy should write lock files when it creates new tiles for this cache. Defaults to ``cache_data/tile_locks``.

  .. versionadded:: 1.6.0


``mbtiles``
===========

Use a single SQLite file for this cache. It uses the `MBTile specification <http://mbtiles.org/>`_.

Available options:

``filename``:
  The path to the MBTiles file. Defaults to ``cachename.mbtiles``.

``tile_lock_dir``:
  Directory where MapProxy should write lock files when it creates new tiles for this cache. Defaults to ``cache_data/tile_locks``.

  .. versionadded:: 1.6.0


You can set the ``sources`` to an empty list, if you use an existing MBTiles file and do not have a source.

::

  caches:
    mbtiles_cache:
      sources: []
      grids: [GLOBAL_MERCATOR]
      cache:
        type: mbtiles
        filename: /path/to/bluemarble.mbtiles

.. note::

  The MBTiles format specification does not include any timestamps for each tile and the seeding function is limited therefore. If you include any ``refresh_before`` time in a seed task, all tiles will be recreated regardless of the value. The cleanup process does not support any ``remove_before`` times for MBTiles and it always removes all tiles.
  Use the ``--summary`` option of the ``mapproxy-seed`` tool.

``sqlite``
===========

.. versionadded:: 1.6.0

Use SQLite databases to store the tiles, similar to ``mbtiles`` cache. The difference to ``mbtiles`` cache is that the ``sqlite`` cache stores each level into a separate databse. This makes it easy to remove complete levels during mapproxy-seed cleanup processes. The ``sqlite`` cache also stores the timestamp of each tile.

Available options:

``dirname``:
  The direcotry where the level databases will be stored.

``tile_lock_dir``:
  Directory where MapProxy should write lock files when it creates new tiles for this cache. Defaults to ``cache_data/tile_locks``.

  .. versionadded:: 1.6.0

::

  caches:
    sqlite_cache:
      sources: [mywms]
      grids: [GLOBAL_MERCATOR]
      cache:
        type: sqlite
        directory: /path/to/cache


``couchdb``
===========

.. versionadded:: 1.3.0

Store tiles inside a `CouchDB <http://couchdb.apache.org/>`_. MapProxy creates a JSON document for each tile. This document contains metadata, like timestamps, and the tile image itself as a attachment.


Requirements
------------

Besides a running CouchDB you will need the `Python requests package <http://python-requests.org/>`_. You can install it the usual way, for example ``pip install requests``.

Configuration
-------------

You can configure the database and database name and the tile ID and additional metadata.

Available options:

``url``:
  The URL of the CouchDB server. Defaults to ``http://localhost:5984``.

``db_name``:
  The name of the database MapProxy uses for this cache. Defaults to the name of the cache.

``tile_lock_dir``:
  Directory where MapProxy should write lock files when it creates new tiles for this cache. Defaults to ``cache_data/tile_locks``.

  .. versionadded:: 1.6.0

``tile_id``:
  Each tile document needs a unique ID. You can change the format with a Python format string that expects the following keys:

  ``x``, ``y``, ``z``:
    The tile coordinate.

  ``grid_name``:
    The name of the grid.

  The default ID uses the following format::

    %(grid_name)s-%(z)d-%(x)d-%(y)d

  .. note:: You can't use slashes (``/``) in CouchDB IDs.

``tile_metadata``:
  MapProxy stores a JSON document for each tile in CouchDB and you can add additional key-value pairs  with metadata to each document.
  There are a few predefined values that MapProxy will replace with  tile-depended values, all other values will be added as they are.

  Predefined values:

  ``{{x}}``, ``{{y}}``, ``{{z}}``:
    The tile coordinate.

  ``{{timestamp}}``:
    The creation time of the tile as seconds since epoch. MapProxy will add a ``timestamp`` key for you, if you don't provide a custom timestamp key.

  ``{{utc_iso}}``:
    The creation time of the tile in UTC in ISO format. For example: ``2011-12-31T23:59:59Z``.

  ``{{tile_centroid}}``:
    The center coordinate of the tile in the cache's coordinate system as a list of long/lat or x/y values.

  ``{{wgs_tile_centroid}}``:
    The center coordinate of the tile in WGS 84 as a list of long/lat values.

Example
-------

::

  caches:
    mycouchdbcache:
      sources: [mywms]
      grids: [mygrid]
      cache:
        type: couchdb
        url: http://localhost:9999
        db_name: mywms_tiles
        tile_metadata:
          mydata: myvalue
          tile_col: '{{x}}'
          tile_row: '{{y}}'
          tile_level: '{{z}}'
          created_ts: '{{timestamp}}'
          created: '{{utc_iso}}'
          center: '{{wgs_tile_centroid}}'



MapProxy will place the JSON document for tile z=3, x=1, y=2 at ``http://localhost:9999/mywms_tiles/mygrid-3-1-2``. The document will look like::

  {
      "_attachments": {
          "tile": {
              "content_type": "image/png",
              "digest": "md5-ch4j5Piov6a5FlAZtwPVhQ==",
              "length": 921,
              "revpos": 2,
              "stub": true
          }
      },
      "_id": "mygrid-3-1-2",
      "_rev": "2-9932acafd060e10bc0db23231574f933",
      "center": [
          -112.5,
          -55.7765730186677
      ],
      "created": "2011-12-15T12:56:21Z",
      "created_ts": 1323953781.531889,
      "mydata": "myvalue",
      "tile_col": 1,
      "tile_level": 3,
      "tile_row": 2
  }


The ``_attachments``-part is the internal structure of CouchDB where the tile itself is stored. You can access the tile directly at: ``http://localhost:9999/mywms_tiles/mygrid-3-1-2/tile``.


``riak``
========

.. versionadded:: 1.6.0

Store tiles in a `Riak <http://basho.com/riak/>`_ cluster. MapProxy creates keys with binary data as value and timestamps as user defined metadata.
This backend is good for very large caches which can be distributed over many nodes. Data can be distributed over multiple nodes providing a fault-tolernt and high-available storage. A Riak cluster is masterless and each node can handle read and write requests.

Requirements
------------

You will need the `Python Riak client <https://pypi.python.org/pypi/riak>`_ version 2.0 or newer. You can install it in the usual way, for example with ``pip install riak``. Environments with older version must be upgraded with ``pip install -U riak``.

Configuration
-------------

Available options:

``nodes``:
    A list of riak nodes. Each node needs a ``host`` and optionally a ``pb_port`` and an ``http_port`` if the ports differ from the default. A single localhost node is used if you don't configure any nodes.

``protocol``:
    Communication protocol. Allowed options is ``http``, ``https`` and ``pbc``. Defaults to ``pbc``.

``bucket``:
    The name of the bucket MapProxy uses for this cache. The bucket is the namespace for the tiles and needs to be unique for each cache. Defaults to cache name suffixed with grid name (e.g. ``mycache_webmercator``).

``default_ports``:
    Default ``pb`` and ``http`` ports for ``pbc`` and ``http`` protocols. Will be used as the default for each defined node.

``secondary_index``:
    If ``true`` enables secondary index for tiles. This improves seed cleanup performance but requires that Riak uses LevelDB as the backend. Refer to the Riak documentation. Defaults to ``false``.

Example
-------

::

    myriakcache:
        sources: [mywms]
        grids: [mygrid]
        type: riak
        nodes:
            - host: 1.example.org
              pb_port: 9999
            - host: 1.example.org
            - host: 1.example.org
        protocol: pbc
        bucket: myriakcachetiles
        default_ports:
            pb: 8087
            http: 8098
