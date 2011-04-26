Authentication and Authorization
================================

.. warning:: This page and the described feautures of MapProxy are a work in progess and might change anytime.

Authentication is the process of mapping a request to a user. There are different ways to do this, from simple HTTP Basic Authentication to cookies or token based systems.

Authorization is the process that defines what an authenticated user is allowed to do. A datastore is required to store this authorization information for everything but trivial systems. These datastores can range from really simple text files (all users in this text file are allowed to do everything) to complex schemas with relational databases (user A is allowed to do B but not C, etc.).

As you can see, the options to choose when implementing a system for authentication and authorization are diverse. Developers (of SDIs, not the software itself) often have specific constraints, like existing user data in a database or an existing login on a website for a Web-GIS. So it is hard to offer a one-size-fits-all solution.

Therefore, MapProxy does not come with any embedded authentication or authorization. But it comes with a flexible authorization interface that allows you (the SDI developer) to implement custom tailored systems.

Luckily, there are lots of existing toolkits that can be used to build systems that match your requirements. For authentication there is the `repoze.who`_ package with `plugins for HTTP Basic Authentication, HTTP cookies, etc <repoze.who_plugins>`_. For authorization there is the `repoze.what`_ package with `plugins for SQL datastores, etc <repoze.what_plugins>`_.

.. _`repoze.who`: http://docs.repoze.org/who/
.. _`repoze.who_plugins`: http://pypi.python.org/pypi?:action=search&term=repoze.who
.. _`repoze.what`: http://docs.repoze.org/what/
.. _`repoze.what_plugins`: http://pypi.python.org/pypi?:action=search&term=repoze.what


.. note:: Developing custom authentication and authorization system requires a bit Python programming and knowledge of `WSGI <http://wsgi.org>`_ and WSGI middleware.

Authentication/Authorization Middleware
---------------------------------------

Your auth system should be implemented as a WSGI middleware. The middleware sits between your web server and the MapProxy.

WSGI Filter Middleware
~~~~~~~~~~~~~~~~~~~~~~

A simple middleware that authorizes random requests might look like::

  class RandomAuthFilter(object):
      def __init__(self, app, global_conf):
          self.app = app

      def __call__(self, environ, start_reponse):
          if random.randint(0, 1) == 1:
            return self.app(environ, start_reponse)
          else:
            start_reponse('403 Forbidden', [('content-type', 'text/plain')])
            return ['no luck today']


One way to add that middleware in front of MapProxy is the ``filter-with`` option of `PasteDeploy`_. The ``config.ini`` looks like::

  [app:mapproxy]
  use = egg:MapProxy#app
  mapproxy_conf = %(here)s/mapproxy.yaml
  filter-with = auth

  [filter:auth]
  paste.filter_app_factory = myauthmodule:RandomAuthFilter
  
  [server:main]
  ...

You can implement simple authentication systems with that method, but you should look at `repoze.who`_ before reinventing the wheel.

.. _`PasteDeploy`: http://pythonpaste.org/deploy/

Authorization Callback
~~~~~~~~~~~~~~~~~~~~~~

Authorization is a bit more complex, because your middleware would need to interpret the request to get information required for the authorization (e.g. layer names for WMS GetMap requests). Limiting the GetCapabilities response to certain layers would even require the middleware to manipulate the XML document. So it's obvious that some parts of the authorization should be handled by MapProxy.

MapProxy can call the middleware back for authorization as soon as it knows what to ask for (e.g. the layer names of a WMS GetMap request). You have to pass that function into the environment so that MapProxy knows what to call.

Here is a more elaborate example that denies requests to all layers that start with a specific prefix. These layers are also hidden from capability documents.

