# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
WMS clients for maps and information.
"""
from __future__ import with_statement
from mapproxy.request.base import split_mime_type
from mapproxy.config import base_config
from mapproxy.layer import MapQuery, InfoQuery
from mapproxy.source import SourceError
from mapproxy.client.http import HTTPClient
from mapproxy.srs import make_lin_transf, SRS
from mapproxy.image import ImageSource
from mapproxy.image.transform import ImageTransformer
from mapproxy.featureinfo import create_featureinfo_doc

import logging
log = logging.getLogger(__name__)

class WMSClient(object):
    def __init__(self, request_template, supported_srs=None, http_client=None,
                 http_method=None, resampling=None, supported_formats=None,
                 lock=None):
        self.request_template = request_template
        self.http_client = http_client or HTTPClient()
        self.http_method = http_method
        self.supported_srs = supported_srs or []
        self.supported_formats = supported_formats or []
        self.resampling = resampling or base_config().image.resampling_method
        self.lock = lock
    
    def get_map(self, query):
        format = self.request_template.params.format
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
        resp = self._retrieve(query, format)
        return ImageSource(resp, size=query.size, format=format,
                           transparent=self.request_template.params.transparent)
    
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
        
        src_query = MapQuery(src_bbox, src_size, src_srs, format)
        resp = self._retrieve(src_query, format)
        
        img = ImageSource(resp, format, size=src_size,
                          transparent=self.request_template.params.transparent)
        
        img = ImageTransformer(src_srs, dst_srs, self.resampling).transform(img, src_bbox, 
            query.size, dst_bbox)
        
        img.format = format
        return img
    
    def _best_supported_srs(self, srs):
        latlong = srs.is_latlong
        
        for srs in self.supported_srs:
            if srs.is_latlong == latlong:
                return srs
        
        # else
        return self.supported_srs[0]
    
    def _retrieve(self, query, format):
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
        else:
            url = self._query_url(query, format)
            data = None
        
        if self.lock:
            with self.lock():
                resp = self.http_client.open(url, data=data)
        else:
            resp = self.http_client.open(url, data=data)
        self._check_resp(resp)
        return resp
    
    def _check_resp(self, resp):
        if 'Content-type' not in resp.headers:
            raise SourceError('response from source WMS has no Content-type header')
        if not resp.headers['Content-type'].startswith('image/'):
            log.warn("expected image response, got: %s", resp.read(8000))
            raise SourceError('no image returned from source WMS')
    
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
        return req
    
    def combined_client(self, other, query):
        """
        Return a new WMSClient that combines this request with the `other`. Returns
        ``None`` if the clients are not combinable (e.g. different URLs).
        """
        if self.request_template.url != other.request_template.url:
            return None
        
        if self.supported_srs != other.supported_srs:
          return None
        
        if self.supported_formats != other.supported_formats:
          return None
        
        new_req = self.request_template.copy()
        new_req.params.layers = new_req.params.layers + other.request_template.params.layers
        
        return WMSClient(new_req, http_client=self.http_client, http_method=self.http_method,
                         resampling=self.resampling)
        

class WMSInfoClient(object):
    def __init__(self, request_template, supported_srs=None, http_client=None):
        self.request_template = request_template
        self.http_client = http_client or HTTPClient()
        if not supported_srs and self.request_template.params.srs is not None:
            supported_srs = [SRS(self.request_template.params.srs)]
        self.supported_srs = supported_srs or []
    
    def get_info(self, query):
        if self.supported_srs and query.srs not in self.supported_srs:
            query = self._get_transformed_query(query)
        resp = self._retrieve(query)
        info_format = resp.headers.get('Content-type', None)
        if not info_format:
            info_format = query.info_format
        return create_featureinfo_doc(resp.read(), info_format)
    
    def _get_transformed_query(self, query):
        """
        Handle FI requests for unsupported SRS.
        """
        req_srs = query.srs
        req_bbox = query.bbox
        info_srs = self._best_supported_srs(req_srs)
        info_bbox = req_srs.transform_bbox_to(info_srs, req_bbox)
        
        req_coord = make_lin_transf((0, query.size[1], query.size[0], 0), req_bbox)(query.pos)
        
        info_coord = req_srs.transform_to(info_srs, req_coord)
        info_pos = make_lin_transf((info_bbox), (0, query.size[1], query.size[0], 0))(info_coord)
        
        info_query = InfoQuery(info_bbox, query.size, info_srs, info_pos, query.info_format)
        return info_query
    
    def _best_supported_srs(self, srs):
        # always choose the first, distortion should not matter
        return self.supported_srs[0]
    
    def _retrieve(self, query):
        url = self._query_url(query)
        return self.http_client.open(url)
    
    def _query_url(self, query):
        req = self.request_template.copy()
        req.params.bbox = query.bbox
        req.params.size = query.size
        req.params.pos = query.pos
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
        return ImageSource(resp, format=format)
    
    def _retrieve(self, query):
        url = self._query_url(query)
        return self.http_client.open(url)
    
    def _check_resp(self, resp):
        if 'Content-type' not in resp.headers:
            raise SourceError('response from source WMS has no Content-type header')
        if not resp.headers['Content-type'].startswith('image/'):
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
        return ImageSource(resp, format=format)
    
    def _check_resp(self, resp):
        if 'Content-type' not in resp.headers:
            raise SourceError('response from source WMS has no Content-type header')
        if not resp.headers['Content-type'].startswith('image/'):
            raise SourceError('no image returned from static LegendURL')
    
    @property
    def identifier(self):
        return (self.url, None)
        
        