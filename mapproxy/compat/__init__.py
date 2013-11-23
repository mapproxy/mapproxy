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

    def iterkeys(d):
        return d.iterkeys()

    def itervalues(d):
        return d.itervalues()


else:
    def iteritems(d):
        return d.items()

    def iterkeys(d):
        return iter(d.keys())

    def itervalues(d):
        return d.values()
