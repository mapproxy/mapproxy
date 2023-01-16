Seeding
=======

Introduction
------------

The MapProxy creates all tiles on demand. To improve the performance for commonly
requested areas it is possible to pre-generate these tiles. The ``mapproxy-seed`` script does this task.

The tool can seed one or more polygon or BBOX areas for each cache. It can seed missing tiles and refresh old tiles. A `cleanup` can be used to remove old tiles.


.. _seed_method:

Method
~~~~~~

MapProxy does not seed the tile pyramid level by level, but traverses the tile pyramid depth-first. It starts in the first zoom level and decides if the tiles in the next zoom level need to be seeded by checking each subtile for intersection with the coverage. It recursively repeats this step for all tiles below till it reaches the last zoom level to seed. Only then, before getting back to the parent tile, the tile is actually seeded.

The following shows in which order tiles are seeded for a simple cache with three levels::

    Level 0 with 1 tile:

              21

    Level 1 with 4 tiles:

             5  10
            15  20

    Level 2 with 16 tiles:

          1  2  6  7
          3  4  8  9
         11 12 16 17
         13 14 18 19


This method is optimized to work `with` the caches of your operating system and geospatial database, as the same area is requested for multiple scales in direct succession.

It also makes checks against complex coverages efficient as subtiles can be rejected early on.

mapproxy-seed
-------------

The command line script expects a seed configuration that describes which tiles from which layer should be generated. See `configuration`_ for the format of the file.


Options
~~~~~~~


.. option:: -s <seed.yaml>, --seed-conf==<seed.yaml>

  The seed configuration. You can also pass the configuration as the last argument to ``mapproxy-seed``

.. option:: -f <mapproxy.yaml>, --proxy-conf=<mapproxy.yaml>

  The MapProxy configuration to use. This file should describe all caches and grids that the seed configuration references.

.. option:: -c N, --concurrency N

  The number of concurrent seed worker. Some parts of the seed tool are CPU intensive
  (image splitting and encoding), use this option to distribute that load across multiple
  CPUs. To limit the concurrent requests to the source WMS see
  :ref:`wms_source_concurrent_requests_label`

.. option:: -n, --dry-run

  This will simulate the seed/cleanup process without requesting, creating or removing any tiles.

.. option:: --summary

  Print a summary of all seeding and cleanup tasks and exit.

.. option:: --quiet

  Reduce the output of the progress logger.

.. option:: -i, --interactive

  Print a summary of each seeding and cleanup task and ask if ``mapproxy-seed`` should seed/cleanup that task. It will query for each task before it starts.

.. option:: --seed=<task1,task2,..>

  Only seed the named seeding tasks. You can select multiple tasks with a list of comma seperated names, or you can use the ``--seed`` option multiple times.
  You can use ``ALL`` to select all tasks.
  This disables all cleanup tasks unless you also use the ``--cleanup`` option.

.. option:: --cleanup=<task1,task2,..>

  Only cleanup the named tasks. You can select multiple tasks with a list of comma seperated names, or you can use the ``--cleanup`` option multiple times.
  You can use ``ALL`` to select all tasks.
  This disables all seeding tasks unless you also use the ``--seed`` option.


.. option:: --continue

  Continue an interrupted seed progress. MapProxy will start the seeding progress at the begining if the progress file (``--progress-file``) was not found.  MapProxy can only continue if the previous seed was started with the ``--progress-file`` or ``--continue`` option.

.. option:: --progress-file

  Filename where MapProxy stores the seeding progress for the ``--continue`` option. Defaults to ``.mapproxy_seed_progress`` in the current working directory. MapProxy will remove that file after a successful seed.

.. option:: --duration

  Stop seeding process after this duration. This option accepts duration in the following format: 120s, 15m, 4h, 0.5d
  Use this option in combination with ``--continue`` to be able to resume the seeding. Works only on Linux and Unix systems.

.. option:: --reseed-file

  File created by ``mapproxy-seed`` at the start of a new seeding.

.. option:: --reseed-interval

  Only start seeding if ``--reseed-file`` is older then this duration.
  This option accepts duration in the following format: 120s, 15m, 4h, 0.5d
  Use this option in combination with ``--continue`` to be able to resume the seeding. By default,

