# This file is part of the MapProxy project.
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
import functools
import os 
import pytest
from mapproxy.test.image import tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import SysTest

from mapproxy.request.wms import (
    WMS100MapRequest,
    WMS111MapRequest,
    WMS130MapRequest,
    WMS111CapabilitiesRequest,
    WMS130CapabilitiesRequest,
    WMS100CapabilitiesRequest,
    WMS110MapRequest,
    WMS110FeatureInfoRequest,
    WMS110CapabilitiesRequest,
)

expected_dim = {'time': {
                        'values': '2020-09-22T11:20:00Z,2020-09-22T13:20:00Z,2020-09-22T15:20:00Z', 
                        'default': '2020-09-22T14:20:00Z'}, 
                'dim_reference_time': {
                        'values': '2020-09-22T11:20:00Z,2020-09-22T13:20:00Z,2020-09-22T15:20:00Z', 
                        'default': '2020-09-22T14:20:00Z'}}

@pytest.fixture(scope="module")
def config_file():
    return "dimension.yaml"

class TestDimensionsWMS130(SysTest):

    def setup_method(self):
        self.common_req = WMS130MapRequest(
            url="/service?", param=dict(service="WMS", version="1.3.0")
        )
        self.common_map_req = WMS130MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.3.0",
                bbox="-180,0,0,80",
                width="200",
                height="200",
                layers="test_cache",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
                time="2020-09-22T14:20:00Z",
            ),
        )

    def test_get_capabilities_dimension(self,app):
        req = WMS130CapabilitiesRequest(url="/service?").copy_with_request_params(
            self.common_req
        )
        resp = app.get(req)
        xml = resp.lxml
    

        dimensions = xml.xpath('//xmlns:Layer/xmlns:Dimension', namespaces=dict(xmlns="http://www.opengis.net/wms"))
        results = dict()

        for dimension in dimensions:
            temp_dict = dict()
            temp_dict['values'] = dimension.text
            temp_dict['default'] = dimension.attrib['default']
            results[dimension.attrib['name']] = temp_dict
        
        assert set(list(expected_dim.keys()))  == set(list(results.keys()))
        
        assert expected_dim['time']['default'] == results['time']['default']
        assert expected_dim['dim_reference_time']['default'] == results['dim_reference_time']['default']
        assert expected_dim['time']['values'] == results['time']['values']
        assert expected_dim['dim_reference_time']['values'] == results['dim_reference_time']['values']

    def test_get_map_dimensions(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=0.0,0.0,20037508.3428,20037508.3428"
                    "&WIDTH=256&TIME=2020-09-22T14:20:00Z"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42422), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params["bbox"] = "0,0,180,90"
                resp = app.get(self.common_map_req)
                assert 35000 < int(resp.headers["Content-length"]) < 75000
                assert resp.content_type == "image/png"

        assert cache_dir.join(
            "test_cache_EPSG900913/time-2020-09-22T14:20:00Z/01/000/000/001/000/000/001.jpeg"
        ).check()

class TestDimensionsWMS111(SysTest):

    def setup_method(self):
        self.common_req = WMS111MapRequest(
            url="/service?", param=dict(service="WMS", version="1.1.1")
        )
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-180,0,0,80",
                width="200",
                height="200",
                layers="test_cache",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
                time="2020-09-22T14:20:00Z",
            ),
        )

    def test_get_capabilities_dimension(self,app):
        req = WMS111CapabilitiesRequest(url="/service?").copy_with_request_params(
            self.common_req
        )
        resp = app.get(req)       
        xml = resp.lxml
        dimensions = xml.xpath('//Layer/Dimension')
        results = dict()

        for dimension in dimensions:
            temp_dict = dict()
            temp_dict['values'] = dimension.text
            temp_dict['default'] = dimension.attrib['default']
            results[dimension.attrib['name']] = temp_dict
        
        assert set(list(expected_dim.keys()))  == set(list(results.keys()))
        
        assert expected_dim['time']['default'] == results['time']['default']
        assert expected_dim['dim_reference_time']['default'] == results['dim_reference_time']['default']

    def test_get_map_dimensions(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=0.0,0.0,20037508.3428,20037508.3428"
                    "&WIDTH=256&TIME=2020-09-22T14:20:00Z"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42422), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params["bbox"] = "0,0,180,90"
                resp = app.get(self.common_map_req)
                assert 35000 < int(resp.headers["Content-length"]) < 75000
                assert resp.content_type == "image/png"

        assert cache_dir.join(
            "test_cache_EPSG900913/time-2020-09-22T14:20:00Z/01/000/000/001/000/000/001.jpeg"
        ).check()

