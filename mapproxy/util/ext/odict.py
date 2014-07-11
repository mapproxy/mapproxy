# -*- coding: utf-8 -*-
"""
    odict
    ~~~~~

    This module is an example implementation of an ordered dict for the
    collections module.  It's not written for performance (it actually
    performs pretty bad) but to show how the API works.


    Questions and Answers
    =====================

    Why would anyone need ordered dicts?

        Dicts in python are unordered which means that the order of items when
        iterating over dicts is undefined.  As a matter of fact it is most of
        the time useless and differs from implementation to implementation.

        Many developers stumble upon that problem sooner or later when
        comparing the output of doctests which often does not match the order
        the developer thought it would.

        Also XML systems such as Genshi have their problems with unordered
        dicts as the input and output ordering of tag attributes is often
        mixed up because the ordering is lost when converting the data into
        a dict.  Switching to lists is often not possible because the
        complexity of a lookup is too high.

        Another very common case is metaprogramming.  The default namespace
        of a class in python is a dict.  With Python 3 it becomes possible
        to replace it with a different object which could be an ordered dict.
        Django is already doing something similar with a hack that assigns
        numbers to some descriptors initialized in the class body of a
        specific subclass to restore the ordering after class creation.

        When porting code from programming languages such as PHP and Ruby
        where the item-order in a dict is guaranteed it's also a great help
        to have an equivalent data structure in Python to ease the transition.

    Where are new keys added?

        At the end.  This behavior is consistent with Ruby 1.9 Hashmaps
        and PHP Arrays.  It also matches what common ordered dict
        implementations do currently.

    What happens if an existing key is reassigned?

        The key is *not* moved.  This is consitent with existing
        implementations and can be changed by a subclass very easily::

            class movingodict(odict):
                def __setitem__(self, key, value):
                    self.pop(key, None)
                    odict.__setitem__(self, key, value)

        Moving keys to the end of a ordered dict on reassignment is not
        very useful for most applications.

    Does it mean the dict keys are sorted by a sort expression?

        That's not the case.  The odict only guarantees that there is an order
        and that newly inserted keys are inserted at the end of the dict.  If
        you want to sort it you can do so, but newly added keys are again added
        at the end of the dict.

    I initializes the odict with a dict literal but the keys are not
    ordered like they should!

        Dict literals in Python generate dict objects and as such the order of
        their items is not guaranteed.  Before they are passed to the odict
        constructor they are already unordered.

    What happens if keys appear multiple times in the list passed to the
    constructor?

        The same as for the dict.  The latter item overrides the former.  This
        has the side-effect that the position of the first key is used because
        the key is actually overwritten:

        >>> odict([('a', 1), ('b', 2), ('a', 3)])
        odict.odict([('a', 3), ('b', 2)])

        This behavor is consistent with existing implementation in Python
        and the PHP array and the hashmap in Ruby 1.9.

    This odict doesn't scale!

        Yes it doesn't.  The delitem operation is O(n).  This is file is a
        mockup of a real odict that could be implemented for collections
        based on an linked list.

    Why is there no .insert()?

        There are few situations where you really want to insert a key at
        an specified index.  To now make the API too complex the proposed
        solution for this situation is creating a list of items, manipulating
        that and converting it back into an odict:

        >>> d = odict([('a', 42), ('b', 23), ('c', 19)])
        >>> l = d.items()
        >>> l.insert(1, ('x', 0))
        >>> odict(l)
        odict.odict([('a', 42), ('x', 0), ('b', 23), ('c', 19)])

    :copyright: (c) 2008 by Armin Ronacher and PEP 273 authors.
    :license: modified BSD license.
"""
from __future__ import absolute_import
from mapproxy.compat import iteritems
from mapproxy.compat.itertools import izip, imap
from copy import deepcopy

missing = object()