.. option:: --use-cache-lock

  Lock each cache to prevent multiple parallel `mapproxy-seed` calls to work on the same cache.
  It does not lock normal operation of MapProxy.

.. option:: --log-config

  The logging configuration file to use.

.. versionadded:: 1.5.0
  ``--continue`` and ``--progress-file`` option

.. versionadded:: 1.7.0
  ``--log-config`` option

.. versionadded:: 1.10.0
  ``--duration``, ``--reseed-file`` and ``--reseed-interval`` option




Examples
~~~~~~~~

Seed with concurrency of 4::

    mapproxy-seed -f mapproxy.yaml -c 4 seed.yaml

Print summary of all seed tasks and exit::

    mapproxy-seed -f mapproxy.yaml -s seed.yaml --summary --seed ALL

Interactively select which tasks should be seeded::

    mapproxy-seed -f mapproxy.yaml -s seed.yaml -i

Seed task1 and task2 and cleanup task3 with concurrency of 2::

    mapproxy-seed -f mapproxy.yaml -s seed.yaml -c 2 --seed task1,task2 \
     --cleanup task3



Configuration
-------------

.. note:: The configuration changed with MapProxy 1.0.0, the old format with ``seeds`` and ``views`` is still supported but will be deprecated in the future. See :ref:`below <seed_old_configuration>` for information about the old format.


The configuration is a YAML file with three sections:

``seeds``
  Configure seeding tasks.

``cleanups``
  Configure cleanup tasks.

``coverages``
  Configure coverages for seeding and cleanup tasks.

Example
~~~~~~~

::

  seeds:
    myseed1:
      [...]
    myseed2
      [...]

  cleanups:
    mycleanup1:
      [...]
    mycleanup2:
      [...]

  coverages:
    mycoverage1:
      [...]
    mycoverage2:
      [...]


``seeds``
---------

Here you can define multiple seeding tasks. A task defines *what* should be seeded. Each task is configured as a dictionary with the name of the task as the key. You can use the names to select single tasks on the command line of ``mapproxy-seed``.

``mapproxy-seed`` will always process one tile pyramid after the other. Each tile pyramid is defined by a cache and a corresponding grid. A cache with multiple grids consists of multiple tile pyramids. You can configure which tile pyramid you want to seed with the ``caches`` and ``grids`` options.

You can further limit the part of the tile pyramid with the ``levels`` and ``coverages`` options.

Each seed tasks takes the following options:

``caches``
~~~~~~~~~~

A list with the caches that should be seeded for this task. The names should match the cache names in your MapProxy configuration.

``grids``
~~~~~~~~~
A list with the grid names that should be seeded for the ``caches``.
The names should match the grid names in your MapProxy configuration.
All caches of this tasks need to support the grids you specify here.
By default, the grids that are common to all configured caches will be seeded.

``levels``
~~~~~~~~~~
Either a list of levels that should be seeded, or a dictionary with ``from`` and ``to`` that define a range of levels. You can omit ``from`` to start at level 0, or you can omit ``to`` to seed till the last level.
By default, all levels will be seeded.

Examples::

  # seed multiple levels
  levels: [2, 3, 4, 8, 9]

  # seed a single level
  levels: [3]

  # seed from level 0 to 10 (including level 10)
  levels:
    to: 10

  # seed from level 3 to 6 (including level 3 and 6)
  levels:
    from: 3
    to: 6

``coverages``
~~~~~~~~~~~~~

A list with coverage names. Limits the seed area to the coverages. By default, the whole coverage of the grids will be seeded.

``refresh_before``
~~~~~~~~~~~~~~~~~~

Regenerate all tiles that are older than the given date. The date can either be absolute or relative. By default, existing tiles will not be refreshed.

MapProxy can also use the last modification time of a file. File paths should be relative to the proxy configuration or absolute.

Examples::

  # absolute as ISO time
  refresh_before:
    time: 2010-10-21T12:35:00

  # relative from the start time of the seed process
  refresh_before:
    weeks: 1
    days: 7
    hours: 4
    minutes: 15

  # modification time of a given file
  refresh_before:
    mtime: path/to/file



Example
~~~~~~~~

