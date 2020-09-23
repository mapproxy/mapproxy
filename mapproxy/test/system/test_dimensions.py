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
from mapproxy.test.system import SysTest
from mapproxy.util.ext.wmsparse.util import parse_datetime_range,parse_duration
from mapproxy.util.ext.wmsparse.duration import parse_datetime

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

class TestDimensions(SysTest):

    def setup(self):
        self.common_req = WMS130MapRequest(
            url="/service?", param=dict(service="WMS", version="1.3.0")
        )

        self.common_req2 = WMS111MapRequest(
            url="/service?", param=dict(service="WMS", version="1.1.1")
        )

        self.common_req3 = WMS110MapRequest(
            url="/service?", param=dict(service="WMS", version="1.1.0")
        )

        self.common_req4 = WMS100MapRequest(
            url="/service?", param=dict(service="WMS", version="1.0.0")
        )


    def test_parsing_datetime(self):
        
        test = "2020-08-01T12:43:38Z"
        
        expected_year = 2020
        expected_month = 8
        expected_day = 1 
        expected_hour = 12
        expected_mins = 43
        expected_secs = 38

        result = parse_datetime(test)
        test_tz = result.tzinfo
        test_tz = test_tz.tzname(test_tz)

        assert result.year == expected_year
        assert result.month == expected_month
        assert result.hour == expected_hour
        assert result.minute == expected_mins
        assert result.second == expected_secs
        assert test_tz == "UTC"


    def test_parse_duration(self):

        test1 = "PT1H"
        expected_1 = 3600 #seconds is 1 hour
        result_1 = parse_duration(test1).seconds

        assert expected_1 == result_1

        test2 = "PT1H30M45S"
        expected_2 = 5445 #seconds 
        result_2 = parse_duration(test2).seconds

        assert expected_2 == result_2

        test3 = "P1MT"
        expected_3 = 1 # months
        result_3 = int(parse_duration(test3).months)

        assert expected_3 == result_3

        test3 = "P1MT"
        expected_3 = 1 # months
        result_3 = int(parse_duration(test3).months)


        test4 = "P1Y2M1W3DT"

        expected_years = 1
        expected_months = 2
        expected_days = 10 # 1 week means 7 days + 3 days
        result_4 = parse_duration(test4)

        result_years = int(result_4.years)
        result_months = int(result_4.months)
        result_days = int(result_4.days)

        assert expected_years == result_years
        assert expected_months == result_months
        assert expected_days == result_days


    def test_parse_datetime_range(self):
        
        test1 = "2020-09-22T00:00:00Z/2020-09-23T00:00:00Z/PT12H"
        
        expected_1 = set(['2020-09-22T00:00:00Z', 
                            '2020-09-22T12:00:00Z', '2020-09-23T00:00:00Z'])
        result_1  = set(parse_datetime_range(test1))

        assert expected_1 == result_1 

        test2 = "2020-08-01T00:00:00Z/P1DT2H30M"
        expected_2 = set(['2020-08-01T00:00:00Z', 
                                '2020-08-02T02:30:00Z'])
        
        result_2  = set(parse_datetime_range(test2))
        
        assert expected_2 == result_2


        test3 = "P1DT2H30M/2020-08-30T00:00:00Z"
        expected_3 = set(['2020-08-28T21:30:00Z',
                                     '2020-08-30T00:00:00Z'])
        result_3  = set(parse_datetime_range(test3))

        assert expected_3 == result_3

    def test_WMS130_dimension(self,app):
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

    def test_WMS111_dimension(self,app):
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

    def test_WMS110_dimension(self,app):
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

    def test_WMS100_dimension(self,app):
        req = WMS100CapabilitiesRequest(url="/service?").copy_with_request_params(
            self.common_req4
        )
        resp = app.get("/service?request=GetCapabilities&version=1.0.0&service=WMS",)       
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


         