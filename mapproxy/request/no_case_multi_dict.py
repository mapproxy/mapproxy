class NoCaseMultiDict(dict):
    """
    This is a dictionary that allows case insensitive access to values.

    >>> d = NoCaseMultiDict([('A', 'b'), ('a', 'c'), ('B', 'f'), ('c', 'x'), ('c', 'y'), ('c', 'z')])
    >>> d['a']
    'b'
    >>> d.get_all('a')
    ['b', 'c']
    >>> 'a' in d and 'b' in d
    True
    """

    def _gen_dict(self, mapping=()):
        """A `NoCaseMultiDict` can be constructed from an iterable of
        ``(key, value)`` tuples or a dict.
        """
        tmp = {}
        if isinstance(mapping, NoCaseMultiDict):
            for key, value in mapping.iteritems():
                tmp.setdefault(key.lower(), (key, []))[1].extend(value)
        else:
            if isinstance(mapping, dict):
                itr = mapping.items()
            else:
                itr = iter(mapping)
            for key, value in itr:
                tmp.setdefault(key.lower(), (key, []))[1].append(value)
        return tmp

    def __init__(self, mapping=()):
        """A `NoCaseMultiDict` can be constructed from an iterable of
        ``(key, value)`` tuples or a dict.
        """
        super().__init__(self._gen_dict(mapping))

    def update(self, mapping=(), append=False):
        """A `NoCaseMultiDict` can be updated from an iterable of
        ``(key, value)`` tuples or a dict.
        """
        for _, (key, values) in self._gen_dict(mapping).items():
            self.set(key, values, append=append, unpack=True)

    def __getitem__(self, key):
        """
        Return the first data value for this key.

        :raise KeyError: if the key does not exist
        """
        if key in self:
            return dict.__getitem__(self, key.lower())[1][0]
        raise KeyError(key)

    def __setitem__(self, key, value):
        dict.setdefault(self, key.lower(), (key, []))[1][:] = [value]

    def __delitem__(self, key):
        dict.__delitem__(self, key.lower())

    def __contains__(self, key):
        return dict.__contains__(self, key.lower())

    def __getstate__(self):
        data = []
        for key, values in self.iteritems():
            for v in values:
                data.append((key, v))
        return data

    def __setstate__(self, data):
        self.__init__(data)

    def get(self, key, default=None, type_func=None):
        """Return the default value if the requested data doesn't exist.
        If `type_func` is provided and is a callable it should convert the value,
        return it or raise a `ValueError` if that is not possible.  In this
        case the function will return the default as if the value was not
        found.

        Example:

        >>> d = NoCaseMultiDict(dict(foo='42', bar='blub'))
        >>> d.get('foo', type_func=int)
        42
        >>> d.get('bar', -1, type_func=int)
        -1
        """
        try:
            rv = self[key]
            if type_func is not None:
                rv = type_func(rv)
        except (KeyError, ValueError):
            rv = default
        return rv

    def get_all(self, key):
        """
        Return all values for the key as a list. Returns an empty list, if
        the key doesn't exist.
        """
        if key in self:
            return dict.__getitem__(self, key.lower())[1]
        else:
            return []

    def set(self, key, value, append=False, unpack=False):
        """
        Set a `value` for the `key`. If `append` is ``True`` the value will be added
        to other values for this `key`.

        If `unpack` is True, `value` will be unpacked and each item will be added.
        """
        if key in self:
            if not append:
                dict.__getitem__(self, key.lower())[1][:] = []
        else:
            dict.__setitem__(self, key.lower(), (key, []))
        if unpack:
            for v in value:
                dict.__getitem__(self, key.lower())[1].append(v)
        else:
            dict.__getitem__(self, key.lower())[1].append(value)

    def iteritems(self):
        """
        Iterates over all keys and values.
        """
        for _, (key, values) in dict.items(self):
            yield key, values

    def copy(self):
        """
        Returns a copy of this object.
        """
        return self.__class__(self)

    def __repr__(self):
        tmp = []
        for key, values in self.iteritems():
            tmp.append((key, values))
        return '%s(%r)' % (self.__class__.__name__, tmp)
