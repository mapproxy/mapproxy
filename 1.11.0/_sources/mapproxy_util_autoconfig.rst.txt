.. _mapproxy_util_autoconfig:

########################
mapproxy-util autoconfig
########################


The ``autoconfig`` sub-command of ``mapproxy-util`` creates MapProxy and MapProxy-seeding configurations based on existing WMS capabilities documents.

It creates a ``source`` for each available layer. The source will include a BBOX coverage from the layer extent, ``legendurl`` for legend graphics, ``featureinfo`` for querlyable layers, scale hints and all detected ``supported_srs``. It will duplicate the layer tree to the ``layers`` section of the MapProxy configuration, including the name, title and abstract.

The tool will create a cache for each source layer and ``supported_srs`` _if_ there is a grid configured in your ``--base`` configuration for that SRS.

The MapProxy layers will use the caches when available, otherwise they will use the source directly (cascaded WMS).

.. note:: The tool can help you to create new configations, but it can't predict how you will use the MapProxy services.
    The generated configuration can be highly inefficient, especially when multiple layers with separate caches are requested at once.
    Please make sure you understand the configuration and check the documentation for more options that are useful for your use-cases.


Options
=======


.. program:: mapproxy-util autoconfig

.. cmdoption:: --capabilities <url|filename>

  URL or filename of the WMS capabilities document. The tool will add `REQUEST` and `SERVICE` parameters to the URL as necessary.

.. cmdoption:: --output <filename>

  Filename for the created MapProxy configuration.

.. cmdoption:: --output-seed <filename>

  Filename for the created MapProxy-seeding configuration.

.. cmdoption:: --force

  Overwrite any existing configuration with the same output filename.



.. cmdoption:: --base <filename>

  Base configuration that should be included in the ``--output`` file with the ``base`` option.

.. cmdoption:: --overwrite <filename>
.. cmdoption:: --overwrite-seed <filename>

  YAML configuration that overwrites configuration optoins before the generated configuration is written to ``--output``/``--output-seed``.

Example
~~~~~~~

Print configuration on console::

    mapproxy-util autoconfig \
        --capabilities http://osm.omniscale.net/proxy/service

Write MapProxy and MapProxy-seeding configuration to files::

    mapproxy-util autoconfig \
        --capabilities http://osm.omniscale.net/proxy/service \
        --output mapproxy.yaml \
        --output-seed seed.yaml

Write MapProxy configuration with caches for grids from ``base.yaml``::

    mapproxy-util autoconfig \
        --capabilities http://osm.omniscale.net/proxy/service \
        --output mapproxy.yaml \
        --base base.yaml



Overwrites
==========

It's likely that you need to tweak the created configuration – e.g. to define another coverage, disable featureinfo, etc. You can do this by editing the output file of course, or you can modify the output by defining all changes to an overwrite file. Overwrite files are applied everytime you call ``mapproxy-util autoconfig``.

Overwrites are YAML files that will be merged with the created configuration file.

The overwrites are applied independently for each ``services``, ``sources``, ``caches`` and ``layers`` section. That means, for example, that you can modify the ``supported_srs`` of a source and the tool will use the updated SRS list to decide which caches will be configured for that source.

Example
~~~~~~~

Created configuration::

    sources:
      mysource_wms:
        type: wms
        req:
            url: http://example.org
            layers: a

Overwrite file::

    sources:
      mysource_wms:
        supported_srs: ['EPSG:4326'] # add new value for mysource_wms
        req:
            layers: a,b  # overwrite existing value
            custom_param: 42  #  new value

Actual configuration written to ``--output``::

    sources:
      mysource_wms:
        type: wms
        supported_srs: ['EPSG:4326']
        req:
            url: http://example.org
            layers: a,b
            custom_param: 42


Special keys
~~~~~~~~~~~~

There are a few special keys that you can use in your overwrite file.


All
^^^

The value of the ``__all__`` key will be merged into all dictionaries. The following overwrite will add ``sessionid`` to the ``req`` options of all ``sources``::

    sources:
      __all__:
        req:
          sessionid: 123456789


Extend
^^^^^^

The values of keys ending with ``__extend__`` will be added to existing lists.

To add another SRS for one source::

    sources:
        my_wms:
          supported_srs__extend__: ['EPSG:31467']


Wildcard
^^^^^^^^

The values of keys starting or ending with three underscores (``___``) will be merged with values where the key matches the suffix or prefix.

For example, to set ``levels`` for ``osm_webmercator`` and ``aerial_webmercator`` and to set ``refresh_before`` for ``osm_webmercator`` and ``osm_utm32``::

    seeds:
        ____webmercator:
            levels:
              from: 0
              to: 12

        osm____:
            refresh_before:
                days: 5

