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
