# missing izip_longest function for Python 2.5 compatibility
# http://docs.python.org/library/itertools.html#itertools.izip_longest
# Copyright 2001-2012 Python Software Foundation; All Rights Reserved

from __future__ import absolute_import
import itertools

if hasattr(itertools, 'izip_longest'):
    izip_longest = itertools.izip_longest
else:
    class ZipExhausted(Exception):
        pass

    def izip_longest(*args, **kwds):
        # izip_longest('ABCD', 'xy', fillvalue='-') --> Ax By C- D-
        fillvalue = kwds.get('fillvalue')
        counter = [len(args) - 1]
        def sentinel():
            if not counter[0]:
                raise ZipExhausted
            counter[0] -= 1
            yield fillvalue
        fillers = itertools.repeat(fillvalue)
        iterators = [itertools.chain(it, sentinel(), fillers) for it in args]
        try:
            while iterators:
                yield tuple(i.next() for i in iterators)
        except ZipExhausted:
            pass