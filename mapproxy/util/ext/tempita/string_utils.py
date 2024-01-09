__all__ = ['b', 'basestring_', 'is_unicode', 'coerce_text']


def b(s):
    if isinstance(s, str):
        return s.encode('latin1')
    return bytes(s)


basestring_ = (bytes, str)


def is_unicode(obj):
    return isinstance(obj, str)


def coerce_text(v):
    if not isinstance(v, basestring_):
        attr = '__str__'
        if hasattr(v, attr):
            return str(v)
        else:
            return bytes(v)
    return v