class TestDimensionsWMS110(SysTest):

    def setup_method(self):
        self.common_req = WMS110MapRequest(
            url="/service?", param=dict(service="WMS", version="1.1.0")
        )
        self.common_map_req = WMS110MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.0",
                bbox="-180,0,0,80",
                width="200",
                height="200",
                layers="test_cache",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
                time="2020-09-22T14:20:00Z",
            ),
        )

    def test_get_capabilities_dimension(self,app):
        req = WMS110CapabilitiesRequest(url="/service?").copy_with_request_params(
            self.common_req
        )
        resp = app.get(req)       
        xml = resp.lxml
        dimensions = xml.xpath('//Layer/Dimension')
        results = dict()

        for dimension in dimensions:
            temp_dict = dict()
            temp_dict['values'] = dimension.text
            temp_dict['default'] = dimension.attrib['default']
            results[dimension.attrib['name']] = temp_dict
        assert set(list(expected_dim.keys()))  == set(list(results.keys()))
        
        assert expected_dim['time']['default'] == results['time']['default']
        assert expected_dim['dim_reference_time']['default'] == results['dim_reference_time']['default']
        assert expected_dim['time']['values'] == results['time']['values']
        assert expected_dim['dim_reference_time']['values'] == results['dim_reference_time']['values']
        assert expected_dim['time']['values'] == results['time']['values']
        assert expected_dim['dim_reference_time']['values'] == results['dim_reference_time']['values']

    def test_get_map_dimensions(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=foo,bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=0.0,0.0,20037508.3428,20037508.3428"
                    "&WIDTH=256&TIME=2020-09-22T14:20:00Z"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42422), [expected_req], bbox_aware_query_comparator=True
            ):
                self.common_map_req.params["bbox"] = "0,0,180,90"
                resp = app.get(self.common_map_req)
                assert 35000 < int(resp.headers["Content-length"]) < 75000
                assert resp.content_type == "image/png"

        assert cache_dir.join(
            "test_cache_EPSG900913/time-2020-09-22T14:20:00Z/01/000/000/001/000/000/001.jpeg"
        ).check()

class TestDimensionsWMS100(SysTest):

    def setup_method(self):
        self.common_req = WMS100MapRequest(
            url="/service?", param=dict(service="WMS", wmtver="1.0.0")
        )

    def test_get_capabilities_dimension(self,app):
        req = WMS100CapabilitiesRequest(url="/service?").copy_with_request_params(
            self.common_req
        )
        resp = app.get(req)       
        xml = resp.lxml
        dimensions = xml.xpath('//Layer/Dimension')
        results = dict()

        for dimension in dimensions:
            temp_dict = dict()
            temp_dict['values'] = dimension.text
            temp_dict['default'] = dimension.attrib['default']
            results[dimension.attrib['name']] = temp_dict

        assert set(list(expected_dim.keys()))  == set(list(results.keys()))
        assert expected_dim['time']['default'] == results['time']['default']
        assert expected_dim['dim_reference_time']['default'] == results['dim_reference_time']['default']
        assert expected_dim['time']['values'] == results['time']['values']
        assert expected_dim['dim_reference_time']['values'] == results['dim_reference_time']['values']
        assert expected_dim['time']['values'] == results['time']['values']
        assert expected_dim['dim_reference_time']['values'] == results['dim_reference_time']['values']