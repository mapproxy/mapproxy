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