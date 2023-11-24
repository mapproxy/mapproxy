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

###Disclamer: 
##This code is based on isodate from: https://github.com/gweis/isodate by  2009, Gerhard Weis 
##Some functions were extracted and modified from original project. 

from decimal import Decimal, ROUND_FLOOR
from datetime import timedelta, tzinfo as tz, date, time, datetime
import re

TIME_REGEX_CACHE = []
# used to cache regular expressions to parse ISO time strings.
DATE_REGEX_CACHE = {}
# A dictionary to cache pre-compiled regular expressions.
# A set of regular expressions is identified, by number of year digits allowed
# and whether a plus/minus sign is required or not. (This option is changeable
# only for 4 digit years).
TZ_REGEX = r"(?P<tzname>(Z|(?P<tzsign>[+-])"\
           r"(?P<tzhour>[0-9]{2})(:?(?P<tzmin>[0-9]{2}))?)?)"

TZ_EXT = '%Z'
ZERO = timedelta(0)

def build_date_regexps(yeardigits=4, expanded=False):
    '''
    Compile set of regular expressions to parse ISO dates. The expressions will
    be created only if they are not already in REGEX_CACHE.
    It is necessary to fix the number of year digits, else it is not possible
    to automatically distinguish between various ISO date formats.
    ISO 8601 allows more than 4 digit years, on prior agreement, but then a +/-
    sign is required (expanded format). To support +/- sign for 4 digit years,
    the expanded parameter needs to be set to True.
    '''
    if yeardigits != 4:
        expanded = True
    if (yeardigits, expanded) not in DATE_REGEX_CACHE:
        cache_entry = []
        # ISO 8601 expanded DATE formats allow an arbitrary number of year
        # digits with a leading +/- sign.
        if expanded:
            sign = 1
        else:
            sign = 0
        # 1. complete dates:
        #    YYYY-MM-DD or +- YYYYYY-MM-DD... extended date format
        cache_entry.append(re.compile(r"(?P<sign>[+-]){%d}(?P<year>[0-9]{%d})"
                                      r"-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})"
                                      % (sign, yeardigits)))
        #    YYYYMMDD or +- YYYYYYMMDD... basic date format
        cache_entry.append(re.compile(r"(?P<sign>[+-]){%d}(?P<year>[0-9]{%d})"
                                      r"(?P<month>[0-9]{2})(?P<day>[0-9]{2})"
                                      % (sign, yeardigits)))
        # 2. complete week dates:
        #    YYYY-Www-D or +-YYYYYY-Www-D ... extended week date
        cache_entry.append(re.compile(r"(?P<sign>[+-]){%d}(?P<year>[0-9]{%d})"
                                      r"-W(?P<week>[0-9]{2})-(?P<day>[0-9]{1})"
                                      % (sign, yeardigits)))
        #    YYYYWwwD or +-YYYYYYWwwD ... basic week date
        cache_entry.append(re.compile(r"(?P<sign>[+-]){%d}(?P<year>[0-9]{%d})W"
                                      r"(?P<week>[0-9]{2})(?P<day>[0-9]{1})"
                                      % (sign, yeardigits)))
        # 3. ordinal dates:
        #    YYYY-DDD or +-YYYYYY-DDD ... extended format
        cache_entry.append(re.compile(r"(?P<sign>[+-]){%d}(?P<year>[0-9]{%d})"
                                      r"-(?P<day>[0-9]{3})"
                                      % (sign, yeardigits)))
        #    YYYYDDD or +-YYYYYYDDD ... basic format
        cache_entry.append(re.compile(r"(?P<sign>[+-]){%d}(?P<year>[0-9]{%d})"
                                      r"(?P<day>[0-9]{3})"
                                      % (sign, yeardigits)))
        # 4. week dates:
        #    YYYY-Www or +-YYYYYY-Www ... extended reduced accuracy week date
        cache_entry.append(re.compile(r"(?P<sign>[+-]){%d}(?P<year>[0-9]{%d})"
                                      r"-W(?P<week>[0-9]{2})"
                                      % (sign, yeardigits)))
        #    YYYYWww or +-YYYYYYWww ... basic reduced accuracy week date
        cache_entry.append(re.compile(r"(?P<sign>[+-]){%d}(?P<year>[0-9]{%d})W"
                                      r"(?P<week>[0-9]{2})"
                                      % (sign, yeardigits)))
        # 5. month dates:
        #    YYY-MM or +-YYYYYY-MM ... reduced accuracy specific month
        cache_entry.append(re.compile(r"(?P<sign>[+-]){%d}(?P<year>[0-9]{%d})"
                                      r"-(?P<month>[0-9]{2})"
                                      % (sign, yeardigits)))
        #    YYYMM or +-YYYYYYMM ... basic incomplete month date format
        cache_entry.append(re.compile(r"(?P<sign>[+-]){%d}(?P<year>[0-9]{%d})"
                                      r"(?P<month>[0-9]{2})"
                                      % (sign, yeardigits)))
        # 6. year dates:
        #    YYYY or +-YYYYYY ... reduced accuracy specific year
        cache_entry.append(re.compile(r"(?P<sign>[+-]){%d}(?P<year>[0-9]{%d})"
                                      % (sign, yeardigits)))
        # 7. century dates:
        #    YY or +-YYYY ... reduced accuracy specific century
        cache_entry.append(re.compile(r"(?P<sign>[+-]){%d}"
                                      r"(?P<century>[0-9]{%d})"
                                      % (sign, yeardigits - 2)))

        DATE_REGEX_CACHE[(yeardigits, expanded)] = cache_entry
    return DATE_REGEX_CACHE[(yeardigits, expanded)]

