# -:- encoding: utf8 -:-
# Copyright (c) 2011, Oliver Tonnhofer <olt@omniscale.de>
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from __future__ import absolute_import

import unittest

from ..validator import validate, ValidationError, SpecError
from ..spec import required, one_off, number, recursive, type_spec, anything


def raises(exception):
    def wrapper(f):
        def _wrapper(self):
            try:
                f(self)
            except exception:
                pass
            else:
                raise AssertionError('expected exception %s', exception)
    return wrapper

class TestSimpleDict(unittest.TestCase):
    def test_validate_simple_dict(self):
        spec = {'hello': 1, 'world': True}
        validate(spec, {'hello': 34, 'world': False})

    @raises(ValidationError)
    def test_invalid_key(self):
        spec = {'world': True}
        validate(spec, {'world_foo': False})

    def test_empty_data(self):
        spec = {'world': 1}
        validate(spec, {})

    @raises(ValidationError)
    def test_invalid_value(self):
        spec = {'world': 1}
        validate(spec, {'world_foo': False})

    @raises(ValidationError)
    def test_missing_required_key(self):
        spec = {required('world'): 1}
        validate(spec, {})
    
    def test_valid_one_off(self):
        spec = {'hello': one_off(1, bool())}
        validate(spec, {'hello': 129})
        validate(spec, {'hello': True})
    
    @raises(ValidationError)
    def test_invalid_one_off(self):
        spec = {'hello': one_off(1, False)}
        validate(spec, {'hello': []})

    def test_instances_and_types(self):
        spec = {'str()': str(), 'basestring': basestring, 'int': int, 'int()': int()}
        validate(spec, {'str()': 'str', 'basestring': u'☃', 'int': 1, 'int()': 1})


class TestLists(unittest.TestCase):
    def test_list(self):
        spec = [1]
        validate(spec, [1, 2, 3, 4, -9])

    def test_empty_list(self):
        spec = [1]
        validate(spec, [])
    
    @raises(ValidationError)
    def test_invalid_item(self):
        spec = [1]
        validate(spec, [1, 'hello'])

class TestNumber(unittest.TestCase):
    def check_valid(self, spec, data):
        validate(spec, data)
    
    def test_numbers(self):
        spec = number()
        for i in (0, 1, 23e999, int(10e20), 23.1, -0.0000000001):
            yield self.check_valid, spec, i

class TestNested(unittest.TestCase):
    def check_valid(self, spec, data):
        validate(spec, data)
    
    @raises(ValidationError)
    def check_invalid(self, spec, data):
        validate(spec, data)
        
    def test_dict(self):
        spec = {
            'globals': {
                'image': {
                    'format': {
                        'png': {
                            'mode': 'RGB',
                        }
                    },
                },
                'cache': {
                    'base_dir': '/path/to/foo'
                }
            }
        }
        
        yield self.check_valid, spec, {'globals': {'image': {'format': {'png': {'mode': 'P'}}}}}
        yield self.check_valid, spec, {'globals': {'image': {'format': {'png': {'mode': 'P'}}},
                                                   'cache': {'base_dir': '/somewhere'}}}
        yield self.check_invalid, spec, {'globals': {'image': {'foo': {'png': {'mode': 'P'}}}}}
        yield self.check_invalid, spec, {'globals': {'image': {'png': {'png': {'mode': 1}}}}}

class TestRecursive(unittest.TestCase):
    def test(self):
        spec = recursive({'hello': str(), 'more': recursive()})
        validate(spec, {'hello': 'world', 'more': {'hello': 'foo', 'more': {'more': {}}}})

    def test_multiple(self):
        spec = {'a': recursive({'hello': str(), 'more': recursive()}), 'b': recursive({'foo': recursive()})}
        validate(spec, {'b': {'foo': {'foo': {}}}})
        validate(spec, {'a': {'hello': 'world', 'more': {'hello': 'foo', 'more': {'more': {}}}}})
        validate(spec, {'b': {'foo': {'foo': {}}},
                        'a': {'hello': 'world', 'more': {'hello': 'foo', 'more': {'more': {}}}}})
    @raises(SpecError)
    def test_without_spec(self):
        spec = {'a': recursive()}
        validate(spec, {'a': {'a': {}}})

class TestTypeSpec(unittest.TestCase):
    def test(self):
        spec = type_spec('type', {'foo': {'alpha': str()}, 'bar': {'one': 1, 'two': str()}})
        validate(spec, {'type': 'foo', 'alpha': 'yes'})
        validate(spec, {'type': 'bar', 'one': 2})

class TestErrors(unittest.TestCase):
    def test_invalid_types(self):
        spec = {'str': str, 'str()': str(), 'basestring': basestring, '1': 1, 'int': int}
        try:
            validate(spec, {'str': 1, 'str()': 1, 'basestring': 1, '1': 'a', 'int': 'int'})
        except ValidationError, ex:
            ex.errors.sort()
            assert ex.errors[0] == "'a' in 1 not of type int"
            assert ex.errors[1] == "'int' in int not of type int"
            assert ex.errors[2] == '1 in basestring not of type basestring'
            assert ex.errors[3] == '1 in str not of type str'
            assert ex.errors[4] == '1 in str() not of type str'
        else:
            assert False

    def test_invalid_key(self):
        spec = {'world': {'europe': {}}}
        try:
            validate(spec, {'world': {'europe': {'germany': 1}}})
        except ValidationError, ex:
            assert 'world.europe' in str(ex)
        else:
            assert False

    def test_invalid_list_item(self):
        spec = {'numbers': [number()]}
        try:
            validate(spec, {'numbers': [1, 2, 3, 'foo']})
        except ValidationError, ex:
            assert 'numbers[3] not of type number' in str(ex), str(ex)
        else:
            assert False

    def test_multiple_invalid_list_items(self):
        spec = {'numbers': [number()]}
        try:
            validate(spec, {'numbers': [1, True, 3, 'foo']})
        except ValidationError, ex:
            assert '2 validation errors' in str(ex), str(ex)
            assert 'numbers[1] not of type number' in ex.errors[0]
            assert 'numbers[3] not of type number' in ex.errors[1]
        else:
            assert False

    def test_error_in_non_string_key(self):
        spec = {1: bool()}
        try:
            validate(spec, {1: 'not a bool'})
        except ValidationError, ex:
            assert "'not a bool' in 1 not of type bool" in ex.errors[0]
        else:
            assert False
    
    def test_error_in_non_string_key_with_anything_key_spec(self):
        spec = {anything(): bool()}
        try:
            validate(spec, {1: 'not a bool'})
        except ValidationError, ex:
            assert "'not a bool' in 1 not of type bool" in ex.errors[0]
        else:
            assert False

if __name__ == '__main__':
    unittest.main()