::

  class SimpleAuthFilter(object):
      """
      Simple MapProxy authorization middleware.
      
      It authorizes WMS requests for layers where the name does
      not start with `prefix`.
      """
      def __init__(self, app, global_conf, prefix='secure'):
          self.app = app
          self.prefix = prefix

      def __call__(self, environ, start_reponse):
          # put authorize callback function into environment
          environ['mapproxy.authorize'] = self.authorize
          return self.app(environ, start_reponse)

      def authorize(self, service, layers=[], environ=None, **kw):
          allowed = denied = False
          if service.startswith('wms.'):
              auth_layers = {}
              for layer in layers:
                  if layer.startswith(self.prefix):
                      auth_layers[layer] = {}
                      denied = True
                  else:
                      auth_layers[layer] = {
                          'map': True,
                          'featureinfo': True,
                          'legendgraphic': True,
                      }
                      allowed = True
          else: # other services are denied
            return {'authorized': 'none'}
          
          if allowed and not denied:
              return {'authorized': 'full'}
          if denied and not allowed:
              return {'authorized': 'none'}
          return {'authorized': 'partial', 'layers': auth_layers}


And here is the part of the ``config.ini`` where we define the filter and pass custom options:: 

  [filter:auth]
  paste.filter_app_factory = myfiltermodule:SimpleAuthFilter
  prefix = foo


MapProxy Authorization API
--------------------------

MapProxy looks in the request environment for a ``mapproxy.authorize`` entry. This entry should contain a callable (function or method). If it does not find any callable, then MapProxy assumes that authorization is not enabled and all requests are allowed.

The signature of the authorization function:

.. function:: authorize(service, environ, layers=[], **kw)
  
  :param service: service that should be authorized
  :param environ: the request environ
  :param layers: list of layer names that should be authorized
  :rtype: dictionary with authorization information

  The arguments might get extended in future versions of MapProxy. Therefore you should collect further arguments in a variable keyword argument (i.e. ``**kw``). 
  
.. note:: The actual name of the callable is insignificant, only the environment key ``mapproxy.authorize`` is important.

The ``service`` parameter is a string and the content depends on the service that calls the authorize function. Generally, it is the lower-case name of the service (e.g. ``tms`` for TMS service), but it can be different to further control the service (e.g. ``wms.map``).

The function should return a dictionary with the authorization information. The expected content of that dictionary can vary with each service. Only the ``authorized`` key is consistent with all services.

The ``authorized`` entry can have four values.

``full``
  The request for the given `service` and `layers` is fully authorized. MapProxy handles the request as if is no authorization.

``partial``
  Only parts of the request are allowed. The dictionary should contains more information on what parts of the request are allowed and what parts are denied. Depending on the service, MapProxy can then filter the request based on that information, e.g. return WMS Capabilities with permitted layers only.

``none``
  The request is denied and MapProxy returns an HTTP 403 response.

``unauthenticated``
  The request(er) was not authenticated and MapProxy returns an HTTP 401 response. Your middleware can capture this and ask the requester for authentication. ``repoze.who``'s ``PluggableAuthenticationMiddleware`` will do this for example.


.. versionadded:: 1.1.0
  The ``environment`` parameter and support for ``authorized: unauthenticated`` results.

WMS Service
~~~~~~~~~~~

The WMS service expects a ``layers`` entry in the authorization dictionary for ``partial`` results. ``layers`` itself should be a dictionary with all layers. All missing layers are interpreted as denied layers.

Each layer contains the information about the permitted features. A missing feature is interpreted as a denied feature.

Here is an example result of a call to the authorize function::

  {
    'authorized': 'partial',
    'layers': {
      'layer1': {
        'map': True,
        'featureinfo': False,
      },
      'layer2': {
        'map': True,
        'featureinfo': True,
      }
    }
  }


The WMS service uses the following service strings:

``wms.map``
^^^^^^^^^^^

This is called for WMS GetMap requests. ``layers`` is a list with the actual layers to render, that means that group layers are resolved.
The ``map`` feature needs to be set to ``True`` for each permitted layer. 
The whole request is rejected if any requested layer is not permitted. Resolved layers (i.e. sub layers of a requested group layer) are filtered out if they are not permitted.

.. versionadded:: 1.1.0
  The ``authorize`` function gets called with an additional ``query_extent`` argument:

  .. function:: authorize(service, environ, layers, query_extent, **kw)
  
    :param query_extent: a tuple of the SRS (e.g. ``EPSG:4326``) and the BBOX
      of the request to authorize.