class odict(dict):
    """
    Ordered dict example implementation.

    This is the proposed interface for a an ordered dict as proposed on the
    Python mailinglist (proposal_).

    It's a dict subclass and provides some list functions.  The implementation
    of this class is inspired by the implementation of Babel but incorporates
    some ideas from the `ordereddict`_ and Django's ordered dict.

    The constructor and `update()` both accept iterables of tuples as well as
    mappings:

    >>> d = odict([('a', 'b'), ('c', 'd')])
    >>> d.update({'foo': 'bar'})
    >>> d
    odict.odict([('a', 'b'), ('c', 'd'), ('foo', 'bar')])

    Keep in mind that when updating from dict-literals the order is not
    preserved as these dicts are unsorted!

    You can copy an odict like a dict by using the constructor, `copy.copy`
    or the `copy` method and make deep copies with `copy.deepcopy`:

    >>> from copy import copy, deepcopy
    >>> copy(d)
    odict.odict([('a', 'b'), ('c', 'd'), ('foo', 'bar')])
    >>> d.copy()
    odict.odict([('a', 'b'), ('c', 'd'), ('foo', 'bar')])
    >>> odict(d)
    odict.odict([('a', 'b'), ('c', 'd'), ('foo', 'bar')])
    >>> d['spam'] = []
    >>> d2 = deepcopy(d)
    >>> d2['spam'].append('eggs')
    >>> d
    odict.odict([('a', 'b'), ('c', 'd'), ('foo', 'bar'), ('spam', [])])
    >>> d2
    odict.odict([('a', 'b'), ('c', 'd'), ('foo', 'bar'), ('spam', ['eggs'])])

    All iteration methods as well as `keys`, `values` and `items` return
    the values ordered by the the time the key-value pair is inserted:

    >>> d.keys()
    ['a', 'c', 'foo', 'spam']
    >>> list(d.values())
    ['b', 'd', 'bar', []]
    >>> list(d.items())
    [('a', 'b'), ('c', 'd'), ('foo', 'bar'), ('spam', [])]
    >>> list(d.iterkeys())
    ['a', 'c', 'foo', 'spam']
    >>> list(d.itervalues())
    ['b', 'd', 'bar', []]
    >>> list(d.iteritems())
    [('a', 'b'), ('c', 'd'), ('foo', 'bar'), ('spam', [])]

    Index based lookup is supported too by `byindex` which returns the
    key/value pair for an index:

    >>> d.byindex(2)
    ('foo', 'bar')

    You can reverse the odict as well:

    >>> d.reverse()
    >>> d
    odict.odict([('spam', []), ('foo', 'bar'), ('c', 'd'), ('a', 'b')])

    And sort it like a list:

    >>> d.sort(key=lambda x: x[0].lower())
    >>> d
    odict.odict([('a', 'b'), ('c', 'd'), ('foo', 'bar'), ('spam', [])])

    .. _proposal: http://thread.gmane.org/gmane.comp.python.devel/95316
    .. _ordereddict: http://www.xs4all.nl/~anthon/Python/ordereddict/
    """

    def __init__(self, *args, **kwargs):
        dict.__init__(self)
        self._keys = []
        self.update(*args, **kwargs)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self._keys.remove(key)

    def __setitem__(self, key, item):
        if key not in self:
            self._keys.append(key)
        dict.__setitem__(self, key, item)

    def __deepcopy__(self, memo=None):
        if memo is None:
            memo = {}
        d = memo.get(id(self), missing)
        if d is not missing:
            return d
        memo[id(self)] = d = self.__class__()
        dict.__init__(d, deepcopy(self.items(), memo))
        d._keys = self._keys[:]
        return d

    def __getstate__(self):
        return {'items': dict(self), 'keys': self._keys}

    def __setstate__(self, d):
        self._keys = d['keys']
        dict.update(d['items'])

    def __reversed__(self):
        return reversed(self._keys)

    def __eq__(self, other):
        if isinstance(other, odict):
            if not dict.__eq__(self, other):
                return False
            return self.items() == other.items()
        return dict.__eq__(self, other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __cmp__(self, other):
        if isinstance(other, odict):
            return cmp(self.items(), other.items())
        elif isinstance(other, dict):
            return dict.__cmp__(self, other)
        return NotImplemented

    @classmethod
    def fromkeys(cls, iterable, default=None):
        return cls((key, default) for key in iterable)

    def clear(self):
        del self._keys[:]
        dict.clear(self)

    def copy(self):
        return self.__class__(self)

    def items(self):
        return list(zip(self._keys, self.values()))

    def iteritems(self):
        return izip(self._keys, self.itervalues())

    def keys(self):
        return self._keys[:]

    def iterkeys(self):
        return iter(self._keys)

    def pop(self, key, default=missing):
        if default is missing:
            return dict.pop(self, key)
        elif key not in self:
            return default
        self._keys.remove(key)
        return dict.pop(self, key, default)

    def popitem(self, key):
        self._keys.remove(key)
        return dict.popitem(key)

    def setdefault(self, key, default=None):
        if key not in self:
            self._keys.append(key)
        dict.setdefault(self, key, default)

    def update(self, *args, **kwargs):
        sources = []
        if len(args) == 1:
            if hasattr(args[0], 'iteritems') or hasattr(args[0], 'items'):
                sources.append(iteritems(args[0]))
            else:
                sources.append(iter(args[0]))
        elif args:
            raise TypeError('expected at most one positional argument')
        if kwargs:
            sources.append(kwargs.iteritems())
        for iterable in sources:
            for key, val in iterable:
                self[key] = val

    def values(self):
        return map(self.get, self._keys)

    def itervalues(self):
        return imap(self.get, self._keys)

    def index(self, item):
        return self._keys.index(item)

    def byindex(self, item):
        key = self._keys[item]
        return (key, dict.__getitem__(self, key))

    def reverse(self):
        self._keys.reverse()

    def sort(self, *args, **kwargs):
        self._keys.sort(*args, **kwargs)

    def __repr__(self):
        return 'odict.odict(%r)' % self.items()

    __copy__ = copy
    __iter__ = iterkeys


if __name__ == '__main__':
    import doctest
    doctest.testmod()