def build_time_regexps():
    '''
    Build regular expressions to parse ISO time string.
    The regular expressions are compiled and stored in TIME_REGEX_CACHE
    for later reuse.
    '''
    if not TIME_REGEX_CACHE:
        # ISO 8601 time representations allow decimal fractions on least
        #    significant time component. Command and Full Stop are both valid
        #    fraction separators.
        #    The letter 'T' is allowed as time designator in front of a time
        #    expression.
        #    Immediately after a time expression, a time zone definition is
        #      allowed.
        #    a TZ may be missing (local time), be a 'Z' for UTC or a string of
        #    +-hh:mm where the ':mm' part can be skipped.
        # TZ information patterns:
        #    ''
        #    Z
        #    +-hh:mm
        #    +-hhmm
        #    +-hh =>
        #    isotzinfo.TZ_REGEX
        # 1. complete time:
        #    hh:mm:ss.ss ... extended format
        TIME_REGEX_CACHE.append(re.compile(r"T?(?P<hour>[0-9]{2}):"
                                           r"(?P<minute>[0-9]{2}):"
                                           r"(?P<second>[0-9]{2}"
                                           r"([,.][0-9]+)?)" + TZ_REGEX))
        #    hhmmss.ss ... basic format
        TIME_REGEX_CACHE.append(re.compile(r"T?(?P<hour>[0-9]{2})"
                                           r"(?P<minute>[0-9]{2})"
                                           r"(?P<second>[0-9]{2}"
                                           r"([,.][0-9]+)?)" + TZ_REGEX))
        # 2. reduced accuracy:
        #    hh:mm.mm ... extended format
        TIME_REGEX_CACHE.append(re.compile(r"T?(?P<hour>[0-9]{2}):"
                                           r"(?P<minute>[0-9]{2}"
                                           r"([,.][0-9]+)?)" + TZ_REGEX))
        #    hhmm.mm ... basic format
        TIME_REGEX_CACHE.append(re.compile(r"T?(?P<hour>[0-9]{2})"
                                           r"(?P<minute>[0-9]{2}"
                                           r"([,.][0-9]+)?)" + TZ_REGEX))
        #    hh.hh ... basic format
        TIME_REGEX_CACHE.append(re.compile(r"T?(?P<hour>[0-9]{2}"
                                           r"([,.][0-9]+)?)" + TZ_REGEX))
    return TIME_REGEX_CACHE


class FixedOffset(tz):
    '''
    A class building tzinfo objects for fixed-offset time zones.
    Note that FixedOffset(0, 0, "UTC") or FixedOffset() is a different way to
    build a UTC tzinfo object.
    '''

    def __init__(self, offset_hours=0, offset_minutes=0, name="UTC"):
        '''
        Initialise an instance with time offset and name.
        The time offset should be positive for time zones east of UTC
        and negate for time zones west of UTC.
        '''
        self.__offset = timedelta(hours=offset_hours, minutes=offset_minutes)
        self.__name = name

    def utcoffset(self, dt):
        '''
        Return offset from UTC in minutes of UTC.
        '''
        return self.__offset

    def tzname(self, dt):
        '''
        Return the time zone name corresponding to the datetime object dt, as a
        string.
        '''
        return self.__name

    def dst(self, dt):
        '''
        Return the daylight saving time (DST) adjustment, in minutes east of
        UTC.
        '''
        return ZERO

    def __repr__(self):
        '''
        Return nicely formatted repr string.
        '''
        return "<FixedOffset %r>" % self.__name

