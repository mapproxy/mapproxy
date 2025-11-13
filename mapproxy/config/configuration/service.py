from __future__ import division

from collections import OrderedDict

from mapproxy.config.configuration.base import ConfigurationBase
from mapproxy.config.configuration.base import ConfigurationError
from mapproxy.config.spec import add_service_to_mapproxy_yaml_spec
from mapproxy.config.validator import add_service_to_config_schema
from mapproxy.service.ows import OWSServer

import logging

log = logging.getLogger('mapproxy.config')


plugin_services = {}


def register_service_configuration(service_name, service_creator,
                                   yaml_spec_service_name=None,
                                   yaml_spec_service_def=None,
                                   schema_service=None):
    """ Method used by plugins to register a new service.

        :param service_name: Name of the service
        :type service_name: str
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

    log.info('Registering configuration for plugin service %s' % service_name)
    plugin_services[service_name] = service_creator
    if yaml_spec_service_name is not None and yaml_spec_service_def is not None:
        add_service_to_mapproxy_yaml_spec(yaml_spec_service_name, yaml_spec_service_def)
    if yaml_spec_service_name is not None and schema_service is not None:
        add_service_to_config_schema(yaml_spec_service_name, schema_service)
    if yaml_spec_service_name is not None and schema_service is not None:
        add_service_to_config_schema(yaml_spec_service_name, schema_service)


class ServiceConfiguration(ConfigurationBase):
    def __init__(self, conf, context):
        if 'wms' in conf:
            if conf['wms'] is None:
                conf['wms'] = {}
            if 'md' not in conf['wms']:
                conf['wms']['md'] = {'title': 'MapProxy WMS'}

        ConfigurationBase.__init__(self, conf, context)

    def services(self):
        services = []
        ows_services = []
        for service_name, service_conf in self.conf.items():
            creator = getattr(self, service_name + '_service', None)
            if not creator:
                # If not a known service, try to use the plugin mechanism
                creator = plugin_services.get(service_name, None)
                if not creator:
                    raise ValueError('unknown service: %s' % service_name)
                new_services = creator(self, service_conf or {})
            else:
                new_services = creator(service_conf or {})

            # a creator can return a list of services...
            if not isinstance(new_services, (list, tuple)):
                new_services = [new_services]

            for new_service in new_services:
                if getattr(new_service, 'service', None):
                    ows_services.append(new_service)
                else:
                    services.append(new_service)

        services.append(OWSServer(ows_services))
        return services

    def tile_layers(self, conf, use_grid_names=False):
        layers = OrderedDict()
        for layer_name, layer_conf in self.context.layers.items():
            for tile_layer in layer_conf.tile_layers(grid_name_as_path=use_grid_names):
                if not tile_layer:
                    continue
                if use_grid_names:
                    layers[tile_layer.md['name_path']] = tile_layer
                else:
                    layers[tile_layer.md['name_internal']] = tile_layer
        return layers

    def kml_service(self, conf):
        from mapproxy.service.kml import KMLServer

        md = self.context.services.conf.get('wms', {}).get('md', {}).copy()
        md.update(conf.get('md', {}))
        max_tile_age = self.context.globals.get_value('tiles.expires_hours')
        max_tile_age *= 60 * 60  # seconds
        use_grid_names = conf.get('use_grid_names', False)
        layers = self.tile_layers(conf, use_grid_names=use_grid_names)
        return KMLServer(layers, md, max_tile_age=max_tile_age, use_dimension_layers=use_grid_names)

    def tms_service(self, conf):
        from mapproxy.service.tile import TileServer

        md = self.context.services.conf.get('wms', {}).get('md', {}).copy()
        md.update(conf.get('md', {}))
        max_tile_age = self.context.globals.get_value('tiles.expires_hours')
        max_tile_age *= 60 * 60  # seconds

        origin = conf.get('origin')
        use_grid_names = conf.get('use_grid_names', False)
        layers = self.tile_layers(conf, use_grid_names=use_grid_names)
        return TileServer(layers, md, max_tile_age=max_tile_age, use_dimension_layers=use_grid_names,
                          origin=origin)

    def wmts_service(self, conf):
        from mapproxy.service.wmts import WMTSServer, WMTSRestServer

        md = self.context.services.conf.get('wms', {}).get('md', {}).copy()
        md.update(conf.get('md', {}))
        layers = self.tile_layers(conf, use_grid_names=True)

        kvp = conf.get('kvp')
        restful = conf.get('restful')

        max_tile_age = self.context.globals.get_value('tiles.expires_hours')
        max_tile_age *= 60 * 60  # seconds

        info_formats = conf.get('featureinfo_formats', [])
        info_formats = OrderedDict((f['suffix'], f['mimetype']) for f in info_formats)

        if kvp is None and restful is None:
            kvp = restful = True

        services = []
        if kvp:
            services.append(
                WMTSServer(
                    layers, md, max_tile_age=max_tile_age,
                    info_formats=info_formats,
                )
            )

        if restful:
            template = conf.get('restful_template')
            fi_template = conf.get('restful_featureinfo_template')
            if template and '{{' in template:
                # TODO remove warning in 1.6
                log.warning("double braces in WMTS restful_template are deprecated {{x}} -> {x}")
            services.append(
                WMTSRestServer(
                    layers, md, template=template,
                    fi_template=fi_template,
                    max_tile_age=max_tile_age,
                    info_formats=info_formats,
                )
            )

        return services

    def wms_service(self, conf):
        from mapproxy.service.wms import WMSServer
        from mapproxy.request.wms import Version

        md = conf.get('md', {})
        inspire_md = conf.get('inspire_md', {})
        tile_layers = self.tile_layers(conf)
        attribution = conf.get('attribution')
        strict = self.context.globals.get_value('strict', conf, global_key='wms.strict')
        on_source_errors = self.context.globals.get_value('on_source_errors',
                                                          conf, global_key='wms.on_source_errors')
        root_layer = self.context.wms_root_layer.wms_layer()
        if not root_layer:
            raise ConfigurationError("found no WMS layer")
        if not root_layer.title:
            # set title of root layer to WMS title
            root_layer.title = md.get('title')
        concurrent_layer_renderer = self.context.globals.get_value(
            'concurrent_layer_renderer', conf,
            global_key='wms.concurrent_layer_renderer')
        image_formats_names = self.context.globals.get_value('image_formats', conf,
                                                             global_key='wms.image_formats')
        image_formats = OrderedDict()
        for format in image_formats_names:
            opts = self.context.globals.image_options.image_opts({}, format)
            if opts.format in image_formats:
                log.warning('duplicate mime-type for WMS image_formats: "%s" already configured, will use last format',
                            opts.format)
            image_formats[opts.format] = opts
        info_types = conf.get('featureinfo_types')
        srs = self.context.globals.get_value('srs', conf, global_key='wms.srs')
        self.context.globals.base_config.wms.srs = srs
        srs_extents = extents_for_srs(conf.get('bbox_srs', []))

        versions = conf.get('versions')
        if versions:
            versions = sorted([Version(v) for v in versions])

        max_output_pixels = self.context.globals.get_value('max_output_pixels', conf,
                                                           global_key='wms.max_output_pixels')
        if isinstance(max_output_pixels, list):
            max_output_pixels = max_output_pixels[0] * max_output_pixels[1]

        max_tile_age = self.context.globals.get_value('tiles.expires_hours')
        max_tile_age *= 60 * 60  # seconds

        server = WMSServer(root_layer, md, attribution=attribution,
                           image_formats=image_formats, info_types=info_types,
                           srs=srs, tile_layers=tile_layers, strict=strict, on_error=on_source_errors,
                           concurrent_layer_renderer=concurrent_layer_renderer,
                           max_output_pixels=max_output_pixels, srs_extents=srs_extents,
                           max_tile_age=max_tile_age, versions=versions,
                           inspire_md=inspire_md,
                           )

        server.fi_transformers = fi_xslt_transformers(conf, self.context)

        return server

    def ogcapi_service(self, conf):
        from mapproxy.srs import SRS
        from mapproxy.service.ogcapi.server import OGCAPIServer

        root_layer = self.context.wms_root_layer.wms_layer()
        if not root_layer:
            raise ConfigurationError("found no layer")

        enable_tiles = conf.get('enable_tiles', True)
        enable_maps = conf.get('enable_maps', True)
        attribution = conf.get('attribution')
        md = conf.get('md', {})

        concurrent_layer_renderer = self.context.globals.get_value(
            'concurrent_layer_renderer', conf,
            global_key='ogcapi.concurrent_layer_renderer')

        image_formats_names = self.context.globals.get_value('image_formats', conf,
                                                             global_key='ogcapi.image_formats')
        image_formats = OrderedDict()
        for format in image_formats_names:
            opts = self.context.globals.image_options.image_opts({}, format)
            if opts.format in image_formats:
                log.warning('duplicate mime-type for OGCAPI image_formats: '
                            '"%s" already configured, will use last format',
                            opts.format)
            image_formats[opts.format] = opts

        max_output_pixels = self.context.globals.get_value('max_output_pixels', conf,
                                                           global_key='ogcapi.max_output_pixels')
        if isinstance(max_output_pixels, list):
            max_output_pixels = max_output_pixels[0] * max_output_pixels[1]

        max_tile_age = self.context.globals.get_value('tiles.expires_hours')
        max_tile_age *= 60 * 60  # seconds

        on_source_errors = self.context.globals.get_value('on_source_errors',
                                                          conf, global_key='ogcapi.on_source_errors')

        default_dataset_layers = conf.get('default_dataset_layers', None)
        if default_dataset_layers:
            layers = root_layer.child_layers()
            default_dataset_layers = [layers[id] for id in default_dataset_layers]

        grid_configs = self.context.grids

        map_srs = self.context.globals.get_value('map_srs', conf, global_key='ogcapi.map_srs')
        if map_srs:
            map_srs = [SRS(srs) for srs in map_srs]
        else:
            map_srs = []

        return OGCAPIServer(root_layer,
                            enable_tiles=enable_tiles,
                            enable_maps=enable_maps,
                            attribution=attribution,
                            metadata=md,
                            image_formats=image_formats,
                            max_tile_age=max_tile_age,
                            on_error=on_source_errors,
                            concurrent_layer_renderer=concurrent_layer_renderer,
                            max_output_pixels=max_output_pixels,
                            grid_configs=grid_configs,
                            map_srs=map_srs,
                            default_dataset_layers=default_dataset_layers)

    def demo_service(self, conf):
        from mapproxy.service.demo import DemoServer
        services = list(self.context.services.conf.keys())
        md = self.context.services.conf.get('wms', {}).get('md', {}).copy()
        md.update(conf.get('md', {}))
        layers = OrderedDict()
        for layer_name, layer_conf in self.context.layers.items():
            lyr = layer_conf.wms_layer()
            if lyr:
                layers[layer_name] = lyr
        image_formats = self.context.globals.get_value('image_formats', conf, global_key='wms.image_formats')
        srs = self.context.globals.get_value('srs', conf, global_key='wms.srs')
        tms_conf = self.context.services.conf.get('tms', {}) or {}
        use_grid_names = tms_conf.get('use_grid_names', False)
        tile_layers = self.tile_layers(tms_conf, use_grid_names=use_grid_names)

        # WMTS restful template
        wmts_conf = self.context.services.conf.get('wmts', {}) or {}
        from mapproxy.service.wmts import WMTSRestServer
        if wmts_conf:
            restful_template = wmts_conf.get('restful_template', WMTSRestServer.default_template)
        else:
            restful_template = WMTSRestServer.default_template

        if 'wmts' in self.context.services.conf:
            kvp = wmts_conf.get('kvp')
            restful = wmts_conf.get('restful')

            if kvp or kvp is None:
                services.append('wmts_kvp')
            if restful or restful is None:
                services.append('wmts_restful')

        if 'wms' in self.context.services.conf:
            versions = self.context.services.conf['wms'].get('versions', ['1.1.1'])
            if '1.1.1' in versions:
                # demo service only supports 1.1.1, use wms_111 as an indicator
                services.append('wms_111')

        layers = OrderedDict(sorted(layers.items(), key=lambda x: x[1].name))
        background = self.context.globals.get_value('background', conf)

        return DemoServer(
            layers, md, tile_layers=tile_layers, image_formats=image_formats, srs=srs, services=services,
            restful_template=restful_template, background=background)


def extents_for_srs(bbox_srs):
    from mapproxy.extent import DefaultMapExtent, MapExtent
    from mapproxy.srs import SRS
    extents = {}
    for srs in bbox_srs:
        if isinstance(srs, str):
            bbox = DefaultMapExtent()
        else:
            srs, bbox = srs['srs'], srs['bbox']
            bbox = MapExtent(bbox, SRS(srs))

        extents[srs] = bbox

    return extents


def fi_xslt_transformers(conf, context):
    from mapproxy.featureinfo import XSLTransformer
    fi_transformers = {}
    fi_xslt = conf.get('featureinfo_xslt')
    if fi_xslt:
        for info_type, fi_xslt in fi_xslt.items():
            fi_xslt = context.globals.abspath(fi_xslt)
            fi_transformers[info_type] = XSLTransformer(fi_xslt)
    return fi_transformers
