# This file is part of the MapProxy project.
# Copyright (C) 2014 Omniscale <http://omniscale.de>
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

from mapproxy.service.wms import limit_srs_extents
from mapproxy.layer import DefaultMapExtent, MapExtent
from mapproxy.srs import SRS

from nose.tools import eq_

class TestLimitSRSExtents(object):
    def test_defaults(self):
        eq_(
            limit_srs_extents({}, ['EPSG:4326', 'EPSG:3857']),
            {
                'EPSG:4326': DefaultMapExtent(),
                'EPSG:3857': DefaultMapExtent(),
            }
        )
    def test_unsupported(self):
        eq_(
            limit_srs_extents({'EPSG:9999': DefaultMapExtent()},
                ['EPSG:4326', 'EPSG:3857']),
            {}
        )
    def test_limited_unsupported(self):
        eq_(
            limit_srs_extents({'EPSG:9999': DefaultMapExtent(), 'EPSG:4326': MapExtent([0, 0, 10, 10], SRS(4326))},
                ['EPSG:4326', 'EPSG:3857']),
            {'EPSG:4326': MapExtent([0, 0, 10, 10], SRS(4326)),}
        )
