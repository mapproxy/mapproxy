# This file is part of the MapProxy project.
# Copyright (C) 2010-213 Omniscale <http://omniscale.de>
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
from __future__ import absolute_import

"""
Date and time utilities.
"""
from time import mktime
import datetime
import calendar
from email.utils import parsedate
from wsgiref.handlers import format_date_time
from mapproxy import compat

def parse_httpdate(date):
    date = parsedate(date)
    if date is None:
        return None
    if date[0] < 1970:
        date = (date[0] + 2000,) +date[1:]
    return calendar.timegm(date)

def timestamp(date):
    if isinstance(date, datetime.datetime):
        date = mktime(date.timetuple())
    assert isinstance(date, compat.numeric_types)
    return date

def format_httpdate(date):
    date = timestamp(date)
    return format_date_time(date)


def timestamp_before(weeks=0, days=0, hours=0, minutes=0, seconds=0):
    """
    >>> import time as time_
    >>> time_.time() - timestamp_before(minutes=1) - 60 <= 1
    True
    >>> time_.time() - timestamp_before(days=1, minutes=2) - 86520 <= 1
    True
    >>> time_.time() - timestamp_before(hours=2) - 7200 <= 1
    True
    """
    delta = datetime.timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds)
    before = datetime.datetime.now() - delta
    return mktime(before.timetuple())

def timestamp_from_isodate(isodate):
    """
    >>> ts = timestamp_from_isodate('2009-06-09T10:57:00')
    >>> # we don't know which timezone the test will run
    >>> (1244537820.0 - 14 * 3600) < ts < (1244537820.0 + 14 * 3600)
    True
    >>> timestamp_from_isodate('2009-06-09T10:57') #doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    ValueError: ...
    """
    if isinstance(isodate, datetime.datetime):
        date = isodate
    else:
        date = datetime.datetime.strptime(isodate, "%Y-%m-%dT%H:%M:%S")
    return mktime(date.timetuple())