Example
+++++++

With a layer tree like::

  - name: layer1
    layers:
      - name: layer1a
        sources: [l1a]
      - name: layer1b
        sources: [l1b]

An authorize result of::

  {
    'authorized': 'partial',
    'layers': {
      'layer1':  {'map': True},
      'layer1a': {'map': True}
    }
  }

Results in the following:

- A request for ``layer1`` renders ``layer1a``, ``layer1b`` gets filtered out.
- A request for ``layer1a`` renders ``layer1a``.
- A request for ``layer1b`` is rejected.
- A request for ``layer1a`` and ``layer1b`` is rejected.


``wms.featureinfo``
^^^^^^^^^^^^^^^^^^^

This is called for WMS GetFeatureInfo requests and the behavior is similar to ``wms.map``.

``wms.capabilities``
^^^^^^^^^^^^^^^^^^^^

This is called for WMS GetCapabilities requests. ``layers`` is a list with all named layers of the WMS service.
Only layers with the ``map`` feature set to ``True`` are included in the capabilities document. Missing layers are not included.

Sub layers are only included when the parent layer is included, since authorization interface is not able to reorder the layer tree. Note, that you are still able to request these sub layers (see ``wms.map`` above).

Layers that are queryable and only marked so in the capabilities if the ``featureinfo`` feature set to ``True``.

With a layer tree like::

  - name: layer1
    layers:
      - name: layer1a
        sources: [l1a]
      - name: layer1b
        sources: [l1b]
      - name: layer1c
        sources: [l1c]

An authorize result of::

  {
    'authorized': 'partial',
    'layers': {
      'layer1':  {'map': True, 'feature': True},
      'layer1a': {'map': True, 'feature': True},
      'layer1b': {'map': True},
      'layer1c': {'map': True},
    }
  }

Results in the following abbreviated capabilities::

  <Layer queryable="1">
    <Name>layer1</Name>
    <Layer queryable="1"><Name>layer1a</Name></Layer>
    <Layer><Name>layer1b</Name></Layer>
  </Layer>


TMS/Tile Service
~~~~~~~~~~~~~~~~

The TMS service expects a ``layers`` entry in the authorization dictionary for ``partial`` results. ``layers`` itself should be a dictionary with all layers. All missing layers are interpreted as denied layers.

Each layer contains the information about the permitted features. The TMS service only supports the ``tile`` feature. A missing feature is interpreted as a denied feature.

Here is an example result of a call to the authorize function::

  {
    'authorized': 'partial',
    'layers': {
      'layer1': {'tile': True},
      'layer2': {'tile': False},
    }
  }


The TMS service uses ``tms`` as the service string for all authorization requests.

Only layers with the ``tile`` feature set to ``True`` are included in the TMS capabilities document (``/tms/1.0.0``). Missing layers are not included.

KML Service
~~~~~~~~~~~

The KML authorization is similar to the TMS authorization.

The KML service uses ``kml`` as the service string for all authorization requests.


Demo Service
~~~~~~~~~~~~

The demo service only supports ``full`` or ``none`` authorization. ``layers`` is always an empty list. The demo service does not authorize the services and layers that are listed in the overview page. If you permit a user to access the demo service, then he can see all services and layers names. However, access to these services is still restricted to the according authorization.

The service string is ``demo``.


MultiMapProxy
~~~~~~~~~~~~~

The :ref:`MultiMapProxy <multimapproxy>` application stores the instance name in the environment as ``mapproxy.instance_name``. This information in not available when your middleware gets called, but you can use it in your authorization function.

Example that rejects MapProxy instances where the name starts with ``secure``.
::


  class MultiMapProxyAuthFilter(object):
      def __init__(self, app, global_conf):
          self.app = app

      def __call__(self, environ, start_reponse):
          environ['mapproxy.authorize'] = self.authorize
          return self.app(environ, start_reponse)
      
      def authorize(self, service, layers=[]):
          instance_name = environ.get('mapproxy.instance_name', '')
          if instance_name.startswith('secure'):
              return {'authorized': 'none'}
          else:
              return {'authorized': 'full'}
          

