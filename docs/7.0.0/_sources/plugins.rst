Writing plugins
===============

Since MapProxy 1.15, it is possible to write plugins for MapProxy that can
add new sources, services or commands. This requires Python >= 3.7

Example
-------

The mapproxy_hips plugin at https://github.com/rouault/mapproxy_hips is an
example of a plugin, which adds a new source, service and customizes the demo
service, demonstrating all the below points.

How to add a plugin ?
---------------------

A plugin should be written as a Python package whose setuptools ``setup()``
method has a ``entry_points`` keyword with a group ``mapproxy`` pointing to
a module with a ``plugin_entrypoint`` method.

.. code-block:: python

    entry_points={"mapproxy": ["hips = mapproxy_hips.pluginmodule"]},


In this example, the ``mapproxy_hips/pluginmodule.py`` file should have
a ``plugin_entrypoint`` method taking no argument and returning nothing.

.. code-block:: python

    def plugin_entrypoint():
        # call different registration methods, like register_service_configuration(),
        # register_source_configuration()
        pass

That method is in charge of registering the various registration methods
detailed hereafter.

Plugins will often by dependent on MapProxy internal classes. It is their
responsibility to check the MapProxy version, in case the MapProxy internal
API or behavior would change and make them incompatible.

Adding a new service
--------------------

The ``mapproxy.config.loader`` module has a ``register_service_configuration()``
method to register a new service and specify the allowed keywords for it in
the YAML configuration file.

.. code-block:: python

    def register_service_configuration(service_name, service_creator,
                                       yaml_spec_service_name = None,
                                       yaml_spec_service_def = None,
                                       schema_service=None):
        """ Method used by plugins to register a new service.

            :param config_name: Name of the service
            :type config_name: str
            :param service_creator: Creator method of the service
            :type service_creator: method of type (serviceConfiguration: ServiceConfiguration, conf: dict) -> Server
            :param yaml_spec_service_name: Name of the service in the YAML configuration file
            :type yaml_spec_service_name: str
            :param yaml_spec_service_def: Definition of the service in the YAML configuration file
            :type yaml_spec_service_def: dict
            :param schema_service: JSON schema extract to insert under
            /properties/services/properties/{yaml_spec_service_name} of config-schema.json
            :type schema_service: dict
        """


This can for example by used like the following snippet:

.. code-block:: python

    from mapproxy.config.configuration.service import register_service_configuration
    from mapproxy.service.base import Server

    class MyExtraServiceServer(Server):
        # Look at classes at https://github.com/mapproxy/mapproxy/tree/master/mapproxy/service
        # for a real implementation
        names = ('my_extra_service',)
        def __init__(self):
            pass

    def my_extra_service_method(serviceConfiguration, conf):
        return MyExtraServiceServer()

    json_schema_extension = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'foo': {
                'type': 'string'
            }
        }
    }
    register_service_configuration('my_extra_service', my_extra_service_method,
                                   'my_extra_service', {'foo': str()},
                                   json_schema_extension)


This allows the following declaration in the YAML mapproxy configuration file:

.. code-block:: yaml

    services:
        my_extra_service:
            foo: bar

A real-world implementation can be found at https://github.com/rouault/mapproxy_hips/blob/master/mapproxy_hips/service/hips.py


Customizing layer metadata in YAML configuration file
-----------------------------------------------------

When implementing a new service, it might be useful to add per-layer metadata
for it. The YAML validator needs to be updated to recognize the new keywords.
The ``add_subcategory_to_layer_md()`` method of the ``mapproxy.config.spec`` module
can be used to do that.

.. code-block:: python


    def add_subcategory_to_layer_md(category_name, category_def):
        """ Add a new category to wms_130_layer_md.
            Used by plugins
        """

This can for example be used like in the following snippet:

.. code-block:: python

    from mapproxy.config.spec import add_subcategory_to_layer_md

    # Add a 'hips' subcategory to layer spec to be able to define hips service
    # specific layer metadata
    add_subcategory_to_layer_md('hips', anything())


Adding a new source
-------------------

The ``mapproxy.config.loader`` module has a ``register_source_configuration()``
method to register a new source and specify the allowed keywords for it in
the YAML configuration file.

.. code-block:: python


    def register_source_configuration(config_name, config_class,
                                      yaml_spec_source_name = None, yaml_spec_source_def = None):
        """ Method used by plugins to register a new source configuration.

            :param config_name: Name of the source configuration
            :type config_name: str
            :param config_class: Class of the source configuration
            :type config_name: SourceConfiguration
            :param yaml_spec_source_name: Name of the source in the YAML configuration file
            :type yaml_spec_source_name: str
            :param yaml_spec_source_def: Definition of the source in the YAML configuration file
            :type yaml_spec_source_def: dict
        """


This can for example by used like the following snippet:

