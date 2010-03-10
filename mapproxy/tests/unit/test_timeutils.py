# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from datetime import datetime
from mapproxy.core.timeutils import parse_httpdate, format_httpdate, timestamp
from nose.tools import eq_, raises

class TestHTTPDate(object):
    def test_parse_httpdate(self):
        for date in (
            'Fri, 13 Feb 2009 23:31:30 GMT',
            'Friday, 13-Feb-09 23:31:30 GMT',
            'Fri Feb 13 23:31:30 2009',
            ):
            eq_(parse_httpdate(date), 1234567890)

    def test_parse_invalid(self):
        for date in (
            None,
            'foobar',
            '4823764923',
            'Fri, 13 Foo 2009 23:31:30 GMT'
            ):
            eq_(parse_httpdate(date), None)
    
    def test_format_httpdate(self):
        eq_(format_httpdate(datetime.fromtimestamp(1234567890)),
            'Fri, 13 Feb 2009 23:31:30 GMT')
        eq_(format_httpdate(1234567890),
            'Fri, 13 Feb 2009 23:31:30 GMT')
    
    @raises(AssertionError)
    def test_format_invalid(self):
        format_httpdate('foobar')

def test_timestamp():
    eq_(timestamp(1234567890), 1234567890)
    eq_(timestamp(datetime.fromtimestamp(1234567890)), 1234567890)
