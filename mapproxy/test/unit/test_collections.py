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

from mapproxy.util.collections import LRU, ImmutableDictList

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


class TestImmutableDictList(object):
    def test_named(self):
        res = ImmutableDictList([('one', 10), ('two', 5), ('three', 3)])
        assert res[0] == 10
        assert res[2] == 3
        assert res['one'] == 10
        assert res['three'] == 3
        assert len(res) == 3
    
    def test_named_iteritems(self):
        res = ImmutableDictList([('one', 10), ('two', 5), ('three', 3)])
        itr = res.iteritems()
        eq_(itr.next(), ('one', 10))
        eq_(itr.next(), ('two', 5))
        eq_(itr.next(), ('three', 3))
        try:
            itr.next()
        except StopIteration:
            pass
        else:
            assert False, 'StopIteration expected'