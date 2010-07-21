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

from __future__ import division, with_statement
from mapproxy.core.image import ImageSource, ImageTransformer
from mapproxy.core.client import retrieve_url, HTTPClientError
from mapproxy.core.srs import SRS, make_lin_transf
from mapproxy.core.utils import NullLock

class WMSClient(object):
    """
    Client for WMS requests.
    """
    def __init__(self, request_template=None, client_request=None, http_client=None,
        supported_srs=None, lock=None):
        """
        :param request_template: a request that will be used as a template for
            new requests
        :param client_request: function is called for each client request.
            gets the request_template and the according request. should return
            a new request object that is used for this request. 
        """
        if client_request is None:
            client_request = wms_client_request
        self.client_request = client_request
        self.request_template = request_template
        self.http_client = http_client
        self.supported_srs = supported_srs
        self.lock = lock or NullLock

    def get_map(self, request):
        if self.supported_srs and SRS(request.params.srs) not in self.supported_srs:
            return self._transformed_get_map(request)
        
        resp = self._retrieve_url(self._map_url(request))
        if not resp.headers['content-type'].startswith('image'):
            raise HTTPClientError('response is not an image: (%s)' % (resp.read()))
        return ImageSource(resp, request.params.format)
    
    def _transformed_get_map(self, request):
        dst_srs = SRS(request.params.srs)
        src_srs = self._best_supported_srs(dst_srs)
        dst_bbox = request.params.bbox
        src_bbox = dst_srs.transform_bbox_to(src_srs, dst_bbox)
        
        src_width, src_height = src_bbox[2]-src_bbox[0], src_bbox[3]-src_bbox[1]
        ratio = src_width/src_height

        dst_size = request.params.size
        
        xres, yres = src_width/dst_size[0], src_height/dst_size[1]
        if xres < yres:
            src_size = dst_size[0], int(dst_size[0]/ratio + 0.5)
        else:
            src_size = int(dst_size[1]*ratio +0.5), dst_size[1]
        
        request = request.copy()
        request.params['srs'] = src_srs.srs_code
        request.params.bbox = src_bbox
        request.params.size = src_size
        
        resp = self._retrieve_url(self._map_url(request))
        
        img = ImageSource(resp, request.params.format, size=src_size)
        img = ImageTransformer(src_srs, dst_srs).transform(img, src_bbox, 
            dst_size, dst_bbox)
        
        img.format = self.request_template.params.format
        return img
    
    def _best_supported_srs(self, srs):
        latlong = srs.is_latlong
        
        for srs in self.supported_srs:
            if srs.is_latlong == latlong:
                return srs
        
        return iter(self.supported_srs).next()
        
    def _map_url(self, request):
        req = self.client_request(self.request_template, request)
        return req.complete_url
    
    def get_info(self, request):
        resp = self._retrieve_url(self._info_url(request))
        return resp.read()
    
    def _retrieve_url(self, url):
        with self.lock():
            if self.http_client:
                return self.http_client.open(url)
            return retrieve_url(url)
    
    def _info_url(self, request):
        req = self.client_request(self.request_template, request)

        if self.request_template is None:
            return req.complete_url
        
        req.params['srs'] = request.params['srs'] #restore requested srs
        self._transform_fi_request(req)
        req.params['query_layers'] = req.params['layers']
        return req.complete_url
    
    def _transform_fi_request(self, request):
        params = request.params
        if self.request_template.params.srs == params.srs:
            return request
        
        pos = params.pos
        req_bbox = params.bbox
        req_pos = make_lin_transf((0, 0) + params.size, req_bbox)(pos)
        req_srs = SRS(params.srs)
        dst_srs = SRS(self.request_template.params.srs)
        dst_pos = req_srs.transform_to(dst_srs, req_pos)
        dst_bbox = req_srs.transform_bbox_to(dst_srs, req_bbox)
        dst_pos = make_lin_transf((dst_bbox), (0, 0) + params.size)(dst_pos)
        
        params['srs'] = self.request_template.params.srs
        params.bbox = dst_bbox
        params.pos = dst_pos
        

def wms_client_request(request_template, map_request):
    if request_template is None:
        return map_request.copy()
    req = request_template.copy_with_request_params(map_request)
    req.url = request_template.url
    req.params.bbox = map_request.params.bbox
    if map_request.params.srs:
        req.params.srs = map_request.params.srs
    return req
