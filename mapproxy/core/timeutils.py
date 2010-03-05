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