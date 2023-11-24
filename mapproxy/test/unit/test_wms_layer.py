# This file is part of the MapProxy project.
# Copyright (C) 2013 Omniscale <http://omniscale.de>
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

from __future__ import division

from mapproxy.layer import MapQuery, InfoQuery
from mapproxy.srs import SRS
from mapproxy.service.wms import combined_layers
from mapproxy.source.wms import WMSSource
from mapproxy.client.wms import WMSClient
from mapproxy.request.wms import create_request


class TestCombinedLayers(object):
    q = MapQuery((0, 0, 10000, 10000), (100, 100), SRS(3857))

    def test_empty(self):
        assert combined_layers([], self.q) == []

    def test_same_source(self):
        layers = [
            WMSSource(
                WMSClient(create_request({"url": "http://foo/", "layers": "a"}, {}))
            ),
            WMSSource(
                WMSClient(create_request({"url": "http://foo/", "layers": "b"}, {}))
            ),
        ]
        combined = combined_layers(layers, self.q)
        assert len(combined) == 1
        assert combined[0].client.request_template.params.layers == ["a", "b"]

    def test_mixed_hosts(self):
        layers = [
            WMSSource(
                WMSClient(create_request({"url": "http://foo/", "layers": "a"}, {}))
            ),
            WMSSource(
                WMSClient(create_request({"url": "http://foo/", "layers": "b"}, {}))
            ),
            WMSSource(
                WMSClient(create_request({"url": "http://bar/", "layers": "c"}, {}))
            ),
            WMSSource(
                WMSClient(create_request({"url": "http://bar/", "layers": "d"}, {}))
            ),
            WMSSource(
                WMSClient(create_request({"url": "http://foo/", "layers": "e"}, {}))
            ),
            WMSSource(
                WMSClient(create_request({"url": "http://foo/", "layers": "f"}, {}))
            ),
        ]
        combined = combined_layers(layers, self.q)
        assert len(combined) == 3
        assert combined[0].client.request_template.params.layers == ["a", "b"]
        assert combined[1].client.request_template.params.layers == ["c", "d"]
        assert combined[2].client.request_template.params.layers == ["e", "f"]

    def test_mixed_params(self):
        layers = [
            WMSSource(
                WMSClient(create_request({"url": "http://foo/", "layers": "a"}, {}))
            ),
            WMSSource(
                WMSClient(create_request({"url": "http://foo/", "layers": "b"}, {}))
            ),
            WMSSource(
                WMSClient(create_request({"url": "http://foo/", "layers": "c"}, {}))
            ),
            WMSSource(
                WMSClient(create_request({"url": "http://foo/", "layers": "d"}, {}))
            ),
            WMSSource(
                WMSClient(create_request({"url": "http://foo/", "layers": "e"}, {}))
            ),
            WMSSource(
                WMSClient(create_request({"url": "http://foo/", "layers": "f"}, {}))
            ),
        ]

        layers[0].supported_srs = ["EPSG:4326"]
        layers[1].supported_srs = ["EPSG:4326"]

        layers[2].supported_formats = ["image/png"]
        layers[3].supported_formats = ["image/png"]

        combined = combined_layers(layers, self.q)
        assert len(combined) == 3
        assert combined[0].client.request_template.params.layers == ["a", "b"]
        assert combined[1].client.request_template.params.layers == ["c", "d"]
        assert combined[2].client.request_template.params.layers == ["e", "f"]


class TestInfoQuery(object):

    def test_coord(self):
        query = InfoQuery(
            (8, 50, 9, 51), (400, 1000), SRS(4326), (100, 600), "text/plain"
        )
        assert query.coord == (8.25, 50.4)
