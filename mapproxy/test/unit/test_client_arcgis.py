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

from io import BytesIO

from mapproxy.client.arcgis import ArcGISInfoClient
from mapproxy.layer import InfoQuery
from mapproxy.request.arcgis import ArcGISIdentifyRequest
from mapproxy.srs import SRS, SupportedSRS
from mapproxy.test.http import assert_query_eq


TESTSERVER_ADDRESS = ('127.0.0.1', 56413)
TESTSERVER_URL = 'http://%s:%s' % TESTSERVER_ADDRESS


class MockHTTPClient(object):
    def __init__(self):
        self.requested = []

    def open(self, url, data=None):
        self.requested.append(url)
        result = BytesIO(b'{}')
        result.seek(0)
        result.headers = {}
        return result

class TestArcGISInfoClient(object):
    def test_fi_request(self):
        req = ArcGISIdentifyRequest(url=TESTSERVER_URL + '/MapServer/export?map=foo', param={'layers':'foo'})
        http = MockHTTPClient()
        wms = ArcGISInfoClient(req, http_client=http, supported_srs=SupportedSRS([SRS(4326)]))
        fi_req = InfoQuery((8, 50, 9, 51), (512, 512),
                           SRS(4326), (128, 64), 'text/plain')

        wms.get_info(fi_req)

        assert_query_eq(http.requested[0],
            TESTSERVER_URL+'/MapServer/identify?map=foo'
                           '&imageDisplay=512,512,96&sr=4326&f=json'
                           '&layers=foo&tolerance=5&returnGeometry=false'
                           '&geometryType=esriGeometryPoint&geometry=8.250000,50.875000'
                           '&mapExtent=8,50,9,51',
            fuzzy_number_compare=True)

    def test_transform_fi_request_supported_srs(self):
        req = ArcGISIdentifyRequest(url=TESTSERVER_URL + '/MapServer/export?map=foo', param={'layers':'foo'})
        http = MockHTTPClient()
        wms = ArcGISInfoClient(req, http_client=http, supported_srs=SupportedSRS([SRS(25832)]))
        fi_req = InfoQuery((8, 50, 9, 51), (512, 512),
                           SRS(4326), (128, 64), 'text/plain')

        wms.get_info(fi_req)

        assert_query_eq(http.requested[0],
            TESTSERVER_URL+'/MapServer/identify?map=foo'
                           '&imageDisplay=512,797,96&sr=25832&f=json'
                           '&layers=foo&tolerance=5&returnGeometry=false'
                           '&geometryType=esriGeometryPoint&geometry=447229.979084,5636149.370634'
                           '&mapExtent=428333.552496,5538630.70275,500000.0,5650300.78652',
            fuzzy_number_compare=True)
