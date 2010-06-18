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

"""
Date and time utilities.
"""

import time
import datetime
import calendar
from email.utils import parsedate
from wsgiref.handlers import format_date_time

def parse_httpdate(date):
    date = parsedate(date)
    if date is None:
        return None
    if date[0] < 1970:
        date = (date[0] + 2000,) +date[1:]
    return calendar.timegm(date)

def timestamp(date):
    if isinstance(date, datetime.datetime):
        date = time.mktime(date.timetuple())
    assert isinstance(date, (float, int, long))
    return date

def format_httpdate(date):
    date = timestamp(date)
    return format_date_time(date)