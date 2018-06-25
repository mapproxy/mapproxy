# This file is part of the MapProxy project.
# Copyright (C) 2010, 2011 Omniscale <http://omniscale.de>
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
from mapproxy.util.times import timestamp_from_isodate

import pytest


def test_timestamp_from_isodate():
    ts = timestamp_from_isodate("2009-06-09T10:57:00")
    assert (1244537820.0 - 14 * 3600) < ts < (1244537820.0 + 14 * 3600)

    with pytest.raises(ValueError):
        timestamp_from_isodate("2009-06-09T10:57")
