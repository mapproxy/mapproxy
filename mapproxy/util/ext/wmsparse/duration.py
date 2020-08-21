from datetime import timedelta
from decimal import Decimal, ROUND_FLOOR

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