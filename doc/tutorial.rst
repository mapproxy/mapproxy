Tutorial
########

This tutorial should give you a quick introduction to the MapProxy configuration.


The MapProxy itself is configured with a single configuration.


Configuration format
====================

MapProxy uses the YAML format. YAML is a superset of JSON. That means every valid 
JSON is also valid YAML. MapProxy uses no advanced features of YAML, so you could 
even use JSON. YAML uses a more readable and user-friendly syntax. We encourage 
you to use it.

If you are familiar with YAML you can skip the next section. 

The YAML configuration consist of comments, dictionaries, lists, strings, numbers 
and booleans.

Comments
--------
Everything after a pound character (``#``) is a comment and will be ignored.

Numbers
-------
Any numerical value like ``12``, ``-4``, ``0``, and ``3.1415``.

Strings
-------
Any string within single or double quotes. You can omit the quotes if the string 
has no other meaning in YAML syntax. For example::
  
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
A list is a collection of other valid objects. There are two formats. The condensed 
form uses square brackets::
  
    [1, 2, 3]
    [42, string, [another list with a string]]
  
The block form starts requires every list item on a separate line, starting with 
a ``-`` character::
  
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

The MapProxy configuration is a dictionay, each key configures a different aspect
of MapProxy. There are the following keys:

- ``globals``:  Here you can define some internals of MapProxy and default values 
                that are used in the other configuration directives.
  
- ``services``:  This is the place to activate and configure MapProxy's services 
                 like WMS and TMS.

- ``sources``: Define where MapProxy can retrieve new data.

- ``caches``: Here you can configure the internal caches.

- ``layers``: Configure the layers that MapProxy offers. Each layer can consist 
              of multiple sources and caches.
  
- ``grids``: MapProxy aligns all cached images to a grid. Here you can define 
             that grid.
  
The order of the directives is not important, so you can organize it your way.

.. At first it seams a bit complex, but after you have configured you first MapProxy it all should become clear.



Example Configuration
=====================

Configuring a Service
---------------------

At first we need to :ref:`configure at least one service <services>`. To enable 
a service, you have to include its name as a key in the `services` dictionary. 
For example::

  service:
    wms:


Each service is a YAML dictionary, with the service type as the key. The dictionary
can be empty, but you need to add the colon so that the configuration parser knows 
it's a dictionary.


A service might accept more configuration options. The WMS service, for example, 
takes a dictionary with metadata. These data is used in the capabilities documents.

Here is an example with some contact information:

.. literalinclude:: tutorial.yaml
  :end-before: #end services

`access_constraints` demonstrates how you can write a string over multiple lines,
just indent every line the same way as the first. And remember, YAML does not 
accept tab characters, you must use space.

For this tutorial we add an other source called `demo`. This is a demo service 
that lists all configured WMS and TMS layers. You can test each layer with a 
simple OpenLayers client. So our configuration file should look like::
  
  service:
    demo:
    wms:
      ...

Adding a Source
----------------

Next you need to :ref:`define the source <sources>` of your data. Every source has
a name and a type. Lets add a WMS source:

.. literalinclude:: tutorial.yaml
  :prepend: sources:
  :start-after: #start source
  :end-before: #end source

In this example `test_wms` is the name of the source, you need this name later 
to reference it. Most sources take more parameters, some are optional, some are 
required. The type `wms` requires the `req` parameter that describes the WMS 
request. You need to define at least a URL and the layer names, but you can add 
more options like `transparent` or `format`.


Adding a Layer
--------------

After defining a source we can use it to :ref:`create a layer <layers_section>` for the 
MapProxy WMS. 

A layer requires a title, which will be used in the capabilities documents, and 
a source. For this layer, we want to use our `test_wms` data source:

.. literalinclude:: tutorial.yaml
  :prepend: layers:
  :start-after: #start cascaded layer
  :end-before: #end cascaded layer
  
Now we have setuped MapProxy as cascading WMS. That means MapProxy only redirect 
requests to the WMS defined in `test_wms` data source.


Starting the development server
-------------------------------

That's it for the first configuration, you can now :ref:`start MapProxy <mapproxy-util>`::


  mapproxy-util serve-develop mapproxy.yaml

:download:`You can get the configuration discussed above here. <yaml/simple_conf.yaml>`


When you type `localhost:8080/demo/` in the URL of your webbrowser you should 
see a demo site like shown below.

.. image:: imgs/mapproxy-demo.jpg

Here you can see the capabilities of your set up service and watch it in action.


Adding a Cache
--------------

To speed up the source with MapProxy we :ref:`create a cache <caches>` for this 
source. 

Each cache needs to know where it can get new data, and how it should be cached, 
so we define out `test_wms` as source for the cache. MapProxy splits images in
small tiles and these tiles will be aligned to a grid. It also caches images in 
different resolutions, like an image pyramid. You can define this image pyramid 
in detail but we start with one of the default grid definitions of MapProxy. 
`GLOBAL_GEODETIC` defines a grid that covers the whole world. It uses EPSG:4326 
as the spatial reference system and aligns with the default grid that OpenLayers 
uses.

Our cache configuration should now look like:

.. literalinclude:: tutorial.yaml
  :start-after: #start caches
  :end-before: #end caches


Adding a cached Layer
---------------------

We can now use our defined cache as source for a layer. When the layer is 
requested by a client, MapProxy looks in cache after requested data and only if 
it hasn't cached the data yet, it requests the `test_wms` data source.

The layer configuration should now look like:
    
.. literalinclude:: tutorial.yaml
  :prepend: layers:
  :start-after: #start cached layer
  :end-before: #end cached layer
  
:download:`You can get the configuration discussed above here. <yaml/cache_conf.yaml>`
  
Defining Resolutions
--------------------

By default MapProxy caches traditional power-of-two image pyramids with a default
number of :ref:`cached resolutions <cache_resolutions>` of 20. The resolutions 
between each pyramid level doubles. If you want to change this, you can do so by
:ref:`defining your own grid <grids>`. Fortunately MapProxy grids provied the 
ability to inherit from an other grid. We let our grid inherit from the previously 
used `GLOBAL_GEODETIC` grid and add five fixed resolutions to it.

The grid configuration should look like:

.. literalinclude:: tutorial.yaml
  :prepend: grids:
  :start-after: #start res grid
  :end-before: #end res grid
  
As you see, we used `base` to inherit from `GLOBAL_GEODETIC` and `res` to define
our preferred resolutions.
Instead of defining fixed resolitions, we can also define a factor that is used 
to calculate the resolutions. The default value of this factor is 2, but you can 
set it to each value you want. Just change `res` with `res_factor` and add your 
prefered factor after it.

A magical value of `res_factor` is **sqrt2**, the square root of two. It doubles 
the number of cached resolutions, so you have 40 instead of 20 available resolutions.
Every secound resolution is identical to the power-of-two resolutions, so you can 
use this layer not only in classic WMS clients, but also in tile-based clients
like OpenLayers which only request in these resolutions. 
  

Defining a Grid
---------------

In the pervious section we saw how to extend a grid to provide self defined
resolutions, but sometimes `GLOBAL_GEODETIC` grid is not usefull because it covers
the hole world and we want only a part of it. So let's see how to :ref:`define our own grid <grids>`.

For example we define a grid for germany. We need a spatial reference system (`srs`)
that match the region of germany and a bounding box (`bbox`) around germany to limit 
the requestable aera. To make the specification of the `bbox` a little bit easyer, 
we put the `bbox_srs` parameter to the grid configuration. So we can define the
`bbox` for example in EPSG:4326.

The `grids` configuration is a dictionary and each grid configuration is identified 
by it's name. We call our grid `germany` and it's configuration should look like:

.. literalinclude:: tutorial.yaml
  :prepend: grids:
  :start-after: #start germany grid
  :end-before: #end germany grid
  
Now we have to replace `GLOBAL_GEODETIC` in the caches configuration with our
`germany` grid and MapProxy takes care of transformation if `srs` of our grid is 
different to the one from data source.

:download:`You can get the configuration discussed above here. <yaml/grid_conf.yaml>`


Mergin Multiple Layers
----------------------

If you have two WMS and want to offer a single layer with data from both server, 
you can combine these in one cache. MapProxy will combine both before it stores 
the tiles on disk. Consider that sources should be defined from bottom to top and 
all sources except the bottom needs to be transparent.

The code below is an example for configure MapProxy to combine two WMS in one 
cache and one layer:

.. literalinclude:: tutorial.yaml
  :start-after: #start combined sources
  :end-before: #end combined sources
  
:download:`You can get the configuration discussed above here. <yaml/merged_conf.yaml>`

Coverages
---------

Sometimes you don't want to provide the full data of a wms in a layer. With 
MapProxy you can define areas where data is available or where data you are 
interested in is. MapProxy provides three ways to restrict the area of available 
data: Bounding boxes, polygons and OGR datasource. To keep it simple, we only 
discust bounding boxes. For more informations about the both outer methods take
a look at :ref:`coverages <coverages>`.
To restrict the area with a bounding box, we have to define it in the coverage 
option of the data source. The listing below restricts the requestable area to 
germany:

.. literalinclude:: tutorial.yaml
  :start-after: #start coverage
  :end-before: #end coverage

As you see notation of a coverage bounding box is similar to the notation in the
grid option.


Meta Tiles and Meta Buffer
--------------------------

When you have experience with WMS you would know the problem of labeling issues.
MapProxy can help to resolve this issues, especial if you have no access to the 
wms configuration. MapProxy uses two technics called :ref:`Meta Tiling <meta_tiles>`
and :ref:`Meta Buffering <meta_buffer>`. Meta Tiling means instead of requesting 
each single tile from the service requesting a single image that covers the area 
of multiple tiles and split it into actual tiles. With Meta Buffering MapProxy 
extends the requested area, so labeling issues can be prevent.

To enable Meta Tiles and Meta Buffer you must define `meta_size` (for Meta Tiles) 
and `meta_buffer` (for Meta Buffer) in cache configuration. The next example shows 
configuration of Meta Tile covering 4 x4 tiles and Meta Buffer expanding requests 
by 100 pixel at each edge:

.. literalinclude:: tutorial.yaml
  :start-after: #start meta
  :end-before: #end meta
  
:download:`You can get the configuration discussed above here. <yaml/meta_conf.yaml>`
  
Seeding
-------

Configuration
~~~~~~~~~~~~~
MapProxy creates all tiles on demand. That means, only tiles requested once are 
cached. Fortunately MapProxy comes with a command line script for pregenerating 
tiles called ``mapproxy-seed``. It have it's own configuration file called 
``seed.yaml`` and a couple of options. We now create a config file for ``mapproxy-seed``.

As all MapProxy configuration files it's notated in yaml. The mandatory options 
is ``seeds``. Here you can define what should be seeded in multiple seeding tasks.
You can specify a list of caches for seeding with ``cache`` . The cache names 
should match the cache names in your MapProxy configuration. If you have specified 
multiple grids for one cache in your MapProxy configuration, you can select these
caches to seed. They must also comply with the caches in your MapProxy configuration.
Furthermore you can limit the levels that should be seeded. If you wish to seed a
delimited area, you can use the ``coverages`` option.

In the example below, we configure ``mapproxy-seed`` to seed our previously created
cache ``meta_cache`` from level 6 to level 16. To show a different possibility to
define a coverage, we use a shapefile to determine the area, we want to be seeded.

.. literalinclude:: yaml/seed.yaml

As you see in the ``coverages`` section the ``polygons`` option point to a
textfile. From these textfile polygons are loaded. The third option tells 
``mapproxy-seed`` the ``srs`` of the specified textfile.

:download:`You can get the configuration discussed above here. <yaml/seed.yaml>`

:download:`Here you can get the neccessary Polygon file for this example <GM.txt>`

Start Seeding
~~~~~~~~~~~~~

Now it's time to start seeding. As we heard above, ``mapproxy-seed`` have a couple 
of options. We have to use options ``-s`` to define our ``seed.yaml`` and ``-f``
for our MapProxy configuration file. We also use ``--dry-run`` so we can see what
would be done and change our configuration. Seeding could be a very system 
utilization process if it isn't configured right. 

Run ``mapproxy-seed`` like::
    
    mapproxy-seed -f mapproxy.yaml -s seed.yaml --dry-run
    
If you sure, that seeding works right, remove ``--dry-run``.


What now?
---------

You can see the full capabilities of MapProxy and a lot of usefull thinks in the
:ref:`Configuration Examples Section <configuration_examples>`.