class Utc(tz):
    '''UTC
    Universal time coordinated time zone.
    '''

    def utcoffset(self, dt):
        '''
        Return offset from UTC in minutes east of UTC, which is ZERO for UTC.
        '''
        return ZERO

    def tzname(self, dt):
        '''
        Return the time zone name corresponding to the datetime object dt,
        as a string.
        '''
        return "UTC"

    def dst(self, dt):
        '''
        Return the daylight saving time (DST) adjustment, in minutes east
        of UTC.
        '''
        return ZERO

    def __reduce__(self):
        '''
        When unpickling a Utc object, return the default instance below, UTC.
        '''
        return _Utc, ()


UTC = Utc()

def build_tzinfo(tzname, tzsign='+', tzhour=0, tzmin=0):
    '''
    create a tzinfo instance according to given parameters.
    tzname:
      'Z'       ... return UTC
      '' | None ... return None
      other     ... return FixedOffset
    '''
    if tzname is None or tzname == '':
        return None
    if tzname == 'Z':
        return UTC
    tzsign = ((tzsign == '-') and -1) or 1
    return FixedOffset(tzsign * tzhour, tzsign * tzmin, tzname)

def fquotmod(val, low, high):
    a, b = val - low, high - low
    div = (a / b).to_integral(ROUND_FLOOR)
    mod = a - div * b
    mod += low
    return int(div), mod

def max_days_in_month(year, month):
    '''
    Determines the number of days of a specific month in a specific year.
    '''
    if month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    if month in (4, 6, 9, 11):
        return 30
    if ((year % 400) == 0) or ((year % 100) != 0) and ((year % 4) == 0):
        return 29
    return 28

