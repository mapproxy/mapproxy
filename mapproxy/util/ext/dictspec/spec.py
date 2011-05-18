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

class required(str):
    """
    Mark a dictionary key as required.
    """
    pass

class anything(object):
    """
    Wildcard key or value for dictionaries.

    >>> from .validator import validate
    >>> validate({anything(): 1}, {'foo': 2, 'bar': 49})
    """
    def compare_type(self, data):
        return True

class recursive(object):
    """
    Recursive types.
    
    >>> from .validator import validate
    >>> spec = recursive({'foo': recursive()})
    >>> validate(spec, {'foo': {'foo': {'foo':{}}}})
    """
    def __init__(self, spec=None):
        self.spec = spec
    def compare_type(self, data):
        return isinstance(data, type(self.spec))

class one_off(object):
    """
    One off the given types.

    >>> from .validator import validate
    >>> validate(one_off(str(), number()), 'foo')
    >>> validate(one_off(str(), number()), 32)
    """
    def __init__(self, *specs):
        self.specs = specs

def combined(*dicts):
    """
    Combine multiple dicts.
    
    >>> (combined({'a': 'foo'}, {'b': 'bar'})
    ...  == {'a': 'foo', 'b': 'bar'})
    True
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result

class number(object):
    """
    Any number.

    >>> from .validator import validate
    >>> validate(number(), 1)
    >>> validate(number(), -32.0)
    >>> validate(number(), 99999999999999L)
    """
    def compare_type(self, data):
        # True/False are also instances of int, exclude them
        return isinstance(data, (float, int, long)) and not isinstance(data, bool)

class type_spec(object):
    def __init__(self, type_key, specs):
        self.type_key = type_key
        self.specs = specs

        for v in specs.itervalues():
            if not isinstance(v, dict):
                raise ValueError('%s requires dict subspecs', self.__class__)
            if self.type_key not in v:
                v[self.type_key] = str()

    def subspec(self, data, context):
        if self.type_key not in data:
            raise ValueError("'%s' not in %s" % (self.type_key, context.current_pos))
        key = data[self.type_key]

        if key not in self.specs:
            raise ValueError("unknown %s value '%s' in %s" % (self.type_key, key, context.current_pos))
        return self.specs[key]
