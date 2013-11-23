import sys
PY2 = sys.version_info[0] == 2
PY3 = not PY2

if PY2:
    numeric_types = (float, int, long)
    string_type = basestring
    text_type = unicode
    # unichr = chr
else:
    numeric_types = (float, int)
    string_type = str
    text_type = str
    # unichr = unichr

if PY2:
    def iteritems(d):
        return d.iteritems()

else:
    def iteritems(d):
        return d.items()