::

  seeds:
    myseed1:
      caches: [osm_cache]
      coverages: [germany]
      grids: [GLOBAL_MERCATOR]
      levels:
        to: 10

    myseed2
      caches: [osm_cache]
      coverages: [niedersachsen, bremen, hamburg]
      grids: [GLOBAL_MERCATOR]
      refresh_before:
        weeks: 3
      levels:
        from: 11
        to: 15

``cleanups``
------------

Here you can define multiple cleanup tasks. Each task is configured as a dictionary with the name of the task as the key. You can use the names to select single tasks on the command line of ``mapproxy-seed``.

``caches``
~~~~~~~~~~

A list with the caches where you want to cleanup old tiles. The names should match the cache names in your MapProxy configuration.

``grids``
~~~~~~~~~
A list with the grid names for the ``caches`` where you want to cleanup.
The names should match the grid names in your MapProxy configuration.
All caches of this tasks need to support the grids you specify here.
By default, the grids that are common to all configured caches will be used.

``levels``
~~~~~~~~~~
Either a list of levels that should be cleaned up, or a dictionary with ``from`` and ``to`` that define a range of levels. You can omit ``from`` to start at level 0, or you can omit ``to`` to cleanup till the last level.
By default, all levels will be cleaned up.

Examples::

  # cleanup multiple levels
  levels: [2, 3, 4, 8, 9]

  # cleanup a single level
  levels: [3]

  # cleanup from level 0 to 10 (including level 10)
  levels:
    to: 10

  # cleanup from level 3 to 6 (including level 3 and 6)
  levels:
    from: 3
    to: 6

``coverages``
~~~~~~~~~~~~~

A list with coverage names. Limits the cleanup area to the coverages. By default, the whole coverage of the grids will be cleaned up.

.. note:: Be careful when cleaning up caches with large coverages and levels with lots of tiles (>14).
  Without ``coverages``, the seed tool works on the file system level and it only needs to check for existing tiles if they should be removed. With ``coverages``, the seed tool traverses the whole tile pyramid and needs to check every posible tile if it exists and if it should be removed. This is much slower.

``remove_all``
~~~~~~~~~~~~~~

When set to true, remove all tiles regardless of the time they were created. You still limit the tiles with the ``levels`` and ``coverage`` options. MapProxy will try to remove tiles in a more efficient way with this option. For example: It will remove complete level directories for ``file`` caches instead of comparing each tile with a timestamp.

``remove_before``
~~~~~~~~~~~~~~~~~

Remove all tiles that are older than the given date. The date can either be absolute or relative. ``remove_before`` defaults to the start time of the seed process, so that newly created tile will not be removed.

MapProxy can also use the last modification time of a file. File paths should be relative to the proxy configuration or absolute.

Examples::

  # absolute as ISO time
  remove_before:
    time: 2010-10-21T12:35:00

  # relative from the start time of the seed process
  remove_before:
    weeks: 1
    days: 7
    hours: 4
    minutes: 15

  # modification time of a given file
  remove_before:
    mtime: path/to/file



Example
~~~~~~~~

::

  cleanups:
    highres:
      caches: [osm_cache]
      grids: [GLOBAL_MERCATOR, GLOBAL_SPERICAL]
      remove_before:
        days: 14
      levels:
        from: 16
    old_project:
      caches: [osm_cache]
      grids: [GLOBAL_MERCATOR]
      coverages: [mypolygon]
      levels:
        from: 14
        to: 18



``coverages``
-------------

There are three different ways to describe the extent of a seeding or cleanup task.

- a simple rectangular bounding box,
- a text file with one or more polygons in WKT format,
- polygons from any data source readable with OGR (e.g. Shapefile, GeoJSON, PostGIS)

Read the :doc:`coverage documentation <coverages>` for more information.

.. note:: You will need to install additional dependencies, if you want to use polygons to define your geographical extent of the seeding area, instead of simple bounding boxes. See :doc:`coverage documentation <coverages>`.

Each coverage has a name that is used in the seed and cleanup task configuration. If you don't specify a coverage for a task, then the BBOX of the grid will be used.



Example
~~~~~~~

