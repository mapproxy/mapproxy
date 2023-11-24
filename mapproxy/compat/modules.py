import sys
PY2 = sys.version_info[0] == 2

__all__ = ['urlparse']

if PY2:
    import urlparse; urlparse
    from cgi import parse_qsl, escape
    from urllib import quote
else:
    from html import escape
    from urllib import parse as urlparse
    from urllib.parse import parse_qsl, quote