.. code-block:: python

    from mapproxy.config.configuration.source import register_source_configuration
    from mapproxy.config.configuration.source import SourceConfiguration

    class my_source_configuration(SourceConfiguration):
        source_type = ('my_extra_source',)

        def source(self, params=None):
            # Look at classes at https://github.com/mapproxy/mapproxy/tree/master/mapproxy/source
            # for a real implementation
            class MySource(object):
                def __init__(self):
                    self.extent = None
            return MySource()

    register_source_configuration('my_extra_source', my_source_configuration,
                                  'my_extra_source', {'foo': str()})


This allows the following declaration in the YAML mapproxy configuration file:

.. code-block:: yaml

    sources:
        some_source_name:
            type: my_extra_source
            foo: bar

A real-world implementation can be found at https://github.com/rouault/mapproxy_hips/blob/master/mapproxy_hips/source/hips.py

Customizing the demo service
----------------------------

The :ref:`demo_service_label` can be customized in two ways:

- Customizing the output of the ``/demo`` HTML output, typically by adding entries
  for new services. This is done with the ``register_extra_demo_substitution_handler()``
  method of the ``mapproxy.service.demo`` module.

  .. code-block:: python

        def register_extra_demo_substitution_handler(handler):
            """ Method used by plugins to register a new handler for doing substitutions
                to the HTML template used by the demo service.
                The handler passed to this method is invoked by the DemoServer._render_template()
                method. The handler may modify the passed substitutions dictionary
                argument. Keys of particular interest are 'extra_services_html_beginning'
                and 'extra_services_html_end' to add HTML content before/after built-in
                services.

                :param handler: New handler for incoming requests
                :type handler: function that takes 3 arguments(DemoServer instance, req and a substitutions dictionary argument).
            """

- Handling new request paths under the ``/demo/`` hierarchy, typically to implement a new
  service. This is done with the ``register_extra_demo_server_handler()``
  method of the ``mapproxy.service.demo`` module.

  .. code-block:: python

        def register_extra_demo_server_handler(handler):
            """ Method used by plugins to register a new handler for the demo service.
                The handler passed to this method is invoked by the DemoServer.handle()
                method when receiving an incoming request. This enables handlers to
                process it, in case it is relevant to it.

                :param handler: New handler for incoming requests
                :type handler: function that takes 2 arguments (DemoServer instance and req) and
                               returns a string with HTML content or None
            """

This can for example be used like in the following snippet:

.. code-block:: python

    from mapproxy.service.demo import register_extra_demo_server_handler, register_extra_demo_substitution_handler

    def demo_server_handler(demo_server, req):
        if 'my_service' in req.args:
            return 'my_return'
        return None

    def demo_substitution_handler(demo_server, req, substitutions):
        html = '<h2>My extra service</h2>'
        html += '<a href="/demo?my_service">My service</a>'
        substitutions['extra_services_html_beginning'] += html

    register_extra_demo_server_handler(demo_server_handler)
    register_extra_demo_substitution_handler(demo_substitution_handler)


A real-world example can be found at https://github.com/rouault/mapproxy_hips/blob/master/mapproxy_hips/service/demo_extra.py


Adding new commands to mapproxy-util
------------------------------------

New commands can be added to :ref:`mapproxy-util` by using the
``register_command()`` method of the ``mapproxy.script.util`` module

.. code-block:: python

    def register_command(command_name, command_spec):
        """ Method used by plugins to register a command.

            :param command_name: Name of the command
            :type command_name: str
            :param command_spec: Definition of the command. Dictionary with a 'func' and 'help' member
            :type command_spec: dict
        """

This can for example be used like in the following snippet:

.. code-block:: python

    import optparse
    from mapproxy.script.util import register_command

    def my_command(args=None):
        parser = optparse.OptionParser("%prog my_command [options] -f mapproxy_conf -l layer")
        parser.add_option("-f", "--mapproxy-conf", dest="mapproxy_conf",
            help="MapProxy configuration.")
        parser.add_option("-l", "--layer", dest="layer", help="Layer")

        if args:
            args = args[1:] # remove script name

        (options, args) = parser.parse_args(args)
        if not options.mapproxy_conf or not options.layer:
            parser.print_help()
            sys.exit(1)

        # Do something


    register_command('my_command', {
        'func': my_command,
        'help': 'Do something.'
    })


A real-world example can be found at https://github.com/rouault/mapproxy_hips/blob/master/mapproxy_hips/script/hipsallsky.py


Intercepting request
--------------------

It is possible to intercept any request in a plugin with `register_request_interceptor`. The provided function will be called on any request and should
always return a request, either the original one or a new one.

Example:

.. code-block:: python

    from mapproxy.wsgiapp import register_request_interceptor

    def interceptor(req):
        if req.path.startswith('service'):
            environ = req.environ.copy()
            environ['QUERY_STRING'] = environ['QUERY_STRING'].replace('foo', 'bar')
            return Request(environ)
        return req

    register_request_interceptor(interceptor)


A real world example can be found at https://github.com/mapproxy/wmts-rest-legend-plugin


Credits
-------

The development of the plugin mechanism has been funded by
Centre National d'Etudes Spatiales (CNES): https://cnes.fr
