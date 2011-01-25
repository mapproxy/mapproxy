Authentication and Authorization
================================

.. warning:: This page and the described feautures of MapProxy are a work in progess and might change anytime.

Authentication is the process of mapping a request to a user. There are different ways to do this, from simple HTTP Basic Authentication to cookies or token based systems.

Authorization is the process that defines what an authenticated user is allowed to do. A kind of datastore is required to store these authorization information for everything but trivial systems. This datastore can range from really simple text files (all users in this text file are allowed to do everything) to complex relational databases (user A is allowed to do B but not C, etc.).

As you can see, the options to choose when implementing a system for authentication and authorization are diverse. Developers (of SDIs, not the software itself) often have specific constraints, like user data in a database or a single login on a website. So it is hard to offer a one-size-fits-all solution.

Therefore, MapProxy does not come with any embedded authentication or authorization. But, it comes with a flexible authorization interface that allows other SDI developers to implement custom tailored systems.

Luckily, there are lots of existing toolkits that implement different authentication and authorization methods. For authentication there is the `repoze.who`_ package with plugins for HTTP Basic Authentication, HTTP cookies, etc. For authorization there is the `repoze.what`_ package with plugins for SQL datastores, etc.

.. _`repoze.who`: http://pypi.python.org/pypi?:action=search&term=repoze.who
.. _`repoze.what`: http://pypi.python.org/pypi?:action=search&term=repoze.what



Auth middleware
---------------

Your auth system should be implemented as a WSGI middleware. The middleware sits between your web server and the MapProxy.

Auth Filter Middleware
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


One way to add that middleware before MapProxy is the ``filter-with`` option of PasteDeploy. The ``config.ini`` looks like::

  [app:mapproxy]
  use = egg:MapProxy#app
  mapproxy_conf = %(here)s/mapproxy.yaml
  filter-with = auth

  [filter:auth]
  paste.filter_app_factory = myauthmodule:RandomAuthFilter
  
  [server:main]
  ...

You can implement simple authentication systems with that method, but you should look at repoze.who before reinventing the wheel.

Authorization Callback
~~~~~~~~~~~~~~~~~~~~~~

Authorization is a bit more complex, because your middleware would need to interpret the request to get information required for the authorization, e.g. the layer names of a WMS GetMap request. Limiting the GetCapabilities response to certain layers would even require the middleware to manipulate the XML document. So it's obvious that some parts of the authorization should be handled by MapProxy.

MapProxy can call the middleware back for authorization as soon as it knows what to ask for (e.g. the layer names of a WMS GetMap request). You have to pass that function into the environment so that MapProxy knows what to call.

Here is a more elaborate example that hides/denies requests to all layers that start with a specific prefix.

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

      def authorize(self, service, layers=[], **kw):
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

MapProxy looks in the request environment for an ``mapproxy.authorize`` entry. This entry should contain a authorize callable (function or method). If it does not find any callable, then MapProxy assumes that authorization is not enabled and all requests should be allowed.

The signature of the authorization function:

.. function:: authorize(service, layers=[])
  
  :param service: service that should be authorized
  :param layers: list of layer names that should be authorized
  :rtype: dictionary with authorization information

.. note:: The actual name of the callable is insignificant, only the environment key ``mapproxy.authorize`` is important.


The ``service`` parameter is a string and the content depends on the service that calls the authorize function (e.g. ``tms``). Generally, it is the lower-case name of the service, but it can be different to further control the service (e.g. ``wms.map``).

The function should return a dictionary with the authorization information. The expected content of that dictionary can vary with each service. Only the ``authorized`` key is consistent with all services.

The ``authorized`` entry can have three values.

``full``
  The request for the given `service` and `layers` is fully authorized. MapProxy will handle the request as if there where no authorization.

``none``
  The request is denied and MapProxy will return an HTTP 403 response. Your middleware can capture this and ask the requester for authentication.

``partial``
  Only parts of the request are allowed. The dictionary should contains more information on what parts of the request are allowed and what parts are denied. Depending on the service, MapProxy can then filter the request based on that information, e.g. return WMS Capabilities with permitted layers only.


WMS Services
~~~~~~~~~~~~

The WMS service expects a ``layers`` entry in the authorization dictionary for ``partial`` results. ``layers`` itself should be a dictionary with all layers. All missing layers are interpreted as denied layers.

Each layer is contains the information about the permitted features. A missing feature is interpreted as a denied feature.

Example result of a call to the authorize function::

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

This is called for WMS GetMap requests. ``layers`` is a list with the actual layers to render, that means that group layers will be resolved.
The ``map`` feature needs to be set to ``True`` for each permitted layer. 
The whole request is rejected if any requested layer is not permitted. Layers that are added automatically (e.g. sub layers of a group) are filtered out.

With a layer tree like::

  - name: layer1
    layers:
      - name: layer1a
        sources: [l1a]
      - name: layer1b
        sources: [l1b]

and permissions for ``layer1`` and ``layer1a``. A request for ``layer1`` or ``layer1a`` will render ``layer1a``, request for ``layer1b`` or both ``layer1a`` and ``layer1b`` will be rejected.

