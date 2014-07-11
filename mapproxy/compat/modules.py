import sys
PY2 = sys.version_info[0] == 2

__all__ = ['urlparse']

if PY2:
    import urlparse; urlparse
else:
    from urllib import parse as urlparse