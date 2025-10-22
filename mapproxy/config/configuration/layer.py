from __future__ import division

from mapproxy.config.configuration.base import ConfigurationBase
from mapproxy.config.configuration.cache import cache_source_names
from mapproxy.config.configuration.source import WMSSourceConfiguration, resolution_range
from mapproxy.config.configuration.base import ConfigurationError
from mapproxy.util.py import memoize

import logging

log = logging.getLogger('mapproxy.config')


class WMSLayerConfiguration(ConfigurationBase):
    @memoize
    def wms_layer(self):
        from mapproxy.service.wms import WMSGroupLayer

        layers = []
        this_layer = None

        if 'layers' in self.conf:
            layers_conf = self.conf['layers']
            for layer_conf in layers_conf:
                lyr = WMSLayerConfiguration(layer_conf, self.context).wms_layer()
                if lyr:
                    layers.append(lyr)

        if 'sources' in self.conf or 'legendurl' in self.conf:
            this_layer = LayerConfiguration(self.conf, self.context).wms_layer()

        if not layers and not this_layer:
            return None

        if not layers:
            layer = this_layer
        else:
            layer = WMSGroupLayer(name=self.conf.get('name'), title=self.conf.get('title'),
                                  this=this_layer, layers=layers, md=self.conf.get('md'))
        return layer


