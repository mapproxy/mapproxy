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

from mapproxy.client.http import HTTPClient
from mapproxy.client.wms import WMSInfoClient
from mapproxy.srs import SRS
from mapproxy.featureinfo import create_featureinfo_doc

class ArcGISClient(object):
    def __init__(self, request_template, http_client=None):
        self.request_template = request_template
        self.http_client = http_client

    def retrieve(self, query, format):
        url  = self._query_url(query, format)
        resp = self.http_client.open(url)
        return resp

    def _query_url(self, query, format):
        req = self.request_template.copy()
        req.params.format = format
        req.params.bbox = query.bbox
        req.params.size = query.size
        req.params.bboxSR = query.srs
        req.params.imageSR = query.srs
        req.params.transparent = query.transparent

        return req.complete_url

    def combined_client(self, other, query):
        return

class ArcGISInfoClient(WMSInfoClient):
    def __init__(self, request_template, supported_srs=None, http_client=None,
            return_geometries=False,
            tolerance=5,
        ):
        self.request_template = request_template
        self.http_client = http_client or HTTPClient()
        if not supported_srs and self.request_template.params.srs is not None:
            supported_srs = [SRS(self.request_template.params.srs)]
        self.supported_srs = supported_srs or []
        self.return_geometries = return_geometries
        self.tolerance = tolerance

    def get_info(self, query):
        if self.supported_srs and query.srs not in self.supported_srs:
            query = self._get_transformed_query(query)
        resp = self._retrieve(query)
        # always use query.info_format and not content-type from response (even esri example server aleays return text/plain)
        return create_featureinfo_doc(resp.read(), query.info_format)

    def _query_url(self, query):
        req = self.request_template.copy()
        req.params.bbox = query.bbox
        req.params.size = query.size
        req.params.pos = query.pos
        req.params.srs = query.srs.srs_code
        if query.info_format.startswith('text/html'):
            req.params['f'] =  'html'
        else:
            req.params['f'] =  'json'

        req.params['tolerance'] = self.tolerance
        req.params['returnGeometry'] = str(self.return_geometries).lower()

        return req.complete_url
