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

from mapproxy.util.collections import LRU

from nose.tools import eq_, raises

class TestLRU(object):
    @raises(KeyError)
    def test_missing_key(self):
        lru = LRU(10)
        lru['foo']
    
    def test_contains(self):
        lru = LRU(10)
        lru['foo1'] = 1
        
        assert 'foo1' in lru
        assert 'foo2' not in lru
    
    def test_repr(self):
        lru = LRU(10)
        lru['foo1'] = 1
        assert 'size=10' in repr(lru)
        assert 'foo1' in repr(lru)
        
    def test_getitem(self):
        lru = LRU(10)
        lru['foo1'] = 1
        lru['foo2'] = 2
        eq_(lru['foo1'], 1)
        eq_(lru['foo2'], 2)
    
    def test_get(self):
        lru = LRU(10)
        lru['foo1'] = 1
        eq_(lru.get('foo1'), 1)
        eq_(lru.get('foo1', 2), 1)
    
    def test_get_default(self):
        lru = LRU(10)
        lru['foo1'] = 1
        eq_(lru.get('foo2'), None)
        eq_(lru.get('foo2', 2), 2)
        
    def test_delitem(self):
        lru = LRU(10)
        lru['foo1'] = 1
        assert 'foo1' in lru
        del lru['foo1']
        assert 'foo1' not in lru
        
    def test_empty(self):
        lru = LRU(10)
        assert bool(lru) == False
        lru['foo1'] = '1'
        assert bool(lru) == True
    
    def test_setitem_overflow(self):
        lru = LRU(2)
        lru['foo1'] = 1
        lru['foo2'] = 2
        lru['foo3'] = 3
        
        assert 'foo1' not in lru
        assert 'foo2' in lru
        assert 'foo3' in lru

    def test_length(self):
        lru = LRU(2)
        eq_(len(lru), 0)
        lru['foo1'] = 1
        eq_(len(lru), 1)
        lru['foo2'] = 2
        eq_(len(lru), 2)
        lru['foo3'] = 3
        eq_(len(lru), 2)
        
        del lru['foo3']
        eq_(len(lru), 1)
        