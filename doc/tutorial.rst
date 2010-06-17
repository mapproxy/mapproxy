Tutorial
########


This tutorial should give you a quick introduction to the MapProxy configuration.


The MapProxy itself is configured with a single configuration.


Configuration format
====================

MapProxy uses the YAML format. YAML is a superset of JSON. That means every valid JSON is also valid YAML. MapProxy uses no advanced features of YAML, so you could even use JSON.
YAML uses a more readable and user-friendly syntax. We encourage you to use it.

If you are familiar with YAML you can skip the next section. 

The YAML configuration consist of dictionaries, lists, strings, numbers and booleans.

Numbers
  Any numerical value like ``12``, ``-4``, ``0``, and ``3.1415``.

Strings
  Any string within single or double quotes. You can omit the quotes if the string has no other meaning in YAML syntax. For example::
  
    'foo'
    foo
    '43' # with quotes, otherwise it would be numeric
    '[string, not a list]'
    A string with spaces and punctuation.

Booleans
  True or false values::
  
    yes
    true
    True
    no
    false
    False
    

List
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

globals
  Here you can define some internals of MapProxy and default values that are used in the other configuration directives.
  
services
  This is the place to activate and configure MapProxy's services like WMS and TMS.

sources
  Define where MapProxy can retrieve new data.

caches
  Here you can configure the internal caches.

layers
  Configure the layers that MapProxy offers. Each layer can consist of multiple sources and caches.
  
grids
  MapProxy aligns all cached images to a grid. Here you can define the grid.
  