class LayerConfiguration(ConfigurationBase):
    @memoize
    def wms_layer(self):
        from mapproxy.service.wms import WMSLayer
        from mapproxy.grid.resolutions import res_to_ogc_scale

        sources = []
        fi_sources = []
        lg_sources = []

        lg_sources_configured = False
        if self.conf.get('legendurl'):
            legend_url = self.conf['legendurl']
            lg_sources.append(WMSSourceConfiguration.static_legend_source(legend_url, self.context))
            lg_sources_configured = True

        for source_name in self.conf.get('sources', []):
            fi_source_names = []
            lg_source_names = []
            if source_name in self.context.caches:
                map_layer = self.context.caches[source_name].map_layer()
                fi_source_names = cache_source_names(self.context, source_name)
                lg_source_names = cache_source_names(self.context, source_name)
            elif source_name in self.context.sources:
                source_conf = self.context.sources[source_name]
                if not source_conf.supports_meta_tiles:
                    raise ConfigurationError('source "%s" of layer "%s" does not support un-tiled access'
                                             % (source_name, self.conf.get('name')))
                map_layer = source_conf.source()
                fi_source_names = [source_name]
                lg_source_names = [source_name]
            else:
                raise ConfigurationError('source/cache "%s" not found' % source_name)

            if map_layer:
                sources.append(map_layer)

            for fi_source_name in fi_source_names:
                if fi_source_name not in self.context.sources:
                    continue
                if not hasattr(self.context.sources[fi_source_name], 'fi_source'):
                    continue
                fi_source = self.context.sources[fi_source_name].fi_source()
                if fi_source:
                    fi_sources.append(fi_source)
            if not lg_sources_configured:
                for lg_source_name in lg_source_names:
                    if lg_source_name not in self.context.sources:
                        continue
                    if not hasattr(self.context.sources[lg_source_name], 'lg_source'):
                        continue
                    lg_source = self.context.sources[lg_source_name].lg_source()
                    if lg_source:
                        lg_sources.append(lg_source)

        res_range = resolution_range(self.conf)
        dimensions = None
        if 'dimensions' in self.conf.keys():
            dimensions = self.dimensions()

        nominal_scale = self.conf.get('nominal_scale')
        if not nominal_scale:
            nominal_res = self.conf.get('nominal_res')
            if nominal_res:
                nominal_scale = res_to_ogc_scale(nominal_res)

        layer = WMSLayer(
            self.conf.get('name'), self.conf.get('title'), sources, fi_sources, lg_sources, res_range=res_range,
            md=self.conf.get('md'), dimensions=dimensions,
            nominal_scale=nominal_scale)
        return layer

    @memoize
    def dimensions(self):
        from mapproxy.layer import Dimension
        from mapproxy.util.ext.wmsparse.util import parse_datetime_range
        dimensions = {}
        for dimension, conf in self.conf.get('dimensions', {}).items():
            raw_values = conf.get('values')
            if len(raw_values) == 1:
                # look for time or dim_reference_time
                if 'time' in dimension.lower():
                    log.debug('Determining values as datetime strings')
                    values = parse_datetime_range(raw_values[0])
                else:
                    log.debug('Determining values as plain strings')
                    values = raw_values[0].strip().split('/')
            else:
                values = [str(val) for val in conf.get('values', ['default'])]

            default = conf.get('default', values[-1])
            dimensions[dimension.lower()] = Dimension(dimension, values, default=default)
        return dimensions

    @memoize
    def tile_layers(self, grid_name_as_path=False):
        from mapproxy.service.tile import TileLayer
        from mapproxy.cache.dummy import DummyCache
        sources = []
        fi_only_sources = []
        if 'tile_sources' in self.conf:
            sources = self.conf['tile_sources']
        else:
            for source_name in self.conf.get('sources', []):
                # we only support caches for tiled access...
                if source_name not in self.context.caches:
                    if source_name in self.context.sources:
                        src_conf = self.context.sources[source_name].conf
                        # but we ignore debug layers for convenience
                        if src_conf['type'] == 'debug':
                            continue
                        # and WMS layers with map: False (i.e. FeatureInfo only sources)
                        if src_conf['type'] == 'wms' and src_conf.get('wms_opts', {}).get('map', True) is False:
                            fi_only_sources.append(source_name)
                            continue

                    return []
                sources.append(source_name)

            if len(sources) > 1:
                # skip layers with more then one source
                return []

        dimensions = self.dimensions()

        tile_layers = []
        for cache_name in sources:
            fi_sources = []
            fi_source_names = cache_source_names(self.context, cache_name)

            for fi_source_name in fi_source_names + fi_only_sources:
                if fi_source_name not in self.context.sources:
                    continue
                if not hasattr(self.context.sources[fi_source_name], 'fi_source'):
                    continue
                fi_source = self.context.sources[fi_source_name].fi_source()
                if fi_source:
                    fi_sources.append(fi_source)

            for grid, extent, cache_source in self.context.caches[cache_name].caches():
                disable_storage = self.context.configuration['caches'][cache_name].get('disable_storage', False)
                if disable_storage:
                    supports_dimensions = isinstance(cache_source.cache, DummyCache)
                else:
                    supports_dimensions = cache_source.cache.supports_dimensions
                if dimensions and not supports_dimensions:
                    # caching of dimension layers is not supported yet
                    raise ConfigurationError(
                        "caching of dimension layer (%s) is not supported yet."
                        " need to `disable_storage: true` on %s cache" % (self.conf['name'], cache_name)
                    )

                md = {}
                md['title'] = self.conf['title']
                md['name'] = self.conf['name']
                md['grid_name'] = grid.name
                if grid_name_as_path:
                    md['name_path'] = (md['name'], md['grid_name'])
                else:
                    md['name_path'] = (md['name'], grid.srs.srs_code.replace(':', '').upper())
                md['name_internal'] = md['name_path'][0] + '_' + md['name_path'][1]
                md['format'] = self.context.caches[cache_name].image_opts().format
                md['cache_name'] = cache_name
                md['extent'] = extent
                md['wmts_kvp_legendurl'] = self.conf.get('wmts_kvp_legendurl')
                md['wmts_rest_legendurl'] = self.conf.get('wmts_rest_legendurl')
                if 'legendurl' in self.conf:
                    wms_conf = self.context.services.conf.get('wms')
                    if wms_conf is not None:
                        versions = wms_conf.get('versions', ['1.3.0'])
                        versions.sort(key=lambda s: [int(u) for u in s.split('.')])
                        legendurl = (f'{{base_url}}/service?service=WMS&amp;request=GetLegendGraphic&amp;'
                                     f'version={versions[-1]}&amp;format=image%2Fpng&amp;layer={{layer_name}}')
                        if md['wmts_kvp_legendurl'] is None:
                            md['wmts_kvp_legendurl'] = legendurl
                        if md['wmts_rest_legendurl'] is None:
                            md['wmts_rest_legendurl'] = legendurl
                tile_layers.append(
                    TileLayer(
                        self.conf['name'], self.conf['title'],
                        info_sources=fi_sources,
                        md=md,
                        tile_manager=cache_source,
                        dimensions=dimensions
                    )
                )

        return tile_layers
