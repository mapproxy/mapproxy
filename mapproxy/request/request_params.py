from urllib.parse import quote

from mapproxy.request.no_case_multi_dict import NoCaseMultiDict


class RequestParams(object):
    """
    This class represents key-value request parameters. It allows case-insensitive
    access to all keys. Multiple values for a single key will be concatenated
    (eg. to ``layers=foo&layers=bar`` becomes ``layers: foo,bar``).

    All values can be accessed as a property.

    :param param: A dict or ``NoCaseMultiDict``.
    """
    params = None

    def __init__(self, param=None):
        self.delimiter = ','

        if param is None:
            self.params = NoCaseMultiDict()
        else:
            self.params = NoCaseMultiDict(param)

    def __str__(self):
        return self.query_string

    def get(self, key, default=None, type_func=None):
        """
        Returns the value for `key` or the `default`. `type_func` is called on the
        value to alter the value (e.g. use ``type_func=int`` to get ints).
        """
        return self.params.get(key, default, type_func)

    def set(self, key, value, append=False, unpack=False):
        """
        Set a `value` for the `key`. If `append` is ``True`` the value will be added
        to other values for this `key`.

        If `unpack` is True, `value` will be unpacked and each item will be added.
        """
        self.params.set(key, value, append=append, unpack=unpack)

    def update(self, mapping=(), append=False):
        """
        Update internal request parameters from an iterable of ``(key, value)``
        tuples or a dict.

        If `append` is ``True`` the value will be added to other values for
        this `key`.
        """
        self.params.update(mapping, append=append)

    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            raise AttributeError("'%s' object has no attribute '%s" %
                                 (self.__class__.__name__, name))

    def __getitem__(self, key):
        return self.delimiter.join(map(str, self.params.get_all(key)))

    def __setitem__(self, key, value):
        """
        Set `value` for the `key`. Does not append values (see ``MapRequest.set``).
        """
        self.set(key, value)

    def __delitem__(self, key):
        if key in self:
            del self.params[key]

    def iteritems(self):
        for key, values in self.params.iteritems():
            yield key, self.delimiter.join((str(x) for x in values))

    def __contains__(self, key):
        return self.params and key in self.params

    def copy(self):
        return self.__class__(self.params)

    @property
    def query_string(self):
        """
        The map request as a query string (the order is not guaranteed).

        >>> qs = RequestParams(dict(foo='egg', bar='ham%eggs', baz=100)).query_string
        >>> sorted(qs.split('&'))
        ['bar=ham%25eggs', 'baz=100', 'foo=egg']
        """
        kv_pairs = []
        for key, values in self.params.iteritems():
            value = ','.join(str(v) for v in values)
            kv_pairs.append(key + '=' + quote(value.encode('utf-8'), safe=','))
        return '&'.join(kv_pairs)

    def with_defaults(self, defaults):
        """
        Return this MapRequest with all values from `defaults` overwritten.
        """
        new = self.copy()
        for key, value in defaults.params.iteritems():
            if value != [None]:
                new.set(key, value, unpack=True)
        return new