class Duration(object):
    '''
    http://www.w3.org/TR/xmlschema-2/#adding-durations-to-dateTimes
    '''

    def __init__(self, days=0, seconds=0, microseconds=0, milliseconds=0,
                 minutes=0, hours=0, weeks=0, months=0, years=0):
        '''
        Initialise this Duration instance with the given parameters.
        '''
        if not isinstance(months, Decimal):
            months = Decimal(str(months))
        if not isinstance(years, Decimal):
            years = Decimal(str(years))
        self.months = months
        self.years = years
        self.tdelta = timedelta(days, seconds, microseconds, milliseconds,
                                minutes, hours, weeks)

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __getattr__(self, name):
  
        return getattr(self.tdelta, name)

    def __str__(self):
       
        params = []
        if self.years:
            params.append('%d years' % self.years)
        if self.months:
            fmt = "%d months"
            if self.months <= 1:
                fmt = "%d month"
            params.append(fmt % self.months)
        params.append(str(self.tdelta))
        return ', '.join(params)

    def __repr__(self):
        
        return "%s.%s(%d, %d, %d, years=%d, months=%d)" % (
            self.__class__.__module__, self.__class__.__name__,
            self.tdelta.days, self.tdelta.seconds,
            self.tdelta.microseconds, self.years, self.months)

    def __hash__(self):
        
        return hash((self.tdelta, self.months, self.years))

    def __neg__(self):
     
        negduration = Duration(years=-self.years, months=-self.months)
        negduration.tdelta = -self.tdelta
        return negduration

    def __add__(self, other):
  
        if isinstance(other, Duration):
            newduration = Duration(years=self.years + other.years,
                                   months=self.months + other.months)
            newduration.tdelta = self.tdelta + other.tdelta
            return newduration
        try:
    
            if (not(float(self.years).is_integer() and
                    float(self.months).is_integer())):
                raise ValueError('fractional years or months not supported'
                                 ' for date calculations')
            newmonth = other.month + self.months
            carry, newmonth = fquotmod(newmonth, 1, 13)
            newyear = other.year + self.years + carry
            maxdays = max_days_in_month(newyear, newmonth)
            if other.day > maxdays:
                newday = maxdays
            else:
                newday = other.day
            newdt = other.replace(year=newyear, month=newmonth, day=newday)
            
            return self.tdelta + newdt
        except AttributeError:
            
            pass
        try:
            
            newduration = Duration(years=self.years, months=self.months)
            newduration.tdelta = self.tdelta + other
            return newduration
        except AttributeError:
           
            pass
        
        return NotImplemented

    __radd__ = __add__

    def __mul__(self, other):
        if isinstance(other, int):
            newduration = Duration(
                years=self.years * other,
                months=self.months * other)
            newduration.tdelta = self.tdelta * other
            return newduration
        return NotImplemented

    __rmul__ = __mul__

    def __sub__(self, other):
     
        if isinstance(other, Duration):
            newduration = Duration(years=self.years - other.years,
                                   months=self.months - other.months)
            newduration.tdelta = self.tdelta - other.tdelta
            return newduration
        try:
            newduration = Duration(years=self.years, months=self.months)
            newduration.tdelta = self.tdelta - other
            return newduration
        except TypeError:
            pass
        return NotImplemented

    def __rsub__(self, other):
        if isinstance(other, timedelta):
            tmpdur = Duration()
            tmpdur.tdelta = other
            return tmpdur - self
        try:
            if (not(float(self.years).is_integer() and
                    float(self.months).is_integer())):
                raise ValueError('fractional years or months not supported'
                                 ' for date calculations')
            newmonth = other.month - self.months
            carry, newmonth = fquotmod(newmonth, 1, 13)
            newyear = other.year - self.years + carry
            maxdays = max_days_in_month(newyear, newmonth)
            if other.day > maxdays:
                newday = maxdays
            else:
                newday = other.day
            newdt = other.replace(year=newyear, month=newmonth, day=newday)
            return newdt - self.tdelta
        except AttributeError:
            pass
        return NotImplemented

    def __eq__(self, other):

        if isinstance(other, Duration):
            if (((self.years * 12 + self.months) ==
                 (other.years * 12 + other.months) and
                 self.tdelta == other.tdelta)):
                return True
            return False
        if self.years == 0 and self.months == 0:
            return self.tdelta == other
        return False

    def __ne__(self, other):

        if isinstance(other, Duration):
            if (((self.years * 12 + self.months) !=
                 (other.years * 12 + other.months) or
                 self.tdelta != other.tdelta)):
                return True
            return False
        if self.years == 0 and self.months == 0:
            return self.tdelta != other
        return True

    def totimedelta(self, start=None, end=None):
        if start is None and end is None:
            raise ValueError("start or end required")
        if start is not None and end is not None:
            raise ValueError("only start or end allowed")
        if start is not None:
            return (start + self) - start
        return end - (end - self)

class ISO8601Error(ValueError):
    '''Raised when the given ISO string can not be parsed.'''


def parse_datetime(datetimestring):
    '''
    Parses ISO 8601 date-times into datetime.datetime objects.
    This function uses parse_date and parse_time to do the job, so it allows
    more combinations of date and time representations, than the actual
    ISO 8601:2004 standard allows.
    '''
    try:
        datestring, timestring = datetimestring.split('T')
    except ValueError:
        raise ISO8601Error("ISO 8601 time designator 'T' missing. Unable to"
                           " parse datetime string %r" % datetimestring)
    tmpdate = parse_date(datestring)
    tmptime = parse_time(timestring)
    return datetime.combine(tmpdate, tmptime)

