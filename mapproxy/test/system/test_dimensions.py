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

    @pytest.mark.parametrize("test_input,expected_value", [ 

        # test_input should be string 
        #expected array ==> [year,month,day,hour,mins,secs,tz]

        ("2020-08-01T12:43:38Z", [2020, 8, 1, 12, 43, 38]),

        ("1999-12-30T01:59:03Z", [1999, 12, 30, 1, 59, 3]),

        ])
    def test_parsing_datetime(self,test_input,expected_value):
        
        #test = "2020-08-01T12:43:38Z"
        expected_year = expected_value[0]
        expected_month =  expected_value[1]
        expected_day =  expected_value[2]
        expected_hour =  expected_value[3]
        expected_mins = expected_value[4]
        expected_secs =  expected_value[5]
     

        result = parse_datetime(test_input)
        test_tz = result.tzinfo
        test_tz = test_tz.tzname(test_tz)

        assert result.year == expected_year
        assert result.month == expected_month
        assert result.hour == expected_hour
        assert result.minute == expected_mins
        assert result.second == expected_secs
        assert test_tz == "UTC"

    
    @pytest.mark.parametrize("test_input,only_time,expected_values", [ 

        # test_input should be string 
        #only_time flag to indicate only time parsing 
        #expected array ==> [year,month,day,secs]

        ("PT1H", True, [0,0,0,3600]),
        ("PT1H30M45S", True ,[0,0,0,5445]),
        ("P6MT", False ,[0,6,0,0]),
        ("P1MT", False ,[0,1,0,0]),
        ("P1Y2M1W3DT", False ,[1,2,10,0]),
        ])

    def test_parse_duration(self,test_input,only_time,expected_values):

        if only_time: 
            expect = expected_values[-1]
            result = parse_duration(test_input).seconds
            assert expect == result

        else:
            expected_years = expected_values[0]
            expected_months = expected_values[1]
            expected_days = expected_values[2]
            expected_seconds = expected_values[3]

            result = parse_duration(test_input)

            result_years = int(result.years)
            result_months = int(result.months)
            result_days = int(result.days)
            result_seconds = int(result.seconds)

            assert expected_years == result_years
            assert expected_months == result_months
            assert expected_days == result_days
            assert expected_seconds == result_seconds


    @pytest.mark.parametrize("test_input,exp_values", [ 

        # test_input should be string 
        #only_time flag to indicate only time parsing 
        #exp_values array ==> [time range values]
        ("2020-09-22T00:00:00Z/2020-09-23T00:00:00Z/PT12H",['2020-09-22T00:00:00Z', 
                            '2020-09-22T12:00:00Z', '2020-09-23T00:00:00Z']),
        ("2020-08-01T00:00:00Z/P1DT2H30M",['2020-08-01T00:00:00Z', 
                                                '2020-08-02T02:30:00Z']),
        ("P1DT2H30M/2020-08-30T00:00:00Z",['2020-08-28T21:30:00Z',
                                             '2020-08-30T00:00:00Z'])
        ])
  
    def test_parse_datetime_range(self,test_input,exp_values):
               
        exp_values = set(exp_values)
        result  = set(parse_datetime_range(test_input))

        assert exp_values == result

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


         