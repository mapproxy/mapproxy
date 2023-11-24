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

"""
Python related helper functions.
"""
from functools import wraps
from mapproxy.compat import PY2

def reraise_exception(new_exc, exc_info):
    """
    Reraise exception (`new_exc`) with the given `exc_info`.
    """
    _exc_class, _exc, tb = exc_info
    if PY2:
        exec('raise new_exc.__class__, new_exc, tb')
    else:
        raise new_exc.with_traceback(tb)

def reraise(exc_info):
    """
    Reraise exception from exc_info`.
    """
    exc_class, exc, tb = exc_info
    if PY2:
        exec('raise exc_class, exc, tb')
    else:
        raise exc.with_traceback(tb)



class cached_property(object):
    """A decorator that converts a function into a lazy property. The
    function wrapped is called the first time to retrieve the result
    and than that calculated result is used the next time you access
    the value::

        class Foo(object):

            @cached_property
            def foo(self):
                # calculate something important here
                return 42
    """

    def __init__(self, func, name=None, doc=None):
        self.func = func
        self.__name__ = name or func.__name__
        self.__doc__ = doc or func.__doc__

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = self.func(obj)
        setattr(obj, self.__name__, value)
        return value

def memoize(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, '__memoize_cache'):
            self.__memoize_cache = {}
        cache = self.__memoize_cache.setdefault(func, {})
        key = args + tuple(kwargs.items())
        if key not in cache:
            cache[key] = func(self, *args, **kwargs)
        return cache[key]
    return wrapper

