# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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
Retrieve maps/information from WMS servers.
"""
import sys
from mapproxy.request.base import split_mime_type
from mapproxy.cache.legend import Legend, legend_identifier
from mapproxy.image import make_transparent, ImageSource, SubImageSource, bbox_position_in_image
from mapproxy.image.merge import concat_legends
from mapproxy.image.transform import ImageTransformer
from mapproxy.layer import MapExtent, DefaultMapExtent, BlankImage, LegendQuery, MapQuery, MapLayer
from mapproxy.source import InfoSource, SourceError, LegendSource
from mapproxy.client.http import HTTPClientError
from mapproxy.util.py import reraise_exception

import logging
log = logging.getLogger('mapproxy.source.wms')

class WMSSource(MapLayer):
    supports_meta_tiles = True
    def __init__(self, client, image_opts=None, coverage=None, res_range=None,
                 transparent_color=None, transparent_color_tolerance=None,
                 supported_srs=None, supported_formats=None, fwd_req_params=None,
                 error_handler=None):
        MapLayer.__init__(self, image_opts=image_opts)
        self.client = client
        self.supported_srs = supported_srs or []
        self.supported_formats = supported_formats or []
        self.fwd_req_params = fwd_req_params or set()

        self.transparent_color = transparent_color
        self.transparent_color_tolerance = transparent_color_tolerance
        if self.transparent_color:
            self.image_opts.transparent = True
        self.coverage = coverage
        self.res_range = res_range
        if self.coverage:
            self.extent = MapExtent(self.coverage.bbox, self.coverage.srs)
        else:
            self.extent = DefaultMapExtent()
        self.error_handler = error_handler

    def is_opaque(self, query):
        """
        Returns true if we are sure that the image is not transparent.
        """
        if self.res_range and not self.res_range.contains(query.bbox, query.size,
                                                          query.srs):
            return False

        if self.image_opts.transparent:
            return False

        if self.opacity is not None and (0.0 < self.opacity < 0.99):
            return False

        if not self.coverage:
            # not transparent and no coverage
            return True

        if self.coverage.contains(query.bbox, query.srs):
            # not transparent and completely inside coverage
            return True

        return False

    def get_map(self, query):
        if self.res_range and not self.res_range.contains(query.bbox, query.size,
                                                          query.srs):
            raise BlankImage()
        if self.coverage and not self.coverage.intersects(query.bbox, query.srs):
            raise BlankImage()
        try:
            resp = self._get_map(query)
            if self.transparent_color:
                resp = make_transparent(resp, self.transparent_color,
                                        self.transparent_color_tolerance)
            resp.opacity = self.opacity
            return resp

        except HTTPClientError as e:
            if self.error_handler:
                resp = self.error_handler.handle(e.response_code, query)
                if resp:
                    return resp
            log.warning('could not retrieve WMS map: %s', e.full_msg or e)
            reraise_exception(SourceError(e.args[0]), sys.exc_info())

    def _get_map(self, query):
        format = self.image_opts.format
        if not format:
            format = query.format
        if self.supported_formats and format not in self.supported_formats:
            format = self.supported_formats[0]
        if self.supported_srs:
            # srs can be equal while still having a different srs_code (EPSG:3857/900913), make sure to use a supported srs_code
            request_srs = None
            for srs in self.supported_srs:
                if query.srs == srs:
                    request_srs = srs
                    break
            if request_srs is None:
                return self._get_transformed(query, format)
            if query.srs.srs_code != request_srs.srs_code:
                query.srs = request_srs
        if self.extent and not self.extent.contains(MapExtent(query.bbox, query.srs)):
            return self._get_sub_query(query, format)
        resp = self.client.retrieve(query, format)
        return ImageSource(resp, size=query.size, image_opts=self.image_opts)

    def _get_sub_query(self, query, format):
        size, offset, bbox = bbox_position_in_image(query.bbox, query.size, self.extent.bbox_for(query.srs))
        if size[0] == 0 or size[1] == 0:
            raise BlankImage()
        src_query = MapQuery(bbox, size, query.srs, format, dimensions=query.dimensions)
        resp = self.client.retrieve(src_query, format)
        return SubImageSource(resp, size=query.size, offset=offset, image_opts=self.image_opts)

    def _get_transformed(self, query, format):
        dst_srs = query.srs
        src_srs = self.supported_srs.best_srs(dst_srs)
        dst_bbox = query.bbox
        src_bbox = dst_srs.transform_bbox_to(src_srs, dst_bbox)

        src_width, src_height = src_bbox[2]-src_bbox[0], src_bbox[3]-src_bbox[1]
        ratio = src_width/src_height
        dst_size = query.size
        xres, yres = src_width/dst_size[0], src_height/dst_size[1]
        if xres < yres:
            src_size = dst_size[0], int(dst_size[0]/ratio + 0.5)
        else:
            src_size = int(dst_size[1]*ratio +0.5), dst_size[1]

        src_query = MapQuery(src_bbox, src_size, src_srs, format, dimensions=query.dimensions)

        if self.coverage and not self.coverage.contains(src_bbox, src_srs):
            img = self._get_sub_query(src_query, format)
        else:
            resp = self.client.retrieve(src_query, format)
            img = ImageSource(resp, size=src_size, image_opts=self.image_opts)

        img = ImageTransformer(src_srs, dst_srs).transform(img, src_bbox,
            query.size, dst_bbox, self.image_opts)

        img.format = format
        return img

    def _is_compatible(self, other, query):
        if not isinstance(other, WMSSource):
            return False

        if self.opacity is not None or other.opacity is not None:
            return False

        if self.supported_srs != other.supported_srs:
            return False

        if self.supported_formats != other.supported_formats:
            return False

        if self.transparent_color != other.transparent_color:
            return False

        if self.transparent_color_tolerance != other.transparent_color_tolerance:
            return False

        if self.coverage != other.coverage:
            return False


        if (query.dimensions_for_params(self.fwd_req_params) !=
            query.dimensions_for_params(other.fwd_req_params)):
            return False

        return True

    def combined_layer(self, other, query):
        if not self._is_compatible(other, query):
            return None

        client = self.client.combined_client(other.client, query)
        if not client:
            return None

        return WMSSource(client, image_opts=self.image_opts,
            transparent_color=self.transparent_color,
            transparent_color_tolerance=self.transparent_color_tolerance,
            supported_srs=self.supported_srs,
            supported_formats=self.supported_formats,
            res_range=None, # layer outside res_range should already be filtered out
            coverage=self.coverage,
            fwd_req_params=self.fwd_req_params,
        )

class WMSInfoSource(InfoSource):
    def __init__(self, client, fi_transformer=None, coverage=None):
        self.client = client
        self.fi_transformer = fi_transformer
        self.coverage = coverage

    def get_info(self, query):
        if self.coverage and not self.coverage.contains(query.coord, query.srs):
            return None
        doc = self.client.get_info(query)
        if self.fi_transformer:
            doc = self.fi_transformer(doc)
        return doc


class WMSLegendSource(LegendSource):
    def __init__(self, clients, legend_cache, static=False):
        self.clients = clients
        self.identifier = legend_identifier([c.identifier for c in self.clients])
        self._cache = legend_cache
        self._size = None
        self.static = static

    @property
    def size(self):
        if not self._size:
            legend = self.get_legend(LegendQuery(format='image/png', scale=None))
            # TODO image size without as_image?
            self._size = legend.as_image().size
        return self._size

    def get_legend(self, query):
        if self.static:
            # prevent caching of static legends for different scales
            legend = Legend(id=self.identifier, scale=None)
        else:
            legend = Legend(id=self.identifier, scale=query.scale)
        if not self._cache.load(legend):
            legends = []
            error_occured = False
            for client in self.clients:
                try:
                    legends.append(client.get_legend(query))
                except HTTPClientError as e:
                    error_occured = True
                    log.error(e.args[0])
                except SourceError as e:
                    error_occured = True
                    # TODO errors?
                    log.error(e.args[0])
            format = split_mime_type(query.format)[1]
            legend = Legend(source=concat_legends(legends, format=format),
                            id=self.identifier, scale=query.scale)
            if not error_occured:
                self._cache.store(legend)
        return legend.source