::

  coverages:
    germany:
      datasource: 'shps/world_boundaries_m.shp'
      where: 'CNTRY_NAME = "Germany"'
      srs: 'EPSG:900913'
    switzerland:
      datasource: 'polygons/SZ.txt'
      srs: 'EPSG:900913'
    austria:
      bbox: [9.36, 46.33, 17.28, 49.09]
      srs: 'EPSG:4326'



Output
------

``mapproxy-seed`` prints out the progress of the current seeding task on the console.

Example progress log::

    [16:48:26]  4  41.00% 582388, 4734701, 586740, 4737666 (5812 tiles)


The output starts with the current time and ends with the number of tiles it has seeded or removed so far. The third value is the current progress in percent. The progress can make large jumps, if the seeding detects that a tile and all its subtiles are outside of the seeding coverage.
The second and fourth value show the level and bounding box of where the seeding tool is in this moment. Keep in mind, that it does not seed level by level. This is described in :ref:`seeding method <seed_method>`.



.. _background_seeding:

Example: Background seeding
---------------------------

.. versionadded:: 1.10.0 Works on Linux and Unix only

The ``--duration`` option allows you run MapProxy seeding for a limited time. In combination with the ``--continue`` option, you can resume the seeding process at a later time.
You can use this to call ``mapproxy-seed`` with ``cron`` to seed in the off-hours.

However, this will restart the seeding process from the beginning every time the is seeding completed.
You can prevent this with the ``--reeseed-interval`` and ``--reseed-file`` option.
The following example starts seeding for six hours. It will seed for another six hours, every time you call this command again. Once all seed and cleanup tasks were processed the command will exit immediately every time you call it within 14 days after the first call. After 14 days, the modification time of the ``reseed.time`` file will be updated and the re-seeding process starts again.

::

  mapproxy-seed -f mapproxy.yaml -s seed.yaml  \
    --reseed-interval 14d --duration 6h --reseed-file reseed.time \
    --continue --progress-file .mapproxy_seed_progress

You can use the ``--reseed-file`` as a ``refresh_before`` and ``remove_before`` ``mtime``-file.



.. _seed_old_configuration:

Old Configuration
-----------------

.. note:: The following description is for the old seed configuration.

The configuration contains two keys: ``views`` and ``seeds``. ``views`` describes
the geographical extents that should be seeded. ``seeds`` links actual layers with
those ``views``.


Seeds
~~~~~

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
    `seconds`, `minutes`, `hours`, `days` or `weeks` entries.

Views
~~~~~

Contains a dictionary with all views. Each view describes a coverage/geographical extent and the levels that should be seeded.

Coverages
^^^^^^^^^

.. note:: You will need to install additional dependencies, if you want to use polygons to define your geographical extent of the seeding area, instead of simple bounding boxes. See :doc:`coverage documentation <coverages>`.


There are three different ways to describe the extent of the seed view.

 - a simple rectangular bounding box,
 - a text file with one or more polygons in WKT format,
 - polygons from any data source readable with OGR (e.g. Shapefile, PostGIS)

Read the :doc:`coverage documentation <coverages>` for more information.

Other options
~~~~~~~~~~~~~

``srs``:
    A list with SRSs. If the layer contains caches for multiple SRS, only the caches
    that match one of the SRS in this list will be seeded.

``res``:
    Seed until this resolution is cached.

or

``level``:
    A number until which this layer is cached, or a tuple with a range of
    levels that should be cached.

Example configuration
^^^^^^^^^^^^^^^^^^^^^

::

  views:
    germany:
      datasource: 'shps/world_boundaries_m.shp'
      where: 'CNTRY_NAME = "Germany"'
      srs: 'EPSG:900913'
      level: [0, 14]
      srs: ['EPSG:900913', 'EPSG:4326']
    switzerland:
      datasource: 'polygons/SZ.txt'
      srs: EPSG:900913
      level: [0, 14]
      srs: ['EPSG:900913']
    austria:
      bbox: [9.36, 46.33, 17.28, 49.09]
      srs: EPSG:4326
      level: [0, 14]
      srs: ['EPSG:900913']

  seeds:
    osm:
      views: ['germany', 'switzerland', 'austria']
      remove_before:
        time: '2010-02-20T16:00:00'
    osm_roads:
      views: ['germany']
      remove_before:
        days: 30
