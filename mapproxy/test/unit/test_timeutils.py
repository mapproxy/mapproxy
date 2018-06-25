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

from datetime import datetime
from mapproxy.util.times import parse_httpdate, format_httpdate, timestamp

import pytest


class TestHTTPDate(object):

    def test_parse_httpdate(self):
        for date in (
            "Fri, 13 Feb 2009 23:31:30 GMT",
            "Friday, 13-Feb-09 23:31:30 GMT",
            "Fri Feb 13 23:31:30 2009",
        ):
            assert parse_httpdate(date) == 1234567890

    def test_parse_invalid(self):
        for date in (None, "foobar", "4823764923", "Fri, 13 Foo 2009 23:31:30 GMT"):
            assert parse_httpdate(date) == None

    def test_format_httpdate(self):
        assert (
            format_httpdate(datetime.fromtimestamp(1234567890))
            == "Fri, 13 Feb 2009 23:31:30 GMT"
        )
        assert format_httpdate(1234567890) == "Fri, 13 Feb 2009 23:31:30 GMT"

    def test_format_invalid(self):
        with pytest.raises(AssertionError):
            format_httpdate("foobar")


def test_timestamp():
    assert timestamp(1234567890) == 1234567890
    assert timestamp(datetime.fromtimestamp(1234567890)) == 1234567890
