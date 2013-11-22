import sys
PY2 = sys.version_info[0] == 2
PY3 = not PY2

if PY2:
    numeric_types = (float, int, long)
    # text_type = str
    # string_types = (str,)
    # unichr = chr
else:
    numeric_types = (float, int)
    # text_type = unicode
    # string_types = (str, unicode)
    # unichr = unichr