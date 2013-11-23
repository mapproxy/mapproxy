# -*- coding: utf-8 -*-
"""
This module implements context-local objects.

This is a partial version of werkzeug/local.py containing only Local and
StackLocal.

Last update: 2011-03-15 9ada59c958b2edbb9739fb55a6b32ef4a97dac07

:copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
try:
    from greenlet import getcurrent as get_current_greenlet
except ImportError: # pragma: no cover
    try:
        from py.magic import greenlet
        get_current_greenlet = greenlet.getcurrent
        del greenlet
    except Exception:
        # catch all, py.* fails with so many different errors.
        get_current_greenlet = int
try:
    from _thread import get_ident as get_current_thread, allocate_lock
except ImportError: # pragma: no cover
    try:
        from thread import get_ident as get_current_thread, allocate_lock
    except ImportError: # pragma: no cover
        from dummy_thread import get_ident as get_current_thread, allocate_lock


# get the best ident function.  if greenlets are not installed we can
# safely just use the builtin thread function and save a python methodcall
# and the cost of calculating a hash.
if get_current_greenlet is int: # pragma: no cover
    get_ident = get_current_thread
else:
    get_ident = lambda: (get_current_thread(), get_current_greenlet())


def release_local(local):
    """Releases the contents of the local for the current context.
    This makes it possible to use locals without a manager.

    Example::

        >>> loc = Local()
        >>> loc.foo = 42
        >>> release_local(loc)
        >>> hasattr(loc, 'foo')
        False

    With this function one can release :class:`Local` objects as well
    as :class:`StackLocal` objects.  However it is not possible to
    release data held by proxies that way, one always has to retain
    a reference to the underlying local object in order to be able
    to release it.

    .. versionadded:: 0.6.1
    """
    local.__release_local__()


class Local(object):
    __slots__ = ('__storage__', '__lock__', '__ident_func__')

    def __init__(self):
        object.__setattr__(self, '__storage__', {})
        object.__setattr__(self, '__lock__', allocate_lock())
        object.__setattr__(self, '__ident_func__', get_ident)

    def __iter__(self):
        return self.__storage__.iteritems()

    def __call__(self, proxy):
        """Create a proxy for a name."""
        return LocalProxy(self, proxy)

    def __release_local__(self):
        self.__storage__.pop(self.__ident_func__(), None)

    def __getattr__(self, name):
        try:
            return self.__storage__[self.__ident_func__()][name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        ident = self.__ident_func__()
        self.__lock__.acquire()
        try:
            storage = self.__storage__
            if ident in storage:
                storage[ident][name] = value
            else:
                storage[ident] = {name: value}
        finally:
            self.__lock__.release()

    def __delattr__(self, name):
        try:
            del self.__storage__[self.__ident_func__()][name]
        except KeyError:
            raise AttributeError(name)


class LocalStack(object):
    """This class works similar to a :class:`Local` but keeps a stack
    of objects instead.  This is best explained with an example::

        >>> ls = LocalStack()
        >>> ls.push(42)
        [42]
        >>> ls.top
        42
        >>> ls.push(23)
        [42, 23]
        >>> ls.top
        23
        >>> ls.pop()
        23
        >>> ls.top
        42

    They can be force released by using a :class:`LocalManager` or with
    the :func:`release_local` function but the correct way is to pop the
    item from the stack after using.  When the stack is empty it will
    no longer be bound to the current context (and as such released).

    By calling the stack without arguments it returns a proxy that resolves to
    the topmost item on the stack.

    .. versionadded:: 0.6.1
    """

    def __init__(self):
        self._local = Local()
        self._lock = allocate_lock()

    def __release_local__(self):
        self._local.__release_local__()

    def _get__ident_func__(self):
        return self._local.__ident_func__
    def _set__ident_func__(self, value):
        object.__setattr__(self._local, '__ident_func__', value)
    __ident_func__ = property(_get__ident_func__, _set__ident_func__)
    del _get__ident_func__, _set__ident_func__

    def __call__(self):
        def _lookup():
            rv = self.top
            if rv is None:
                raise RuntimeError('object unbound')
            return rv
        return LocalProxy(_lookup)

    def push(self, obj):
        """Pushes a new item to the stack"""
        self._lock.acquire()
        try:
            rv = getattr(self._local, 'stack', None)
            if rv is None:
                self._local.stack = rv = []
            rv.append(obj)
            return rv
        finally:
            self._lock.release()

    def pop(self):
        """Removes the topmost item from the stack, will return the
        old value or `None` if the stack was already empty.
        """
        self._lock.acquire()
        try:
            stack = getattr(self._local, 'stack', None)
            if stack is None:
                return None
            elif len(stack) == 1:
                release_local(self._local)
                return stack[-1]
            else:
                return stack.pop()
        finally:
            self._lock.release()

    @property
    def top(self):
        """The topmost item on the stack.  If the stack is empty,
        `None` is returned.
        """
        try:
            return self._local.stack[-1]
        except (AttributeError, IndexError):
            return None

