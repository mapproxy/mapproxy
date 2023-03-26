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

import re
import datetime
from mapproxy.compat import string_type
from mapproxy.util.ext.wmsparse.duration import parse_datetime,Duration,ISO8601Error
from decimal import Decimal
import calendar

ISO8601_INTERVAL_REGEX = re.compile(
    r"^(?P<sign>[+-])?"
    r"P(?!\b)"
    r"(?P<years>[0-9]+([,.][0-9]+)?Y)?"
    r"(?P<months>[0-9]+([,.][0-9]+)?M)?"
    r"(?P<weeks>[0-9]+([,.][0-9]+)?W)?"
    r"(?P<days>[0-9]+([,.][0-9]+)?D)?"
    r"((?P<separator>T)(?P<hours>[0-9]+([,.][0-9]+)?H)?"
    r"(?P<minutes>[0-9]+([,.][0-9]+)?M)?"
    r"(?P<seconds>[0-9]+([,.][0-9]+)?S)?)?$")


xpath_elem = re.compile(r'(^|/)([^/]+:)?([^/]+)')


def parse_duration(datestring):
    """
    Parses an ISO 8601 durations into datetime.timedelta or Duration objects.
    If the ISO date string does not contain years or months, a timedelta
    instance is returned, else a Duration instance is returned.
    The following duration formats are supported:
      -PnnW                  duration in weeks
      -PnnYnnMnnDTnnHnnMnnS  complete duration specification
      -PYYYYMMDDThhmmss      basic alternative complete date format
      -PYYYY-MM-DDThh:mm:ss  extended alternative complete date format
      -PYYYYDDDThhmmss       basic alternative ordinal date format
      -PYYYY-DDDThh:mm:ss    extended alternative ordinal date format

    """
    if not isinstance(datestring, string_type):
        raise TypeError("Expecting a string %r" % datestring)
    match = ISO8601_INTERVAL_REGEX.match(datestring)
    if not match:
        # try alternative format:
        if datestring.startswith("P"):
            durdt = parse_datetime(datestring[1:])
            if durdt.year != 0 or durdt.month != 0:
                ret = Duration(days=durdt.day, seconds=durdt.second,
                               microseconds=durdt.microsecond,
                               minutes=durdt.minute, hours=durdt.hour,
                               months=durdt.month, years=durdt.year)
            else:  
                ret = datetime.timedelta(days=durdt.day, seconds=durdt.second,
                                microseconds=durdt.microsecond,
                                minutes=durdt.minute, hours=durdt.hour)
            return ret
        raise ISO8601Error("Unable to parse duration string %r" % datestring)
    groups = match.groupdict()
    for key, val in groups.items():
        if key not in ('separator', 'sign'):
            if val is None:
                groups[key] = "0n"
            if key in ('years', 'months'):
                groups[key] = Decimal(groups[key][:-1].replace(',', '.'))
            else:
                groups[key] = float(groups[key][:-1].replace(',', '.'))
    if groups["years"] == 0 and groups["months"] == 0:
        ret = datetime.timedelta(days=groups["days"], hours=groups["hours"],
                        minutes=groups["minutes"], seconds=groups["seconds"],
                        weeks=groups["weeks"])
        if groups["sign"] == '-':
            ret = datetime.timedelta(0) - ret
    else:
        ret = Duration(years=groups["years"], months=groups["months"],
                       days=groups["days"], hours=groups["hours"],
                       minutes=groups["minutes"], seconds=groups["seconds"],
                       weeks=groups["weeks"])
        if groups["sign"] == '-':
            ret = Duration(0) - ret
    return ret

def resolve_ns(xpath, namespaces, default=None):
    """
    Resolve namespaces in xpath to absolute URL as required by etree.
    """
    def repl(match):
        ns = match.group(2)
        if ns:
            abs_ns = namespaces.get(ns[:-1], default)
        else:
            abs_ns = default

        if not abs_ns:
            return '%s%s' % (match.group(1), match.group(3))
        else:
            return '%s{%s}%s' % (match.group(1), abs_ns, match.group(3))

    return xpath_elem.sub(repl, xpath)

def parse_datetime_range(datetime_range_str):
    """
    Only works for Z and PT??H for now.
    For example:
         2020-03-25T12:00:00Z/2020-03-27T00:00:00Z/PT12H30M

    A time interval is the intervening time between two time points. The amount of intervening time is expressed by a duration (as described in the previous section). The two time points (start and end) are expressed by either a combined date and time representation or just a date representation.

    There are four ways to express a time interval:
        1. Start and end, such as "2007-03-01T13:00:00Z/2008-05-11T15:30:00Z"
        2. Start and duration, such as "2007-03-01T13:00:00Z/P1Y2M10DT2H30M"
        3. Duration and end, such as "P1Y2M10DT2H30M/2008-05-11T15:30:00Z"
        4. Duration only, such as "P1Y2M10DT2H30M", with additional context information

        sources: https://www.iso.org/standard/40874.html 
                 https://en.wikipedia.org/wiki/ISO_8601

        P is the duration designator (for period) placed at the start of the duration representation.
            Y is the year designator that follows the value for the number of years.
            M is the month designator that follows the value for the number of months.
            W is the week designator that follows the value for the number of weeks.
            D is the day designator that follows the value for the number of days.
        T is the time designator that precedes the time components of the representation.
            H is the hour designator that follows the value for the number of hours.
            M is the minute designator that follows the value for the number of minutes.
            S is the second designator that follows the value for the number of seconds.

    """
    #initial values
    init_str = None
    end_str = None

    datetime_range_str = datetime_range_str.strip() #delete blank spaces
    splitting = datetime_range_str.split('/')

    values = [] #store final values

    if len(splitting) == 1:
        # sample: "2020-08-25T00:00:00Z"
        datetime_val = parse_datetime(splitting[0])
        values.append(datetime_val.isoformat().replace('+00:00', 'Z'))
        return values

    if len(splitting) == 2 and splitting[1].startswith("P"): 
        # sample: "2007-03-01T13:00:00Z/P1Y2M10DT2H30M"
        init_str, interval =  splitting

    if len(splitting) == 2 and splitting[0].startswith("P"): 
        # sample: ""P1Y2M10DT2H30M/2008-05-11T15:30:00Z""
        interval, end_str =  splitting

    if len(splitting) == 3 and splitting[2].startswith("P"): 
        # sample: "2020-08-25T00:00:00Z/2020-08-26T00:00:00Z/PT2H30M"
        init_str, end_str, interval =  splitting

    #period, time = interval.split('T')
    delta = parse_duration(interval)

    # missing end 
    if end_str is None:
        init = parse_datetime(init_str)
        end = init + delta

    #missing init
    if init_str is None:
        end = parse_datetime(end_str)
        init = end - delta

    if init_str and end_str: 
        init = parse_datetime(init_str)
        end = parse_datetime(end_str)

    current = init
    while current < (end + delta):
        values.append(current.isoformat().replace('+00:00', 'Z'))
        current = current + delta

    return values
