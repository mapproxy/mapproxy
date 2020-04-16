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
WMS clients for maps and information.
"""
import sys

from mapproxy.compat import text_type
from mapproxy.request.base import split_mime_type
from mapproxy.layer import InfoQuery
from mapproxy.source import SourceError
from mapproxy.client.http import HTTPClient
from mapproxy.srs import make_lin_transf, SRS, SupportedSRS
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.featureinfo import create_featureinfo_doc

import logging
log = logging.getLogger('mapproxy.source.wms')

class WMSClient(object):
    def __init__(self, request_template, http_client=None,
                 http_method=None, lock=None, fwd_req_params=None):
        self.request_template = request_template
        self.http_client = http_client or HTTPClient()
        self.http_method = http_method
        self.lock = lock
        self.fwd_req_params = fwd_req_params or set()

    def retrieve(self, query, format):
        if self.http_method == 'POST':
            request_method = 'POST'
        elif self.http_method == 'GET':
            request_method = 'GET'
        else: # 'AUTO'
            if 'sld_body' in self.request_template.params:
                request_method = 'POST'
            else:
                request_method = 'GET'

        if request_method == 'POST':
            url, data = self._query_data(query, format)
            if isinstance(data, text_type):
                data = data.encode('utf-8')
        else:
            url = self._query_url(query, format)
            data = None

        if self.lock:
            with self.lock():
                resp = self.http_client.open(url, data=data)
        else:
            resp = self.http_client.open(url, data=data)
        self._check_resp(resp, url)
        return resp

    def _check_resp(self, resp, url):
        if not resp.headers.get('Content-type', 'image/').startswith('image/'):
            # log response depending on content-type
            if resp.headers['Content-type'].startswith(('text/', 'application/vnd.ogc')):
                log_size = 8000 # larger xml exception
            else:
                log_size = 100 # image?
            data = resp.read(log_size+1)

            truncated = ''
            if len(data) == log_size+1:
                data = data[:-1]
                truncated = ' [output truncated]'

            if sys.version_info >= (3, 5, 0):
                data = data.decode('utf-8', 'backslashreplace')
            else:
                data = data.decode('ascii', 'ignore')

            log.warning("no image returned from source WMS: {}, response was: '{}'{}".format(url, data, truncated))
            raise SourceError('no image returned from source WMS: %s' % (url, ))

    def _query_url(self, query, format):
        return self._query_req(query, format).complete_url

    def _query_data(self, query, format):
        req = self._query_req(query, format)
        return req.url.rstrip('?'), req.query_string

    def _query_req(self, query, format):
        req = self.request_template.copy()
        req.params.bbox = query.bbox
        req.params.size = query.size
        req.params.srs = query.srs.srs_code
        req.params.format = format
        # also forward dimension request params if available in the query
        req.params.update(query.dimensions_for_params(self.fwd_req_params))
        return req

    def combined_client(self, other, query):
        """
        Return a new WMSClient that combines this request with the `other`. Returns
        ``None`` if the clients are not combinable (e.g. different URLs).
        """
        if self.request_template.url != other.request_template.url:
            return None

        new_req = self.request_template.copy()
        new_req.params.layers = new_req.params.layers + other.request_template.params.layers

        return WMSClient(new_req, http_client=self.http_client,
                http_method=self.http_method, fwd_req_params=self.fwd_req_params)


class WMSInfoClient(object):
    def __init__(self, request_template, supported_srs=None, http_client=None):
        self.request_template = request_template
        self.http_client = http_client or HTTPClient()
        if not supported_srs and self.request_template.params.srs is not None:
            supported_srs = SupportedSRS([SRS(self.request_template.params.srs)])
        self.supported_srs = supported_srs

    def get_info(self, query):
        if self.supported_srs and query.srs not in self.supported_srs:
            query = self._get_transformed_query(query)
        resp = self._retrieve(query)

        # use from template if available
        info_format = self.request_template.params.get('info_format')
        if not info_format:
            # otherwise from response
            info_format = resp.headers.get('Content-type', None)
        if not info_format:
            # otherwise from query
            info_format = query.info_format
        return create_featureinfo_doc(resp.read(), info_format)

    def _get_transformed_query(self, query):
        """
        Handle FI requests for unsupported SRS.
        """
        req_srs = query.srs
        req_bbox = query.bbox
        req_coord = make_lin_transf((0, 0, query.size[0], query.size[1]), req_bbox)(query.pos)

        info_srs = self.supported_srs.best_srs(req_srs)
        info_bbox = req_srs.transform_bbox_to(info_srs, req_bbox)
        # calculate new info_size to keep square pixels after transform_bbox_to
        info_aratio = (info_bbox[3] - info_bbox[1])/(info_bbox[2] - info_bbox[0])
        info_size = query.size[0], int(info_aratio*query.size[0])

        info_coord = req_srs.transform_to(info_srs, req_coord)
        info_pos = make_lin_transf((info_bbox), (0, 0, info_size[0], info_size[1]))(info_coord)
        info_pos = int(round(info_pos[0])), int(round(info_pos[1]))

        info_query = InfoQuery(
            bbox=info_bbox,
            size=info_size,
            srs=info_srs,
            pos=info_pos,
            info_format=query.info_format,
            feature_count=query.feature_count,
        )
        return info_query

    def _retrieve(self, query):
        url = self._query_url(query)
        return self.http_client.open(url)

    def _query_url(self, query):
        req = self.request_template.copy()
        req.params.bbox = query.bbox
        req.params.size = query.size
        req.params.pos = query.pos
        if query.feature_count:
            req.params['feature_count'] = query.feature_count
        req.params['query_layers'] = req.params['layers']
        if not 'info_format' in req.params and query.info_format:
            req.params['info_format'] = query.info_format
        if not req.params.format:
            req.params.format = query.format or 'image/png'
        req.params.srs = query.srs.srs_code

        return req.complete_url

class WMSLegendClient(object):
    def __init__(self, request_template, http_client=None):
        self.request_template = request_template
        self.http_client = http_client or HTTPClient()

    def get_legend(self, query):
        resp = self._retrieve(query)
        format = split_mime_type(query.format)[1]
        self._check_resp(resp)
        return ImageSource(resp, image_opts=ImageOptions(format=format))

    def _retrieve(self, query):
        url = self._query_url(query)
        return self.http_client.open(url)

    def _check_resp(self, resp):
        if not resp.headers.get('Content-type', 'image/').startswith('image/'):
            raise SourceError('no image returned from source WMS')

    def _query_url(self, query):
        req = self.request_template.copy()
        if not req.params.format:
            req.params.format = query.format or 'image/png'
        if query.scale:
            req.params['scale'] = query.scale
        return req.complete_url

    @property
    def identifier(self):
        return (self.request_template.url, self.request_template.params.layer)

class WMSLegendURLClient(object):
    def __init__(self, static_url, http_client=None):
        self.url = static_url
        self.http_client = http_client or HTTPClient()

    def get_legend(self, query):
        resp = self.http_client.open(self.url)
        format = split_mime_type(query.format)[1]
        self._check_resp(resp)
        return ImageSource(resp, image_opts=ImageOptions(format=format))

    def _check_resp(self, resp):
        if not resp.headers.get('Content-type', 'image/').startswith('image/'):
            raise SourceError('no image returned from static LegendURL')

    @property
    def identifier(self):
        return (self.url, None)

