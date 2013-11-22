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
                 supported_srs=None, supported_formats=None, fwd_req_params=None):
        MapLayer.__init__(self, image_opts=image_opts)
        self.client = client
        self.supported_srs = supported_srs or []
        self.supported_formats = supported_formats or []
        self.fwd_req_params = fwd_req_params or set()

        self.transparent_color = transparent_color
        self.transparent_color_tolerance = transparent_color_tolerance
        if self.transparent_color:
            self.transparent = True
        self.coverage = coverage
        self.res_range = res_range
        if self.coverage:
            self.extent = MapExtent(self.coverage.bbox, self.coverage.srs)
        else:
            self.extent = DefaultMapExtent()

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
            log.warn('could not retrieve WMS map: %s', e)
            reraise_exception(SourceError(e.args[0]), sys.exc_info())

    def _get_map(self, query):
        format = self.image_opts.format
        if not format:
            format = query.format
        if self.supported_formats and format not in self.supported_formats:
            format = self.supported_formats[0]
        if self.supported_srs:
            if query.srs not in self.supported_srs:
                return self._get_transformed(query, format)
            # some srs are equal but not the same (e.g. 900913/3857)
            # use only supported srs so we use the right srs code.
            idx = self.supported_srs.index(query.srs)
            if self.supported_srs[idx] is not query.srs:
                query.srs = self.supported_srs[idx]
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
        src_srs = self._best_supported_srs(dst_srs)
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

    def _best_supported_srs(self, srs):
        latlong = srs.is_latlong

        for srs in self.supported_srs:
            if srs.is_latlong == latlong:
                return srs

        # else
        return self.supported_srs[0]

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
    def __init__(self, client, fi_transformer=None):
        self.client = client
        self.fi_transformer = fi_transformer

    def get_info(self, query):
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

