# This file is part of the MapProxy project.
# Copyright (C) 2010-2014 Omniscale <http://omniscale.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
WMS service handler
"""
from mapproxy.compat import iteritems
from mapproxy.compat.itertools import chain
from functools import partial
from mapproxy.cache.tile import CacheInfo
from mapproxy.request.wms import (wms_request, WMS111LegendGraphicRequest,
    mimetype_from_infotype, infotype_from_mimetype, switch_bbox_epsg_axis_order)
from mapproxy.srs import SRS, TransformationError
from mapproxy.service.base import Server
from mapproxy.response import Response
from mapproxy.source import SourceError
from mapproxy.exception import RequestError
from mapproxy.image import bbox_position_in_image, SubImageSource, BlankImageSource
from mapproxy.image.merge import concat_legends, LayerMerger
from mapproxy.image.opts import ImageOptions
from mapproxy.image.message import attribution_image, message_image
from mapproxy.layer import BlankImage, MapQuery, InfoQuery, LegendQuery, MapError, LimitedLayer
from mapproxy.layer import MapBBOXError, merge_layer_extents, merge_layer_res_ranges
from mapproxy.util import async
from mapproxy.util.py import cached_property, reraise
from mapproxy.util.coverage import load_limited_to
from mapproxy.util.ext.odict import odict
from mapproxy.template import template_loader, bunch, recursive_bunch
from mapproxy.service import template_helper
from mapproxy.layer import DefaultMapExtent, MapExtent

get_template = template_loader(__name__, 'templates', namespace=template_helper.__dict__)


class PERMIT_ALL_LAYERS(object):
    pass

class WMSServer(Server):
    service = 'wms'
    fi_transformers = None

    def __init__(self, root_layer, md, srs, image_formats,
        request_parser=None, tile_layers=None, attribution=None,
        info_types=None, strict=False, on_error='raise',
        concurrent_layer_renderer=1, max_output_pixels=None,
        srs_extents=None, max_tile_age=None,
        versions=None,
        inspire_md=None,
        ):
        Server.__init__(self)
        self.request_parser = request_parser or partial(wms_request, strict=strict, versions=versions)
        self.root_layer = root_layer
        self.layers = root_layer.child_layers()
        self.tile_layers = tile_layers or {}
        self.strict = strict
        self.attribution = attribution
        self.md = md
        self.on_error = on_error
        self.concurrent_layer_renderer = concurrent_layer_renderer
        self.image_formats = image_formats
        self.info_types = info_types
        self.srs = srs
        self.srs_extents = srs_extents
        self.max_output_pixels = max_output_pixels
        self.max_tile_age = max_tile_age
        self.inspire_md = inspire_md

    def map(self, map_request):
        self.check_map_request(map_request)

        params = map_request.params
        query = MapQuery(params.bbox, params.size, SRS(params.srs), params.format)

        if map_request.params.get('tiled', 'false').lower() == 'true':
            query.tiled_only = True
        orig_query = query

        if self.srs_extents and params.srs in self.srs_extents:
            # limit query to srs_extent if query is larger
            query_extent = MapExtent(params.bbox, SRS(params.srs))
            if not self.srs_extents[params.srs].contains(query_extent):
                limited_extent = self.srs_extents[params.srs].intersection(query_extent)
                if not limited_extent:
                    img_opts = self.image_formats[params.format_mime_type].copy()
                    img_opts.bgcolor = params.bgcolor
                    img_opts.transparent = params.transparent
                    img = BlankImageSource(size=params.size, image_opts=img_opts, cacheable=True)
                    return Response(img.as_buffer(), content_type=img_opts.format.mime_type)
                sub_size, offset, sub_bbox = bbox_position_in_image(params.bbox, params.size, limited_extent.bbox)
                query = MapQuery(sub_bbox, sub_size, SRS(params.srs), params.format)

        actual_layers = odict()
        for layer_name in map_request.params.layers:
            layer = self.layers[layer_name]
            # only add if layer renders the query
            if layer.renders_query(query):
                # if layer is not transparent and will be rendered,
                # remove already added (then hidden) layers
                if not layer.transparent:
                    actual_layers = odict()
                for layer_name, map_layers in layer.map_layers_for_query(query):
                    actual_layers[layer_name] = map_layers

        authorized_layers, coverage = self.authorized_layers('map', actual_layers.keys(),
            map_request.http.environ, query_extent=(query.srs.srs_code, query.bbox))

        self.filter_actual_layers(actual_layers, map_request.params.layers, authorized_layers)

        render_layers = []
        for layers in actual_layers.values():
            render_layers.extend(layers)

        self.update_query_with_fwd_params(query, params=params,
            layers=render_layers)

        raise_source_errors =  True if self.on_error == 'raise' else False
        renderer = LayerRenderer(render_layers, query, map_request,
                                 raise_source_errors=raise_source_errors,
                                 concurrent_rendering=self.concurrent_layer_renderer)

        merger = LayerMerger()
        renderer.render(merger)

        if self.attribution and self.attribution.get('text') and not query.tiled_only:
            merger.add(attribution_image(self.attribution['text'], query.size))
        img_opts = self.image_formats[params.format_mime_type].copy()
        img_opts.bgcolor = params.bgcolor
        img_opts.transparent = params.transparent
        result = merger.merge(size=query.size, image_opts=img_opts,
            bbox=query.bbox, bbox_srs=params.srs, coverage=coverage)

        if query != orig_query:
            result = SubImageSource(result, size=orig_query.size, offset=offset, image_opts=img_opts)

        # Provide the wrapping WSGI app or filter the opportunity to process the
        # image before it's wrapped up in a response
        result = self.decorate_img(result, 'wms.map', actual_layers.keys(),
            map_request.http.environ, (query.srs.srs_code, query.bbox))

        try:
            result_buf = result.as_buffer(img_opts)
        except IOError as ex:
            raise RequestError('error while processing image file: %s' % ex,
                request=map_request)

        resp = Response(result_buf, content_type=img_opts.format.mime_type)

        if query.tiled_only and isinstance(result.cacheable, CacheInfo):
            cache_info = result.cacheable
            resp.cache_headers(cache_info.timestamp, etag_data=(cache_info.timestamp, cache_info.size),
                               max_age=self.max_tile_age)
            resp.make_conditional(map_request.http)

        if not result.cacheable:
            resp.cache_headers(no_cache=True)

        return resp

    def capabilities(self, map_request):
        # TODO: debug layer
        # if '__debug__' in map_request.params:
        #     layers = self.layers.values()
        # else:
        #     layers = [layer for name, layer in iteritems(self.layers)
        #               if name != '__debug__']

        if map_request.params.get('tiled', 'false').lower() == 'true':
            tile_layers = self.tile_layers.values()
        else:
            tile_layers = []

        service = self._service_md(map_request)
        root_layer = self.authorized_capability_layers(map_request.http.environ)

        info_types = ['text', 'html', 'xml'] # defaults
        if self.info_types:
            info_types = self.info_types
        elif self.fi_transformers:
            info_types = self.fi_transformers.keys()
        info_formats = [mimetype_from_infotype(map_request.version, info_type) for info_type in info_types]
        result = Capabilities(service, root_layer, tile_layers,
            self.image_formats, info_formats, srs=self.srs, srs_extents=self.srs_extents,
            inspire_md=self.inspire_md,
            ).render(map_request)
        return Response(result, mimetype=map_request.mime_type)

    def featureinfo(self, request):
        infos = []
        self.check_featureinfo_request(request)

        p = request.params
        query = InfoQuery(p.bbox, p.size, SRS(p.srs), p.pos,
              p['info_format'], format=request.params.format or None,
              feature_count=p.get('feature_count'))

        actual_layers = odict()

        for layer_name in request.params.query_layers:
            layer = self.layers[layer_name]
            if not layer.queryable:
                raise RequestError('layer %s is not queryable' % layer_name, request=request)
            for layer_name, info_layers in layer.info_layers_for_query(query):
                actual_layers[layer_name] = info_layers

        authorized_layers, coverage = self.authorized_layers('featureinfo', actual_layers.keys(),
            request.http.environ, query_extent=(query.srs.srs_code, query.bbox))
        self.filter_actual_layers(actual_layers, request.params.layers, authorized_layers)

        # outside of auth-coverage
        if coverage and not coverage.contains(query.coord, query.srs):
            infos = []
        else:
            info_layers = []
            for layers in actual_layers.values():
                info_layers.extend(layers)

            for layer in info_layers:
                info = layer.get_info(query)
                if info is None:
                    continue
                infos.append(info)

        mimetype = None
        if 'info_format' in request.params:
            mimetype = request.params.info_format

        if not infos:
            return Response('', mimetype=mimetype)

        if self.fi_transformers:
            doc = infos[0].combine(infos)
            if doc.info_type == 'text':
                resp = doc.as_string()
                mimetype = 'text/plain'
            else:
                if not mimetype:
                    if 'xml' in self.fi_transformers:
                        info_type = 'xml'
                    elif 'html' in self.fi_transformers:
                        info_type = 'html'
                    else:
                        info_type = 'text'
                    mimetype = mimetype_from_infotype(request.version, info_type)
                else:
                    info_type = infotype_from_mimetype(request.version, mimetype)
                resp = self.fi_transformers[info_type](doc).as_string()
        else:
            mimetype = mimetype_from_infotype(request.version, infos[0].info_type)
            if len(infos) > 1:
                resp = infos[0].combine(infos).as_string()
            else:
                resp = infos[0].as_string()

        return Response(resp, mimetype=mimetype)

    def check_map_request(self, request):
        if self.max_output_pixels and \
            (request.params.size[0] * request.params.size[1]) > self.max_output_pixels:
            request.prevent_image_exception = True
            raise RequestError("image size too large", request=request)

        self.validate_layers(request)
        request.validate_format(self.image_formats)
        request.validate_srs(self.srs)

    def update_query_with_fwd_params(self, query, params, layers):
        # forward relevant request params into MapQuery.dimensions
        for layer in layers:
            if not hasattr(layer, 'fwd_req_params'):
                continue
            for p in layer.fwd_req_params:
                if p in params:
                    query.dimensions[p] = params[p]

    def check_featureinfo_request(self, request):
        self.validate_layers(request)
        request.validate_srs(self.srs)

    def validate_layers(self, request):
        query_layers = request.params.query_layers if hasattr(request, 'query_layers') else []
        for layer in chain(request.params.layers, query_layers):
            if layer not in self.layers:
                raise RequestError('unknown layer: ' + str(layer), code='LayerNotDefined',
                                   request=request)

    def check_legend_request(self, request):
        if request.params.layer not in self.layers:
            raise RequestError('unknown layer: ' + request.params.layer,
                               code='LayerNotDefined', request=request)

    #TODO: If layer not in self.layers raise RequestError
    def legendgraphic(self, request):
        legends = []
        self.check_legend_request(request)
        layer = request.params.layer
        if not self.layers[layer].has_legend:
            raise RequestError('layer %s has no legend graphic' % layer, request=request)
        legend = self.layers[layer].legend(request)

        [legends.append(i) for i in legend if i is not None]
        result = concat_legends(legends)
        if 'format' in request.params:
            mimetype = request.params.format_mime_type
        else:
            mimetype = 'image/png'
        img_opts = self.image_formats[request.params.format_mime_type]
        return Response(result.as_buffer(img_opts), mimetype=mimetype)

    def _service_md(self, map_request):
        md = dict(self.md)
        md['url'] = map_request.url
        md['has_legend'] = self.root_layer.has_legend
        return md

    def authorized_layers(self, feature, layers, env, query_extent):
        if 'mapproxy.authorize' in env:
            result = env['mapproxy.authorize']('wms.' + feature, layers[:],
                environ=env, query_extent=query_extent)
            if result['authorized'] == 'unauthenticated':
                raise RequestError('unauthorized', status=401)
            if result['authorized'] == 'full':
                return PERMIT_ALL_LAYERS, None
            layers = {}
            if result['authorized'] == 'partial':
                for layer_name, permissions in iteritems(result['layers']):
                    if permissions.get(feature, False) == True:
                        layers[layer_name] = permissions.get('limited_to')
            limited_to = result.get('limited_to')
            if limited_to:
                coverage = load_limited_to(limited_to)
            else:
                coverage = None
            return layers, coverage
        else:
            return PERMIT_ALL_LAYERS, None

    def filter_actual_layers(self, actual_layers, requested_layers, authorized_layers):
        if authorized_layers is not PERMIT_ALL_LAYERS:
            requested_layer_names = set(requested_layers)
            for layer_name in actual_layers.keys():
                if layer_name not in authorized_layers:
                    # check whether layer was requested explicit...
                    if layer_name in requested_layer_names:
                        raise RequestError('forbidden', status=403)
                    # or implicit (part of group layer)
                    else:
                        del actual_layers[layer_name]
                elif authorized_layers[layer_name] is not None:
                    limited_to = load_limited_to(authorized_layers[layer_name])
                    actual_layers[layer_name] = [LimitedLayer(lyr, limited_to) for lyr in actual_layers[layer_name]]

    def authorized_capability_layers(self, env):
        if 'mapproxy.authorize' in env:
            result = env['mapproxy.authorize']('wms.capabilities', self.layers.keys(), environ=env)
            if result['authorized'] == 'unauthenticated':
                raise RequestError('unauthorized', status=401)
            if result['authorized'] == 'full':
                return self.root_layer
            if result['authorized'] == 'partial':
                limited_to = result.get('limited_to')
                if limited_to:
                    coverage = load_limited_to(limited_to)
                else:
                    coverage = None
                return FilteredRootLayer(self.root_layer, result['layers'], coverage=coverage)
            raise RequestError('forbidden', status=403)
        else:
            return self.root_layer

class FilteredRootLayer(object):
    def __init__(self, root_layer, permissions, coverage=None):
        self.root_layer = root_layer
        self.permissions = permissions
        self.coverage = coverage

    def __getattr__(self, name):
        return getattr(self.root_layer, name)

    @cached_property
    def extent(self):
        layer_name = self.root_layer.name
        limited_to = self.permissions.get(layer_name, {}).get('limited_to')
        extent = self.root_layer.extent

        if limited_to:
            coverage = load_limited_to(limited_to)
            limited_coverage = coverage.intersection(extent.bbox, extent.srs)
            extent = limited_coverage.extent

        if self.coverage:
            limited_coverage = self.coverage.intersection(extent.bbox, extent.srs)
            extent = limited_coverage.extent
        return extent

    @property
    def queryable(self):
        if not self.root_layer.queryable: return False

        layer_name = self.root_layer.name
        if not layer_name or self.permissions.get(layer_name, {}).get('featureinfo', False):
            return True
        return False

    def layer_permitted(self, layer):
        if not self.permissions.get(layer.name, {}).get('map', False):
            return False
        extent = layer.extent

        limited_to = self.permissions.get(layer.name, {}).get('limited_to')
        if limited_to:
            coverage = load_limited_to(limited_to)
            if not coverage.intersects(extent.bbox, extent.srs):
                return False

        if self.coverage:
            if not self.coverage.intersects(extent.bbox, extent.srs):
                return False
        return True

    @cached_property
    def layers(self):
        layers = []
        for layer in self.root_layer.layers:
            if not layer.name or self.layer_permitted(layer):
                filtered_layer = FilteredRootLayer(layer, self.permissions, self.coverage)
                if filtered_layer.is_active or filtered_layer.layers:
                    # add filtered_layer only if it is active (no grouping layer)
                    # or if it contains other active layers
                    layers.append(filtered_layer)
        return layers

DEFAULT_EXTENTS = {
    'EPSG:3857': DefaultMapExtent(),
    'EPSG:4326': DefaultMapExtent(),
    'EPSG:900913': DefaultMapExtent(),
}

def limit_srs_extents(srs_extents, supported_srs):
    """
    Limit srs_extents to supported_srs.
    """
    if srs_extents:
        srs_extents = srs_extents.copy()
    else:
        srs_extents = DEFAULT_EXTENTS.copy()

    for srs in list(srs_extents.keys()):
        if srs not in supported_srs:
            srs_extents.pop(srs)

    return srs_extents

class Capabilities(object):
    """
    Renders WMS capabilities documents.
    """
    def __init__(self, server_md, layers, tile_layers, image_formats, info_formats,
        srs, srs_extents=None, epsg_axis_order=False,
        inspire_md=None,
        ):
        self.service = server_md
        self.layers = layers
        self.tile_layers = tile_layers
        self.image_formats = image_formats
        self.info_formats = info_formats
        self.srs = srs
        self.srs_extents = limit_srs_extents(srs_extents, srs)
        self.inspire_md = inspire_md

    def layer_srs_bbox(self, layer, epsg_axis_order=False):
        layer_srs_code = layer.extent.srs.srs_code
        for srs, extent in iteritems(self.srs_extents):
            if extent.is_default:
                bbox = layer.extent.bbox_for(SRS(srs))
            else:
                bbox = extent.bbox_for(SRS(srs))

            if epsg_axis_order:
                bbox = switch_bbox_epsg_axis_order(bbox, srs)
            yield srs, bbox

        # add native srs
        if layer_srs_code not in self.srs_extents:
            bbox = layer.extent.bbox
            if epsg_axis_order:
                bbox = switch_bbox_epsg_axis_order(bbox, layer_srs_code)
            yield layer_srs_code, bbox

    def render(self, _map_request):
        return self._render_template(_map_request.capabilities_template)

    def _render_template(self, template):
        template = get_template(template)
        inspire_md = None
        if self.inspire_md:
            inspire_md = recursive_bunch(default='', **self.inspire_md)
        doc = template.substitute(service=bunch(default='', **self.service),
                                   layers=self.layers,
                                   formats=self.image_formats,
                                   info_formats=self.info_formats,
                                   srs=self.srs,
                                   tile_layers=self.tile_layers,
                                   layer_srs_bbox=self.layer_srs_bbox,
                                   inspire_md=inspire_md,
        )
        # strip blank lines
        doc = '\n'.join(l for l in doc.split('\n') if l.rstrip())
        return doc

class LayerRenderer(object):
    def __init__(self, layers, query, request, raise_source_errors=True,
                 concurrent_rendering=1):
        self.layers = layers
        self.query = query
        self.request = request
        self.raise_source_errors = raise_source_errors
        self.concurrent_rendering = concurrent_rendering

    def render(self, layer_merger):
        render_layers = combined_layers(self.layers, self.query)
        if not render_layers: return

        async_pool = async.Pool(size=min(len(render_layers), self.concurrent_rendering))

        if self.raise_source_errors:
            return self._render_raise_exceptions(async_pool, render_layers, layer_merger)
        else:
            return self._render_capture_source_errors(async_pool, render_layers,
                                                      layer_merger)

    def _render_raise_exceptions(self, async_pool, render_layers, layer_merger):
        # call _render_layer, raise all exceptions
        try:
            for layer_task in async_pool.imap(self._render_layer, render_layers,
                                              use_result_objects=True):
                if layer_task.exception is None:
                    layer, layer_img = layer_task.result
                    if layer_img is not None:
                        layer_merger.add(layer_img, layer.coverage)
                else:
                    ex = layer_task.exception
                    async_pool.shutdown(True)
                    reraise(ex)
        except SourceError as ex:
            raise RequestError(ex.args[0], request=self.request)

    def _render_capture_source_errors(self, async_pool, render_layers, layer_merger):
        # call _render_layer, capture SourceError exceptions
        errors = []
        rendered = 0

        for layer_task in async_pool.imap(self._render_layer, render_layers,
                                          use_result_objects=True):
            if layer_task.exception is None:
                layer, layer_img = layer_task.result
                if layer_img is not None:
                    layer_merger.add(layer_img, layer.coverage)
                rendered += 1
            else:
                layer_merger.cacheable = False
                ex = layer_task.exception
                if isinstance(ex[1], SourceError):
                    errors.append(ex[1].args[0])
                else:
                    async_pool.shutdown(True)
                    reraise(ex)

        if render_layers and not rendered:
            errors = '\n'.join(errors)
            raise RequestError('Could not get any sources:\n'+errors, request=self.request)

        if errors:
            layer_merger.add(message_image('\n'.join(errors), self.query.size,
                image_opts=ImageOptions(transparent=True)))

    def _render_layer(self, layer):
        try:
            layer_img = layer.get_map(self.query)
            if layer_img is not None:
                layer_img.opacity = layer.opacity

            return layer, layer_img
        except SourceError:
            raise
        except MapBBOXError:
            raise RequestError('Request too large or invalid BBOX.', request=self.request)
        except MapError as e:
            raise RequestError('Invalid request: %s' % e.args[0], request=self.request)
        except TransformationError:
            raise RequestError('Could not transform BBOX: Invalid result.',
                request=self.request)
        except BlankImage:
            return layer, None

class WMSLayerBase(object):
    """
    Base class for WMS layer (layer groups and leaf layers).
    """

    "True if layer is an actual layer (not a group only)"
    is_active = True

    "list of sublayers"
    layers = []

    "metadata dictionary with tile, name, etc."
    md = {}

    "True if .info() is supported"
    queryable = False

    transparent = False

    "True is .legend() is supported"
    has_legend = False
    legend_url = None
    legend_size = None

    "resolution range (i.e. ScaleHint) of the layer"
    res_range = None
    "MapExtend of the layer"
    extent = None

    def is_opaque(self):
        return not self.transparent

    def map_layers_for_query(self, query):
        raise NotImplementedError()

    def legend(self, query):
        raise NotImplementedError()

    def info(self, query):
        raise NotImplementedError()

class WMSLayer(WMSLayerBase):
    """
    Class for WMS layers.

    Combines map, info and legend sources with metadata.
    """
    is_active = True
    layers = []
    def __init__(self, name, title, map_layers, info_layers=[], legend_layers=[],
                 res_range=None, md=None):
        self.name = name
        self.title = title
        self.md = md or {}
        self.map_layers = map_layers
        self.info_layers = info_layers
        self.legend_layers = legend_layers
        self.extent = merge_layer_extents(map_layers)
        if res_range is None:
            res_range = merge_layer_res_ranges(map_layers)
        self.res_range = res_range
        self.queryable = True if info_layers else False
        self.transparent = all(not map_lyr.is_opaque() for map_lyr in self.map_layers)
        self.has_legend = True if legend_layers else False

    def renders_query(self, query):
        if self.res_range and not self.res_range.contains(query.bbox, query.size, query.srs):
            return False
        return True

    def map_layers_for_query(self, query):
        if not self.map_layers:
            return []
        return [(self.name, self.map_layers)]

    def info_layers_for_query(self, query):
        if not self.info_layers:
            return []
        return [(self.name, self.info_layers)]

    def legend(self, request):
        p = request.params
        query = LegendQuery(p.format, p.scale)

        for lyr in self.legend_layers:
            yield lyr.get_legend(query)

    @property
    def legend_size(self):
        width = 0
        height = 0
        for layer in self.legend_layers:
            width = max(layer.size[0], width)
            height += layer.size[1]
        return (width, height)

    @property
    def legend_url(self):
        if self.has_legend:
            req = WMS111LegendGraphicRequest(url='?',
                param=dict(format='image/png', layer=self.name, sld_version='1.1.0'))
            return req.complete_url
        else:
            return None

    def child_layers(self):
        return {self.name: self}


class WMSGroupLayer(WMSLayerBase):
    """
    Class for WMS group layers.

    Groups multiple wms layers, but can also contain a single layer (``this``)
    that represents this layer.
    """
    def __init__(self, name, title, this, layers, md=None):
        self.name = name
        self.title = title
        self.this = this
        self.md = md or {}
        self.is_active = True if this is not None else False
        self.layers = layers
        self.transparent = True if this and not this.is_opaque() or all(not l.is_opaque() for l in layers) else False
        self.has_legend = True if this and this.has_legend or any(l.has_legend for l in layers) else False
        self.queryable = True if this and this.queryable or any(l.queryable for l in layers) else False
        all_layers = layers + ([self.this] if self.this else [])
        self.extent = merge_layer_extents(all_layers)
        self.res_range = merge_layer_res_ranges(all_layers)

    @property
    def legend_size(self):
        return self.this.legend_size

    @property
    def legend_url(self):
        return self.this.legend_url

    def renders_query(self, query):
        if self.res_range and not self.res_range.contains(query.bbox, query.size, query.srs):
            return False
        return True

    def map_layers_for_query(self, query):
        if self.this:
            return self.this.map_layers_for_query(query)
        else:
            layers = []
            for layer in self.layers:
                layers.extend(layer.map_layers_for_query(query))
            return layers

    def info_layers_for_query(self, query):
        if self.this:
            return self.this.info_layers_for_query(query)
        else:
            layers = []
            for layer in self.layers:
                layers.extend(layer.info_layers_for_query(query))
            return layers

    def child_layers(self):
        layers = odict()
        if self.name:
            layers[self.name] = self
        for lyr in self.layers:
            if hasattr(lyr, 'child_layers'):
                layers.update(lyr.child_layers())
            elif lyr.name:
                layers[lyr.name] = lyr
        return layers


def combined_layers(layers, query):
    """
    Returns a new list of the layers where all adjacent layers are combined
    if possible.
    """
    if len(layers) <= 1:
        return layers
    layers = layers[:]
    combined_layers = [layers.pop(0)]
    while layers:
        current_layer = layers.pop(0)
        combined = combined_layers[-1].combined_layer(current_layer, query)
        if combined:
            # change last layer with combined
            combined_layers[-1] = combined
        else:
            combined_layers.append(current_layer)
    return combined_layers
