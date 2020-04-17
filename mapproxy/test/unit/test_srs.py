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

import os

import pytest

from mapproxy.config import base_config
from mapproxy import srs, proj
from mapproxy.srs import SRS, PreferredSrcSRS, SupportedSRS


class TestSRS(object):

    def test_epsg4326(self):
        srs = SRS(4326)

        assert srs.is_latlong
        assert not srs.is_axis_order_en
        assert srs.is_axis_order_ne

    def test_crs84(self):
        srs = SRS("CRS:84")

        assert srs.is_latlong
        assert srs.is_axis_order_en
        assert not srs.is_axis_order_ne

        assert srs == SRS("EPSG:4326")

    def test_epsg31467(self):
        srs = SRS("EPSG:31467")

        assert not srs.is_latlong
        assert not srs.is_axis_order_en
        assert srs.is_axis_order_ne

    def test_epsg900913(self):
        srs = SRS("epsg:900913")

        assert not srs.is_latlong
        assert srs.is_axis_order_en
        assert not srs.is_axis_order_ne

    def test_from_srs(self):
        srs1 = SRS("epgs:4326")
        srs2 = SRS(srs1)
        assert srs1 == srs2

# proj_data_dir test relies on old Proj4 epsg files.
@pytest.mark.skipif(not proj.USE_PROJ4_API, reason="only for old proj4 lib")
class Test_0_ProjDefaultDataPath(object):

    def test_known_srs(self):
        srs.SRS(4326)

    def test_unknown_srs(self):
        with pytest.raises(RuntimeError):
            srs.SRS(1234)


@pytest.fixture(scope="class")
def custom_proj_data_dir():
    srs._proj_initalized = False
    srs._srs_cache = {}
    base_config().srs.proj_data_dir = os.path.dirname(__file__)

    yield

    srs._proj_initalized = False
    srs._srs_cache = {}
    srs.set_datapath(None)
    base_config().srs.proj_data_dir = None

@pytest.mark.skipif(not proj.USE_PROJ4_API, reason="only for old proj4 lib")
@pytest.mark.usefixtures("custom_proj_data_dir")
class Test_1_ProjDataPath(object):

    def test_dummy_srs(self):
        srs.SRS(1234)

    def test_unknown_srs(self):
        with pytest.raises(RuntimeError):
            srs.SRS(2339)

class TestPreferredSrcSRS(object):

    # test selection of preferred SRS
    # unprojected: 4326, 4258
    # projected: 3857, 25831, 25832, 31467
    @pytest.mark.parametrize("target,available,expected", [

        # always return target if available
        (4326, [25832, 4326, 3857], 4326),

        (4326, [25832, 4326, 3857], 4326),
        (4326, [25831, 3857], 3857),

        (3857, [25832, 4258, 3857, 31466], 3857),
        (3857, [25832, 4258, 31467, 25831, 31466], 25832),
        (3857, [4258, 31467, 25831, 31466], 25831),
        (3857, [4258, 31467, 31466], 31467),
        (3857, [4258, 31466], 31466),
        (3857, [4258], 4258),

        # always return first preferred, regardless of order in available
        (4326, [3857, 4258], 4258),
        (4326, [4258, 3857], 4258),

        # no preferred, return first that is also projected/unprojected
        (31467, [4326, 25831, 3857], 25831),
        (4258, [25831, 4326, 3857], 4326),

        # no preferred and no srs that is also projected/unprojected, return first
        (31467, [4326, 4258], 4326),
        (4258, [3857, 25832, 31467], 3857),
    ])
    def test_preferred(self, target, available, expected):
        preferredSRS = PreferredSrcSRS()
        preferredSRS.add(SRS(4326), [SRS(4258), SRS(3857)])
        preferredSRS.add(SRS(3857), [SRS(25832), SRS(25831), SRS(31467), SRS(4326)])

        assert preferredSRS.preferred_src(SRS(target), [SRS(c) for c in available]) == SRS(expected)

    def test_no_available(self):
        preferredSRS = PreferredSrcSRS()
        preferredSRS.add(SRS(4326), [SRS(4258), SRS(3857)])

        with pytest.raises(ValueError):
            preferredSRS.preferred_src(SRS(4326), [])


class TestSupportedSRS(object):
    @pytest.fixture
    def preferred(self):
        preferredSRS = PreferredSrcSRS()
        preferredSRS.add(SRS(4326), [SRS(4258), SRS(3857)])
        preferredSRS.add(SRS(3857), [SRS(25832), SRS(25831), SRS(31467), SRS(4326)])
        return preferredSRS

    def test_supported(self, preferred):
        supported = SupportedSRS([SRS(4326), SRS(25832)], preferred)
        assert SRS(4326) in supported
        assert SRS(4258) not in supported
        assert SRS(25832) in supported

    def test_iter(self, preferred):
        supported = SupportedSRS([SRS(4326), SRS(25832)], preferred)
        assert [SRS(4326), SRS(25832)] == [srs for srs in supported]

    def test_best_srs(self, preferred):
        supported = SupportedSRS([SRS(4326), SRS(25832)], preferred)
        assert supported.best_srs(SRS(4326)) == SRS(4326)
        assert supported.best_srs(SRS(4258)) == SRS(4326)
        assert supported.best_srs(SRS(25832)) == SRS(25832)
        assert supported.best_srs(SRS(25831)) == SRS(25832)
        assert supported.best_srs(SRS(3857)) == SRS(25832)
        supported = SupportedSRS([SRS(4326), SRS(31467), SRS(25831)], preferred)
        assert supported.best_srs(SRS(3857)) == SRS(25831)
        assert supported.best_srs(SRS(25831)) == SRS(25831)

    def test_best_srs_no_preferred(self, preferred):
        supported = SupportedSRS([SRS(4326), SRS(25832)], None)
        assert supported.best_srs(SRS(4326)) == SRS(4326)
        assert supported.best_srs(SRS(4258)) == SRS(4326)
        assert supported.best_srs(SRS(25832)) == SRS(25832)
        assert supported.best_srs(SRS(25831)) == SRS(25832)
        assert supported.best_srs(SRS(3857)) == SRS(25832)

