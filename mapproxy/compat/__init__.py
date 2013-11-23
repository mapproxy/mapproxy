import sys
PY2 = sys.version_info[0] == 2
PY3 = not PY2

if PY2:
    numeric_types = (float, int, long)
    string_type = basestring
    # text_type = str
    # unichr = chr
else:
    numeric_types = (float, int)
    string_type = str
    # text_type = unicode
    # unichr = unichr