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
        if isinstance(name, str):
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
