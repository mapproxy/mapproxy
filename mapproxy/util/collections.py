# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
from collections import deque
from mapproxy.compat.itertools import islice
from mapproxy.compat import string_type

class LRU(object):
    """
    Least Recently Used dictionary.

    Stores `size` key-value pairs. Removes last used key-value
    when dict is full.


    This LRU was developed for sizes <1000.
    Set new: O(1)
    Get/Set existing: O(1) newest to O(n) for oldest entry
    Contains: O(1)
    """
    def __init__(self, size=100):
        self.size = size
        self.values = {}
        self.last_used = deque()

    def get(self, key, default=None):
        if key not in self.values:
            return default
        else:
            return self[key]

    def __repr__(self):
        last_values = []
        for k in islice(self.last_used, 10):
            last_values.append((k, self.values[k]))

        return '<LRU size=%d values=%s%s>' % (
            self.size, repr(last_values)[:-1],
            ', ...]' if len(self)>10 else ']')

    def __getitem__(self, key):
        result = self.values[key]
        try:
            self.last_used.remove(key)
        except ValueError:
            pass
        self.last_used.appendleft(key)
        return result

    def __setitem__(self, key, value):
        if key in self.values:
            try:
                self.last_used.remove(key)
            except ValueError:
                pass
        self.last_used.appendleft(key)
        self.values[key] = value

        while len(self.values) > self.size:
            del self.values[self.last_used.pop()]

    def __len__(self):
        return len(self.values)

    def __delitem__(self, key):
        if key in self.values:
            try:
                self.last_used.remove(key)
            except ValueError:
                pass
        del self.values[key]

    def __contains__(self, key):
        return key in self.values


class ImmutableDictList(object):
    """
    A dictionary where each item can also be accessed by the
    integer index of the initial position.

    >>> d = ImmutableDictList([('foo', 23), ('bar', 24)])
    >>> d['bar']
    24
    >>> d[0], d[1]
    (23, 24)
    """
    def __init__(self, items):
        self._names = []
        self._values = {}
        for name, value in items:
            self._values[name] = value
            self._names.append(name)

    def __getitem__(self, name):
        if isinstance(name, string_type):
            return self._values[name]
        else:
            return self._values[self._names[name]]

    def __contains__(self, name):
        try:
            self[name]
            return True
        except KeyError:
            return False

    def __len__(self):
        return len(self._values)

    def __str__(self):
        values = []
        for name in self._names:
            values.append('%s: %s' % (name, self._values[name]))
        return '[%s]' % (', '.join(values),)

    def iteritems(self):
        for idx in self._names:
            yield idx, self._values[idx]