def parse_date(
        datestring,
        yeardigits=4, expanded=False, defaultmonth=1, defaultday=1):
    '''
    Parse an ISO 8601 date string into a datetime.date object.
    As the datetime.date implementation is limited to dates starting from
    0001-01-01, negative dates (BC) and year 0 can not be parsed by this
    method.
    For incomplete dates, this method chooses the first day for it. For
    instance if only a century is given, this method returns the 1st of
    January in year 1 of this century.
    supported formats: (expanded formats are shown with 6 digits for year)
      YYYYMMDD    +-YYYYYYMMDD      basic complete date
      YYYY-MM-DD  +-YYYYYY-MM-DD    extended complete date
      YYYYWwwD    +-YYYYYYWwwD      basic complete week date
      YYYY-Www-D  +-YYYYYY-Www-D    extended complete week date
      YYYYDDD     +-YYYYYYDDD       basic ordinal date
      YYYY-DDD    +-YYYYYY-DDD      extended ordinal date
      YYYYWww     +-YYYYYYWww       basic incomplete week date
      YYYY-Www    +-YYYYYY-Www      extended incomplete week date
      YYYMM       +-YYYYYYMM        basic incomplete month date
      YYY-MM      +-YYYYYY-MM       incomplete month date
      YYYY        +-YYYYYY          incomplete year date
      YY          +-YYYY            incomplete century date
    @param datestring: the ISO date string to parse
    @param yeardigits: how many digits are used to represent a year
    @param expanded: if True then +/- signs are allowed. This parameter
                     is forced to True, if yeardigits != 4
    @return: a datetime.date instance represented by datestring
    @raise ISO8601Error: if this function can not parse the datestring
    @raise ValueError: if datestring can not be represented by datetime.date
    '''
    if yeardigits != 4:
        expanded = True
    isodates = build_date_regexps(yeardigits, expanded)
    for pattern in isodates:
        match = pattern.match(datestring)
        if match:
            groups = match.groupdict()
            # sign, century, year, month, week, day,
            # FIXME: negative dates not possible with python standard types
            sign = (groups['sign'] == '-' and -1) or 1
            if 'century' in groups:
                return date(
                    sign * (int(groups['century']) * 100 + 1),
                    defaultmonth, defaultday)
            if 'month' not in groups:  # weekdate or ordinal date
                ret = date(sign * int(groups['year']), 1, 1)
                if 'week' in groups:
                    isotuple = ret.isocalendar()
                    if 'day' in groups:
                        days = int(groups['day'] or 1)
                    else:
                        days = 1
                    # if first week in year, do weeks-1
                    return ret + timedelta(weeks=int(groups['week']) -
                                           (((isotuple[1] == 1) and 1) or 0),
                                           days=-isotuple[2] + days)
                elif 'day' in groups:  # ordinal date
                    return ret + timedelta(days=int(groups['day']) - 1)
                else:  # year date
                    return ret.replace(month=defaultmonth, day=defaultday)
            # year-, month-, or complete date
            if 'day' not in groups or groups['day'] is None:
                day = defaultday
            else:
                day = int(groups['day'])
            return date(sign * int(groups['year']),
                        int(groups['month']) or defaultmonth, day)
    raise ISO8601Error('Unrecognised ISO 8601 date format: %r' % datestring)


def parse_time(timestring):
    '''
    Parses ISO 8601 times into datetime.time objects.
    Following ISO 8601 formats are supported:
      (as decimal separator a ',' or a '.' is allowed)
      hhmmss.ssTZD    basic complete time
      hh:mm:ss.ssTZD  extended compelte time
      hhmm.mmTZD      basic reduced accuracy time
      hh:mm.mmTZD     extended reduced accuracy time
      hh.hhTZD        basic reduced accuracy time
    TZD is the time zone designator which can be in the following format:
              no designator indicates local time zone
      Z       UTC
      +-hhmm  basic hours and minutes
      +-hh:mm extended hours and minutes
      +-hh    hours
    '''
    isotimes = build_time_regexps()
    for pattern in isotimes:
        match = pattern.match(timestring)
        if match:
            groups = match.groupdict()
            for key, value in groups.items():
                if value is not None:
                    groups[key] = value.replace(',', '.')
            Tzinfo = build_tzinfo(groups['tzname'], groups['tzsign'],
                                  int(groups['tzhour'] or 0),
                                  int(groups['tzmin'] or 0))
            if 'second' in groups:
                # round to microseconds if fractional seconds are more precise
                second = Decimal(groups['second']).quantize(Decimal('.000001'))
                microsecond = (second - int(second)) * int(1e6)
                # int(...) ... no rounding
                # to_integral() ... rounding
                return time(int(groups['hour']), int(groups['minute']),
                            int(second), int(microsecond.to_integral()),
                            Tzinfo)
            if 'minute' in groups:
                minute = Decimal(groups['minute'])
                second = (minute - int(minute)) * 60
                microsecond = (second - int(second)) * int(1e6)
                return time(int(groups['hour']), int(minute), int(second),
                            int(microsecond.to_integral()), Tzinfo)
            else:
                microsecond, second, minute = 0, 0, 0
            hour = Decimal(groups['hour'])
            minute = (hour - int(hour)) * 60
            second = (minute - int(minute)) * 60
            microsecond = (second - int(second)) * int(1e6)
            return time(int(hour), int(minute), int(second),
                        int(microsecond.to_integral()), Tzinfo)
    raise ISO8601Error('Unrecognised ISO 8601 time format: %r' % timestring)
