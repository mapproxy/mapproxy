Seeding
=======

The MapProxy creates all tiles on demand. To improve the performance for commonly
requested views it is possible to pre-generate these tiles. The ``proxy_seed`` script does
this task.

proxy_seed
----------

The command line script expects a seed configuration that describes which tiles from which layer should be generated. See `seed configuration`_ for the format of the file.

Use the ``-f`` option to specify the proxy configuration.
::

    proxy_seed -f etc/proxy.yaml etc/seed.yaml


rebuild
^^^^^^^

The script checks if the requested tiles are present. If they are not cached, they will be
created. If the seed is configured with an ``remove_before`` date, the tile will be
recreated if it is older.

If you want to rebuild the cache, you can use the ``-r`` (``--rebuild``) option. It will
rebuild level per level. It first creates the new tiles for this level, then changes the
old ones with the new tiles and only removes the old tiles afterwards. That way the cache
is always present. The rebuild level will contain an ``last_seed`` file with the
time-stamp of the last rebuild. If there is a `remove_before` date configured, the level
will only be rebuild if the ``last_seed`` file is older than the date.


Seed configuration
------------------

The configuration contains two keys: ``views`` and ``seeds``. ``views`` describes
geographical extends that should be seeded. ``seeds`` links actual layers with
those ``views``.


``seeds``
^^^^^^^^^

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
    If present, recreate tiles if they are older than the date or time delta. Also, tiles
    that are older will be removed. If you use the ``--rebuild`` option, the level will
    only be recreated if the ``last_seed`` file in the level directory is older. If there
    is no such file, the level will be rebuilt.
    
    You can either define a fixed time or a time delta. The `time` is a ISO-like date
    string (no time-zones, no abbreviations). To define time delta use one or more
    `minutes`, `hours`, `days`, `weeks` entries.

``views``
^^^^^^^^^^

Contains a dictionary with all views. Each view describes a geographical extend.

``bbox``:
    The BBOX that should be cached. If omitted, the whole BBOX of the layer is used.

``bbox_srs``:
    The SRS of the BBOX. If omitted the SRS of the first layer cache is used.

``srs``:
    A list with SRS. If the layer contains caches for multiple SRS, only the caches
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