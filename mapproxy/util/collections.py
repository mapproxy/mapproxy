# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import
from collections import deque
from itertools import islice

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

