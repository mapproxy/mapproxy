Tutorial
########

This tutorial should give you a quick introduction to the MapProxy configuration.


The MapProxy itself is configured with a single configuration.


Configuration format
====================

MapProxy uses the YAML format. YAML is a superset of JSON. That means every valid JSON is also valid YAML. MapProxy uses no advanced features of YAML, so you could even use JSON.
YAML uses a more readable and user-friendly syntax. We encourage you to use it.

If you are familiar with YAML you can skip the next section. 

The YAML configuration consist of comments, dictionaries, lists, strings, numbers and booleans.

Comments
--------
Everything after a pound character (``#``) is a comment and will be ignored.

Numbers
-------
Any numerical value like ``12``, ``-4``, ``0``, and ``3.1415``.

Strings
-------
Any string within single or double quotes. You can omit the quotes if the string has no other meaning in YAML syntax. For example::
  
    'foo'
    foo
    '43' # with quotes, otherwise it would be numeric
    '[string, not a list]'
    A string with spaces and punctuation.

Booleans
--------
True or false values::
  
    yes
    true
    True
    no
    false
    False
    

List
----
A list is a collection of other valid objects. There are two formats. The condensed form uses square brackets::
  
    [1, 2, 3]
    [42, string, [another list with a string]]
  
The block form starts requires every list item on a separate line, starting with a ``-`` character::
  
    - 1
    - 2
    - 3
    
    - 42
    - string
    - [another list]

Dictionaries
------------
A dictionary maps keys to values. Values itself can be any valid object.
You can also nest dictionaries.
::
  
    foo: 3
    bar: baz
    baz:
      ham: 2
      spam: 4


Configuration Layout
====================

The MapProxy configuration is a dictionay, each key configures a different aspect of MapProxy. There are the following keys:

- ``globals``:  Here you can define some internals of MapProxy and default values that are used in the other configuration directives.
  
- ``services``:
  This is the place to activate and configure MapProxy's services like WMS and TMS.

- ``sources``: Define where MapProxy can retrieve new data.

- ``caches``: Here you can configure the internal caches.

- ``layers``: Configure the layers that MapProxy offers. Each layer can consist of multiple sources and caches.
  
- ``grids``: MapProxy aligns all cached images to a grid. Here you can define that grid.
  
The order of the directives is not important, so you can organize it your way.

.. At first it seams a bit complex, but after you have configured you first MapProxy it all should become clear.



Example Configuration
=====================




Configuring a Service
---------------------

At first we need to configure at least one service. To enable a service, you have to include its name as a key in the `services` dictionary. For example::

  service:
    wms:


Each service is a YAML dictionary, with the service type as the key. The dictionary can be empty, but you need to add the colon so that the configuration parser knows it's a dictionary.


A service might accept more configuration options. The WMS service, for example, takes a dictionary with metadata. These data is used in the capabilities documents.

Here is an example with some contact information:

.. literalinclude:: tutorial.yaml
  :end-before: #end service

`access_constraints` demonstrates how you can write a string over multiple lines, just indent every line the same way as the first. And remember, YAML does not accept tab characters, you must use space.

Adding a Source
----------------

Next you need to define the source of your data. Every source has a name and a type. Lets add a WMS source:

.. literalinclude:: tutorial.yaml
  :start-after: #start source
  :end-before: #end source

In this example `test_wms` is the name of the source, you need this name later to reference it. Most sources take more parameters, some are optional, some are required. The type `wms` requires the `req` parameter that describes the WMS request. You need to define at least a URL and the layer names, but you can add more options like `transparent` or `format`.

Adding a Cache
--------------

Next we want to create a cache for this source. Each cache needs to know where it can get new data, and how it should be cached. MapProxy splits images in small tiles and these tiles will be aligned to a grid. It also caches images in different resolutions, like an image pyramid. You can define this image pyramid in detail but we start with one of the default grid definitions of MapProxy. `GLOBAL_GEODETIC` defines a grid that covers the whole world. It uses EPSG:4326 as the spatial reference system and aligns with the default grid that OpenLayers uses.

Our cache configuration should now look like:

.. literalinclude:: tutorial.yaml
  :start-after: #start cache
  :end-before: #end cache

Adding a Layer
--------------

In the last step we need to create a layer for the MapProxy WMS. We need to give this layer a title, that is used in the capabilities documents, and a source. For this layer, we want to use our test cache as the data source:

.. literalinclude:: tutorial.yaml
  :start-after: #start layer
  :end-before: #end layer



Starting the development server
-------------------------------

That's it for the first configuration, you can now start MapProxy.
::

  mapproxy-util serve-develop mapproxy.yaml
  


