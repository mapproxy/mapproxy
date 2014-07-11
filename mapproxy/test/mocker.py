"""
Mocker

Graceful platform for test doubles in Python: mocks, stubs, fakes, and dummies.

Copyright (c) 2007-2010, Gustavo Niemeyer <gustavo@niemeyer.net>

All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice,
      this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice,
      this list of conditions and the following disclaimer in the documentation
      and/or other materials provided with the distribution.
    * Neither the name of the copyright holder nor the names of its
      contributors may be used to endorse or promote products derived from
      this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
import tempfile
import unittest
import inspect
import shutil
import types
import sys
import os
import re
import gc


if sys.version_info < (2, 4):
    from sets import Set as set # pragma: nocover

if sys.version_info[0] == 2:
    import __builtin__
else:
    import builtins as __builtin__

from mapproxy.compat import iteritems

__all__ = ["Mocker", "Expect", "expect", "IS", "CONTAINS", "IN", "MATCH",
           "ANY", "ARGS", "KWARGS", "MockerTestCase"]


__author__ = "Gustavo Niemeyer <gustavo@niemeyer.net>"
__license__ = "BSD"
__version__ = "1.1"


ERROR_PREFIX = "[Mocker] "


# --------------------------------------------------------------------
# Exceptions

class MatchError(AssertionError):
    """Raised when an unknown expression is seen in playback mode."""


# --------------------------------------------------------------------
# Helper for chained-style calling.

class expect(object):
    """This is a simple helper that allows a different call-style.

    With this class one can comfortably do chaining of calls to the
    mocker object responsible by the object being handled. For instance::

        expect(obj.attr).result(3).count(1, 2)

    Is the same as::

        obj.attr
        mocker.result(3)
        mocker.count(1, 2)

    """

    __mocker__ = None

    def __init__(self, mock, attr=None):
        self._mock = mock
        self._attr = attr

    def __getattr__(self, attr):
        return self.__class__(self._mock, attr)

    def __call__(self, *args, **kwargs):
        mocker = self.__mocker__
        if not mocker:
            mocker = self._mock.__mocker__
        getattr(mocker, self._attr)(*args, **kwargs)
        return self


def Expect(mocker):
    """Create an expect() "function" using the given Mocker instance.

    This helper allows defining an expect() "function" which works even
    in trickier cases such as:

        expect = Expect(mymocker)
        expect(iter(mock)).generate([1, 2, 3])

    """
    return type("Expect", (expect,), {"__mocker__": mocker})


# --------------------------------------------------------------------
# Extensions to Python's unittest.

class MockerTestCase(unittest.TestCase):
    """unittest.TestCase subclass with Mocker support.

    @ivar mocker: The mocker instance.

    This is a convenience only.  Mocker may easily be used with the
    standard C{unittest.TestCase} class if wanted.

    Test methods have a Mocker instance available on C{self.mocker}.
    At the end of each test method, expectations of the mocker will
    be verified, and any requested changes made to the environment
    will be restored.

    In addition to the integration with Mocker, this class provides
    a few additional helper methods.
    """

    def __init__(self, methodName="runTest"):
        # So here is the trick: we take the real test method, wrap it on
        # a function that do the job we have to do, and insert it in the
        # *instance* dictionary, so that getattr() will return our
        # replacement rather than the class method.
        test_method = getattr(self, methodName, None)
        if test_method is not None:
            def test_method_wrapper():
                try:
                    result = test_method()
                except:
                    raise
                else:
                    if (self.mocker.is_recording() and
                        self.mocker.get_events()):
                        raise RuntimeError("Mocker must be put in replay "
                                           "mode with self.mocker.replay()")
                    if (hasattr(result, "addCallback") and
                        hasattr(result, "addErrback")):
                        def verify(result):
                            self.mocker.verify()
                            return result
                        result.addCallback(verify)
                    else:
                        self.mocker.verify()
                        self.mocker.restore()
                    return result
            # Copy all attributes from the original method..
            for attr in dir(test_method):
                # .. unless they're present in our wrapper already.
                if not hasattr(test_method_wrapper, attr) or attr == "__doc__":
                    setattr(test_method_wrapper, attr,
                            getattr(test_method, attr))
            setattr(self, methodName, test_method_wrapper)

        # We could overload run() normally, but other well-known testing
        # frameworks do it as well, and some of them won't call the super,
        # which might mean that cleanup wouldn't happen.  With that in mind,
        # we make integration easier by using the following trick.
        run_method = self.run
        def run_wrapper(*args, **kwargs):
            try:
                return run_method(*args, **kwargs)
            finally:
                self.__cleanup()
        self.run = run_wrapper

        self.mocker = Mocker()
        self.expect = Expect(self.mocker)

        self.__cleanup_funcs = []
        self.__cleanup_paths = []

        super(MockerTestCase, self).__init__(methodName)

    def __call__(self, *args, **kwargs):
        # This is necessary for Python 2.3 only, because it didn't use run(),
        # which is supported above.
        try:
            super(MockerTestCase, self).__call__(*args, **kwargs)
        finally:
            if sys.version_info < (2, 4):
                self.__cleanup()

    def __cleanup(self):
        for path in self.__cleanup_paths:
            if os.path.isfile(path):
                os.unlink(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
        self.mocker.reset()
        for func, args, kwargs in self.__cleanup_funcs:
            func(*args, **kwargs)

    def addCleanup(self, func, *args, **kwargs):
        self.__cleanup_funcs.append((func, args, kwargs))

    def makeFile(self, content=None, suffix="", prefix="tmp", basename=None,
                 dirname=None, path=None):
        """Create a temporary file and return the path to it.

        @param content: Initial content for the file.
        @param suffix: Suffix to be given to the file's basename.
        @param prefix: Prefix to be given to the file's basename.
        @param basename: Full basename for the file.
        @param dirname: Put file inside this directory.

        The file is removed after the test runs.
        """
        if path is not None:
            self.__cleanup_paths.append(path)
        elif basename is not None:
            if dirname is None:
                dirname = tempfile.mkdtemp()
                self.__cleanup_paths.append(dirname)
            path = os.path.join(dirname, basename)
        else:
            fd, path = tempfile.mkstemp(suffix, prefix, dirname)
            self.__cleanup_paths.append(path)
            os.close(fd)
            if content is None:
                os.unlink(path)
        if content is not None:
            file = open(path, "w")
            file.write(content)
            file.close()
        return path

    def makeDir(self, suffix="", prefix="tmp", dirname=None, path=None):
        """Create a temporary directory and return the path to it.

        @param suffix: Suffix to be given to the file's basename.
        @param prefix: Prefix to be given to the file's basename.
        @param dirname: Put directory inside this parent directory.

        The directory is removed after the test runs.
        """
        if path is not None:
            os.makedirs(path)
        else:
            path = tempfile.mkdtemp(suffix, prefix, dirname)
        self.__cleanup_paths.append(path)
        return path

    def failUnlessIs(self, first, second, msg=None):
        """Assert that C{first} is the same object as C{second}."""
        if first is not second:
            raise self.failureException(msg or "%r is not %r" % (first, second))

    def failIfIs(self, first, second, msg=None):
        """Assert that C{first} is not the same object as C{second}."""
        if first is second:
            raise self.failureException(msg or "%r is %r" % (first, second))

    def failUnlessIn(self, first, second, msg=None):
        """Assert that C{first} is contained in C{second}."""
        if first not in second:
            raise self.failureException(msg or "%r not in %r" % (first, second))

    def failUnlessStartsWith(self, first, second, msg=None):
        """Assert that C{first} starts with C{second}."""
        if first[:len(second)] != second:
            raise self.failureException(msg or "%r doesn't start with %r" %
                                               (first, second))

    def failIfStartsWith(self, first, second, msg=None):
        """Assert that C{first} doesn't start with C{second}."""
        if first[:len(second)] == second:
            raise self.failureException(msg or "%r starts with %r" %
                                               (first, second))

    def failUnlessEndsWith(self, first, second, msg=None):
        """Assert that C{first} starts with C{second}."""
        if first[len(first)-len(second):] != second:
            raise self.failureException(msg or "%r doesn't end with %r" %
                                               (first, second))

    def failIfEndsWith(self, first, second, msg=None):
        """Assert that C{first} doesn't start with C{second}."""
        if first[len(first)-len(second):] == second:
            raise self.failureException(msg or "%r ends with %r" %
                                               (first, second))

    def failIfIn(self, first, second, msg=None):
        """Assert that C{first} is not contained in C{second}."""
        if first in second:
            raise self.failureException(msg or "%r in %r" % (first, second))

    def failUnlessApproximates(self, first, second, tolerance, msg=None):
        """Assert that C{first} is near C{second} by at most C{tolerance}."""
        if abs(first - second) > tolerance:
            raise self.failureException(msg or "abs(%r - %r) > %r" %
                                        (first, second, tolerance))

    def failIfApproximates(self, first, second, tolerance, msg=None):
        """Assert that C{first} is far from C{second} by at least C{tolerance}.
        """
        if abs(first - second) <= tolerance:
            raise self.failureException(msg or "abs(%r - %r) <= %r" %
                                        (first, second, tolerance))

    def failUnlessMethodsMatch(self, first, second):
        """Assert that public methods in C{first} are present in C{second}.

        This method asserts that all public methods found in C{first} are also
        present in C{second} and accept the same arguments.  C{first} may
        have its own private methods, though, and may not have all methods
        found in C{second}.  Note that if a private method in C{first} matches
        the name of one in C{second}, their specification is still compared.

        This is useful to verify if a fake or stub class have the same API as
        the real class being simulated.
        """
        first_methods = dict(inspect.getmembers(first, inspect.ismethod))
        second_methods = dict(inspect.getmembers(second, inspect.ismethod))
        for name, first_method in iteritems(first_methods):
            first_argspec = inspect.getargspec(first_method)
            first_formatted = inspect.formatargspec(*first_argspec)

            second_method = second_methods.get(name)
            if second_method is None:
                if name[:1] == "_":
                    continue # First may have its own private methods.
                raise self.failureException("%s.%s%s not present in %s" %
                    (first.__name__, name, first_formatted, second.__name__))

            second_argspec = inspect.getargspec(second_method)
            if first_argspec != second_argspec:
                second_formatted = inspect.formatargspec(*second_argspec)
                raise self.failureException("%s.%s%s != %s.%s%s" %
                    (first.__name__, name, first_formatted,
                     second.__name__, name, second_formatted))

    def failUnlessRaises(self, excClass, *args, **kwargs):
        """
        Fail unless an exception of class excClass is thrown by callableObj
        when invoked with arguments args and keyword arguments kwargs. If a
        different type of exception is thrown, it will not be caught, and the
        test case will be deemed to have suffered an error, exactly as for an
        unexpected exception. It returns the exception instance if it matches
        the given exception class.

        This may also be used as a context manager when provided with a single
        argument, as such:

        with self.failUnlessRaises(ExcClass):
            logic_which_should_raise()
        """
        return self.failUnlessRaisesRegexp(excClass, None, *args, **kwargs)

    def failUnlessRaisesRegexp(self, excClass, regexp, *args, **kwargs):
        """
        Fail unless an exception of class excClass is thrown by callableObj
        when invoked with arguments args and keyword arguments kwargs, and
        the str(error) value matches the provided regexp. If a different type
        of exception is thrown, it will not be caught, and the test case will
        be deemed to have suffered an error, exactly as for an unexpected
        exception. It returns the exception instance if it matches the given
        exception class.

        This may also be used as a context manager when provided with a single
        argument, as such:

        with self.failUnlessRaisesRegexp(ExcClass, "something like.*happened"):
            logic_which_should_raise()
        """
        def match_regexp(error):
            error_str = str(error)
            if regexp is not None and not re.search(regexp, error_str):
                raise self.failureException("%r doesn't match %r" %
                                            (error_str, regexp))
        excName = self.__class_name(excClass)
        if args:
            callableObj = args[0]
            try:
                result = callableObj(*args[1:], **kwargs)
            except excClass as e:
                match_regexp(e)
                return e
            else:
                raise self.failureException("%s not raised (%r returned)" %
                                            (excName, result))
        else:
            test = self
            class AssertRaisesContextManager(object):
                def __enter__(self):
                    return self
                def __exit__(self, type, value, traceback):
                    self.exception = value
                    if value is None:
                        raise test.failureException("%s not raised" % excName)
                    elif isinstance(value, excClass):
                        match_regexp(value)
                        return True
            return AssertRaisesContextManager()

    def __class_name(self, cls):
        return getattr(cls, "__name__", str(cls))

    def failUnlessIsInstance(self, obj, cls, msg=None):
        """Assert that isinstance(obj, cls)."""
        if not isinstance(obj, cls):
            if msg is None:
                msg = "%r is not an instance of %s" % \
                      (obj, self.__class_name(cls))
            raise self.failureException(msg)

    def failIfIsInstance(self, obj, cls, msg=None):
        """Assert that isinstance(obj, cls) is False."""
        if isinstance(obj, cls):
            if msg is None:
                msg = "%r is an instance of %s" % \
                      (obj, self.__class_name(cls))
            raise self.failureException(msg)

    assertIs = failUnlessIs
    assertIsNot = failIfIs
    assertIn = failUnlessIn
    assertNotIn = failIfIn
    assertStartsWith = failUnlessStartsWith
    assertNotStartsWith = failIfStartsWith
    assertEndsWith = failUnlessEndsWith
    assertNotEndsWith = failIfEndsWith
    assertApproximates = failUnlessApproximates
    assertNotApproximates = failIfApproximates
    assertMethodsMatch = failUnlessMethodsMatch
    assertRaises = failUnlessRaises
    assertRaisesRegexp = failUnlessRaisesRegexp
    assertIsInstance = failUnlessIsInstance
    assertIsNotInstance = failIfIsInstance
    assertNotIsInstance = failIfIsInstance # Poor choice in 2.7/3.2+.

    # The following are missing in Python < 2.4.
    assertTrue = unittest.TestCase.failUnless
    assertFalse = unittest.TestCase.failIf

    # The following is provided for compatibility with Twisted's trial.
    assertIdentical = assertIs
    assertNotIdentical = assertIsNot
    failUnlessIdentical = failUnlessIs
    failIfIdentical = failIfIs


# --------------------------------------------------------------------
# Mocker.

class classinstancemethod(object):

    def __init__(self, method):
        self.method = method

    def __get__(self, obj, cls=None):
        def bound_method(*args, **kwargs):
            return self.method(cls, obj, *args, **kwargs)
        return bound_method


class MockerBase(object):
    """Controller of mock objects.

    A mocker instance is used to command recording and replay of
    expectations on any number of mock objects.

    Expectations should be expressed for the mock object while in
    record mode (the initial one) by using the mock object itself,
    and using the mocker (and/or C{expect()} as a helper) to define
    additional behavior for each event.  For instance::

        mock = mocker.mock()
        mock.hello()
        mocker.result("Hi!")
        mocker.replay()
        assert mock.hello() == "Hi!"
        mock.restore()
        mock.verify()

    In this short excerpt a mock object is being created, then an
    expectation of a call to the C{hello()} method was recorded, and
    when called the method should return the value C{10}.  Then, the
    mocker is put in replay mode, and the expectation is satisfied by
    calling the C{hello()} method, which indeed returns 10.  Finally,
    a call to the L{restore()} method is performed to undo any needed
    changes made in the environment, and the L{verify()} method is
    called to ensure that all defined expectations were met.

    The same logic can be expressed more elegantly using the
    C{with mocker:} statement, as follows::

        mock = mocker.mock()
        mock.hello()
        mocker.result("Hi!")
        with mocker:
            assert mock.hello() == "Hi!"

    Also, the MockerTestCase class, which integrates the mocker on
    a unittest.TestCase subclass, may be used to reduce the overhead
    of controlling the mocker.  A test could be written as follows::

        class SampleTest(MockerTestCase):

            def test_hello(self):
                mock = self.mocker.mock()
                mock.hello()
                self.mocker.result("Hi!")
                self.mocker.replay()
                self.assertEquals(mock.hello(), "Hi!")
    """

    _recorders = []

    # For convenience only.
    on = expect

    class __metaclass__(type):
        def __init__(self, name, bases, dict):
            # Make independent lists on each subclass, inheriting from parent.
            self._recorders = list(getattr(self, "_recorders", ()))

    def __init__(self):
        self._recorders = self._recorders[:]
        self._events = []
        self._recording = True
        self._ordering = False
        self._last_orderer = None

    def is_recording(self):
        """Return True if in recording mode, False if in replay mode.

        Recording is the initial state.
        """
        return self._recording

    def replay(self):
        """Change to replay mode, where recorded events are reproduced.

        If already in replay mode, the mocker will be restored, with all
        expectations reset, and then put again in replay mode.

        An alternative and more comfortable way to replay changes is
        using the 'with' statement, as follows::

            mocker = Mocker()
            <record events>
            with mocker:
                <reproduce events>

        The 'with' statement will automatically put mocker in replay
        mode, and will also verify if all events were correctly reproduced
        at the end (using L{verify()}), and also restore any changes done
        in the environment (with L{restore()}).

        Also check the MockerTestCase class, which integrates the
        unittest.TestCase class with mocker.
        """
        if not self._recording:
            for event in self._events:
                event.restore()
        else:
            self._recording = False
        for event in self._events:
            event.replay()

    def restore(self):
        """Restore changes in the environment, and return to recording mode.

        This should always be called after the test is complete (succeeding
        or not).  There are ways to call this method automatically on
        completion (e.g. using a C{with mocker:} statement, or using the
        L{MockerTestCase} class.
        """
        if not self._recording:
            self._recording = True
            for event in self._events:
                event.restore()

    def reset(self):
        """Reset the mocker state.

        This will restore environment changes, if currently in replay
        mode, and then remove all events previously recorded.
        """
        if not self._recording:
            self.restore()
        self.unorder()
        del self._events[:]

    def get_events(self):
        """Return all recorded events."""
        return self._events[:]

    def add_event(self, event):
        """Add an event.

        This method is used internally by the implementation, and
        shouldn't be needed on normal mocker usage.
        """
        self._events.append(event)
        if self._ordering:
            orderer = event.add_task(Orderer(event.path))
            if self._last_orderer:
                orderer.add_dependency(self._last_orderer)
            self._last_orderer = orderer
        return event

    def verify(self):
        """Check if all expectations were met, and raise AssertionError if not.

        The exception message will include a nice description of which
        expectations were not met, and why.
        """
        errors = []
        for event in self._events:
            try:
                event.verify()
            except AssertionError as e:
                error = str(e)
                if not error:
                    raise RuntimeError("Empty error message from %r"
                                       % event)
                errors.append(error)
        if errors:
            message = [ERROR_PREFIX + "Unmet expectations:", ""]
            for error in errors:
                lines = error.splitlines()
                message.append("=> " + lines.pop(0))
                message.extend([" " + line for line in lines])
                message.append("")
            raise AssertionError(os.linesep.join(message))

    def mock(self, spec_and_type=None, spec=None, type=None,
             name=None, count=True):
        """Return a new mock object.

        @param spec_and_type: Handy positional argument which sets both
                     spec and type.
        @param spec: Method calls will be checked for correctness against
                     the given class.
        @param type: If set, the Mock's __class__ attribute will return
                     the given type.  This will make C{isinstance()} calls
                     on the object work.
        @param name: Name for the mock object, used in the representation of
                     expressions.  The name is rarely needed, as it's usually
                     guessed correctly from the variable name used.
        @param count: If set to false, expressions may be executed any number
                     of times, unless an expectation is explicitly set using
                     the L{count()} method.  By default, expressions are
                     expected once.
        """
        if spec_and_type is not None:
            spec = type = spec_and_type
        return Mock(self, spec=spec, type=type, name=name, count=count)

    def proxy(self, object, spec=True, type=True, name=None, count=True,
              passthrough=True):
        """Return a new mock object which proxies to the given object.

        Proxies are useful when only part of the behavior of an object
        is to be mocked.  Unknown expressions may be passed through to
        the real implementation implicitly (if the C{passthrough} argument
        is True), or explicitly (using the L{passthrough()} method
        on the event).

        @param object: Real object to be proxied, and replaced by the mock
                       on replay mode.  It may also be an "import path",
                       such as C{"time.time"}, in which case the object
                       will be the C{time} function from the C{time} module.
        @param spec: Method calls will be checked for correctness against
                     the given object, which may be a class or an instance
                     where attributes will be looked up.  Defaults to the
                     the C{object} parameter.  May be set to None explicitly,
                     in which case spec checking is disabled.  Checks may
                     also be disabled explicitly on a per-event basis with
                     the L{nospec()} method.
        @param type: If set, the Mock's __class__ attribute will return
                     the given type.  This will make C{isinstance()} calls
                     on the object work.  Defaults to the type of the
                     C{object} parameter.  May be set to None explicitly.
        @param name: Name for the mock object, used in the representation of
                     expressions.  The name is rarely needed, as it's usually
                     guessed correctly from the variable name used.
        @param count: If set to false, expressions may be executed any number
                     of times, unless an expectation is explicitly set using
                     the L{count()} method.  By default, expressions are
                     expected once.
        @param passthrough: If set to False, passthrough of actions on the
                            proxy to the real object will only happen when
                            explicitly requested via the L{passthrough()}
                            method.
        """
        if isinstance(object, basestring):
            if name is None:
                name = object
            import_stack = object.split(".")
            attr_stack = []
            while import_stack:
                module_path = ".".join(import_stack)
                try:
                    __import__(module_path)
                except ImportError:
                    attr_stack.insert(0, import_stack.pop())
                    if not import_stack:
                        raise
                    continue
                else:
                    object = sys.modules[module_path]
                    for attr in attr_stack:
                        object = getattr(object, attr)
                    break
        if isinstance(object, types.UnboundMethodType):
            object = object.__func__
        if spec is True:
            spec = object
        if type is True:
            type = __builtin__.type(object)
        return Mock(self, spec=spec, type=type, object=object,
                    name=name, count=count, passthrough=passthrough)

    def replace(self, object, spec=True, type=True, name=None, count=True,
                passthrough=True):
        """Create a proxy, and replace the original object with the mock.

        On replay, the original object will be replaced by the returned
        proxy in all dictionaries found in the running interpreter via
        the garbage collecting system.  This should cover module
        namespaces, class namespaces, instance namespaces, and so on.

        @param object: Real object to be proxied, and replaced by the mock
                       on replay mode.  It may also be an "import path",
                       such as C{"time.time"}, in which case the object
                       will be the C{time} function from the C{time} module.
        @param spec: Method calls will be checked for correctness against
                     the given object, which may be a class or an instance
                     where attributes will be looked up.  Defaults to the
                     the C{object} parameter.  May be set to None explicitly,
                     in which case spec checking is disabled.  Checks may
                     also be disabled explicitly on a per-event basis with
                     the L{nospec()} method.
        @param type: If set, the Mock's __class__ attribute will return
                     the given type.  This will make C{isinstance()} calls
                     on the object work.  Defaults to the type of the
                     C{object} parameter.  May be set to None explicitly.
        @param name: Name for the mock object, used in the representation of
                     expressions.  The name is rarely needed, as it's usually
                     guessed correctly from the variable name used.
        @param passthrough: If set to False, passthrough of actions on the
                            proxy to the real object will only happen when
                            explicitly requested via the L{passthrough()}
                            method.
        """
        mock = self.proxy(object, spec, type, name, count, passthrough)
        event = self._get_replay_restore_event()
        event.add_task(ProxyReplacer(mock))
        return mock

    def patch(self, object, spec=True):
        """Patch an existing object to reproduce recorded events.

        @param object: Class or instance to be patched.
        @param spec: Method calls will be checked for correctness against
                     the given object, which may be a class or an instance
                     where attributes will be looked up.  Defaults to the
                     the C{object} parameter.  May be set to None explicitly,
                     in which case spec checking is disabled.  Checks may
                     also be disabled explicitly on a per-event basis with
                     the L{nospec()} method.

        The result of this method is still a mock object, which can be
        used like any other mock object to record events.  The difference
        is that when the mocker is put on replay mode, the *real* object
        will be modified to behave according to recorded expectations.

        Patching works in individual instances, and also in classes.
        When an instance is patched, recorded events will only be
        considered on this specific instance, and other instances should
        behave normally.  When a class is patched, the reproduction of
        events will be considered on any instance of this class once
        created (collectively).

        Observe that, unlike with proxies which catch only events done
        through the mock object, *all* accesses to recorded expectations
        will be considered;  even these coming from the object itself
        (e.g. C{self.hello()} is considered if this method was patched).
        While this is a very powerful feature, and many times the reason
        to use patches in the first place, it's important to keep this
        behavior in mind.

        Patching of the original object only takes place when the mocker
        is put on replay mode, and the patched object will be restored
        to its original state once the L{restore()} method is called
        (explicitly, or implicitly with alternative conventions, such as
        a C{with mocker:} block, or a MockerTestCase class).
        """
        if spec is True:
            spec = object
        patcher = Patcher()
        event = self._get_replay_restore_event()
        event.add_task(patcher)
        mock = Mock(self, object=object, patcher=patcher,
                    passthrough=True, spec=spec)
        patcher.patch_attr(object, '__mocker_mock__', mock)
        return mock

    def act(self, path):
        """This is called by mock objects whenever something happens to them.

        This method is part of the interface between the mocker
        and mock objects.
        """
        if self._recording:
            event = self.add_event(Event(path))
            for recorder in self._recorders:
                recorder(self, event)
            return Mock(self, path)
        else:
            # First run events that may run, then run unsatisfied events, then
            # ones not previously run. We put the index in the ordering tuple
            # instead of the actual event because we want a stable sort
            # (ordering between 2 events is undefined).
            events = self._events
            order = [(events[i].satisfied()*2 + events[i].has_run(), i)
                     for i in range(len(events))]
            order.sort()
            postponed = None
            for weight, i in order:
                event = events[i]
                if event.matches(path):
                    if event.may_run(path):
                        return event.run(path)
                    elif postponed is None:
                        postponed = event
            if postponed is not None:
                return postponed.run(path)
            raise MatchError(ERROR_PREFIX + "Unexpected expression: %s" % path)

    def get_recorders(cls, self):
        """Return recorders associated with this mocker class or instance.

        This method may be called on mocker instances and also on mocker
        classes.  See the L{add_recorder()} method for more information.
        """
        return (self or cls)._recorders[:]
    get_recorders = classinstancemethod(get_recorders)

    def add_recorder(cls, self, recorder):
        """Add a recorder to this mocker class or instance.

        @param recorder: Callable accepting C{(mocker, event)} as parameters.

        This is part of the implementation of mocker.

        All registered recorders are called for translating events that
        happen during recording into expectations to be met once the state
        is switched to replay mode.

        This method may be called on mocker instances and also on mocker
        classes.  When called on a class, the recorder will be used by
        all instances, and also inherited on subclassing.  When called on
        instances, the recorder is added only to the given instance.
        """
        (self or cls)._recorders.append(recorder)
        return recorder
    add_recorder = classinstancemethod(add_recorder)

    def remove_recorder(cls, self, recorder):
        """Remove the given recorder from this mocker class or instance.

        This method may be called on mocker classes and also on mocker
        instances.  See the L{add_recorder()} method for more information.
        """
        (self or cls)._recorders.remove(recorder)
    remove_recorder = classinstancemethod(remove_recorder)

    def result(self, value):
        """Make the last recorded event return the given value on replay.

        @param value: Object to be returned when the event is replayed.
        """
        self.call(lambda *args, **kwargs: value)

    def generate(self, sequence):
        """Last recorded event will return a generator with the given sequence.

        @param sequence: Sequence of values to be generated.
        """
        def generate(*args, **kwargs):
            for value in sequence:
                yield value
        self.call(generate)

    def throw(self, exception):
        """Make the last recorded event raise the given exception on replay.

        @param exception: Class or instance of exception to be raised.
        """
        def raise_exception(*args, **kwargs):
            raise exception
        self.call(raise_exception)

    def call(self, func, with_object=False):
        """Make the last recorded event cause the given function to be called.

        @param func: Function to be called.
        @param with_object: If True, the called function will receive the
            patched or proxied object so that its state may be used or verified
            in checks.

        The result of the function will be used as the event result.
        """
        event = self._events[-1]
        if with_object and event.path.root_object is None:
            raise TypeError("Mock object isn't a proxy")
        event.add_task(FunctionRunner(func, with_root_object=with_object))

    def count(self, min, max=False):
        """Last recorded event must be replayed between min and max times.

        @param min: Minimum number of times that the event must happen.
        @param max: Maximum number of times that the event must happen.  If
                    not given, it defaults to the same value of the C{min}
                    parameter.  If set to None, there is no upper limit, and
                    the expectation is met as long as it happens at least
                    C{min} times.
        """
        event = self._events[-1]
        for task in event.get_tasks():
            if isinstance(task, RunCounter):
                event.remove_task(task)
        event.prepend_task(RunCounter(min, max))

    def is_ordering(self):
        """Return true if all events are being ordered.

        See the L{order()} method.
        """
        return self._ordering

    def unorder(self):
        """Disable the ordered mode.

        See the L{order()} method for more information.
        """
        self._ordering = False
        self._last_orderer = None

    def order(self, *path_holders):
        """Create an expectation of order between two or more events.

        @param path_holders: Objects returned as the result of recorded events.

        By default, mocker won't force events to happen precisely in
        the order they were recorded.  Calling this method will change
        this behavior so that events will only match if reproduced in
        the correct order.

        There are two ways in which this method may be used.  Which one
        is used in a given occasion depends only on convenience.

        If no arguments are passed, the mocker will be put in a mode where
        all the recorded events following the method call will only be met
        if they happen in order.  When that's used, the mocker may be put
        back in unordered mode by calling the L{unorder()} method, or by
        using a 'with' block, like so::

            with mocker.ordered():
                <record events>

        In this case, only expressions in <record events> will be ordered,
        and the mocker will be back in unordered mode after the 'with' block.

        The second way to use it is by specifying precisely which events
        should be ordered.  As an example::

            mock = mocker.mock()
            expr1 = mock.hello()
            expr2 = mock.world
            expr3 = mock.x.y.z
            mocker.order(expr1, expr2, expr3)

        This method of ordering only works when the expression returns
        another object.

        Also check the L{after()} and L{before()} methods, which are
        alternative ways to perform this.
        """
        if not path_holders:
            self._ordering = True
            return OrderedContext(self)

        last_orderer = None
        for path_holder in path_holders:
            if type(path_holder) is Path:
                path = path_holder
            else:
                path = path_holder.__mocker_path__
            for event in self._events:
                if event.path is path:
                    for task in event.get_tasks():
                        if isinstance(task, Orderer):
                            orderer = task
                            break
                    else:
                        orderer = Orderer(path)
                        event.add_task(orderer)
                    if last_orderer:
                        orderer.add_dependency(last_orderer)
                    last_orderer = orderer
                    break

    def after(self, *path_holders):
        """Last recorded event must happen after events referred to.

        @param path_holders: Objects returned as the result of recorded events
                             which should happen before the last recorded event

        As an example, the idiom::

            expect(mock.x).after(mock.y, mock.z)

        is an alternative way to say::

            expr_x = mock.x
            expr_y = mock.y
            expr_z = mock.z
            mocker.order(expr_y, expr_x)
            mocker.order(expr_z, expr_x)

        See L{order()} for more information.
        """
        last_path = self._events[-1].path
        for path_holder in path_holders:
            self.order(path_holder, last_path)

    def before(self, *path_holders):
        """Last recorded event must happen before events referred to.

        @param path_holders: Objects returned as the result of recorded events
                             which should happen after the last recorded event

        As an example, the idiom::

            expect(mock.x).before(mock.y, mock.z)

        is an alternative way to say::

            expr_x = mock.x
            expr_y = mock.y
            expr_z = mock.z
            mocker.order(expr_x, expr_y)
            mocker.order(expr_x, expr_z)

        See L{order()} for more information.
        """
        last_path = self._events[-1].path
        for path_holder in path_holders:
            self.order(last_path, path_holder)

    def nospec(self):
        """Don't check method specification of real object on last event.

        By default, when using a mock created as the result of a call to
        L{proxy()}, L{replace()}, and C{patch()}, or when passing the spec
        attribute to the L{mock()} method, method calls on the given object
        are checked for correctness against the specification of the real
        object (or the explicitly provided spec).

        This method will disable that check specifically for the last
        recorded event.
        """
        event = self._events[-1]
        for task in event.get_tasks():
            if isinstance(task, SpecChecker):
                event.remove_task(task)

    def passthrough(self, result_callback=None):
        """Make the last recorded event run on the real object once seen.

        @param result_callback: If given, this function will be called with
            the result of the *real* method call as the only argument.

        This can only be used on proxies, as returned by the L{proxy()}
        and L{replace()} methods, or on mocks representing patched objects,
        as returned by the L{patch()} method.
        """
        event = self._events[-1]
        if event.path.root_object is None:
            raise TypeError("Mock object isn't a proxy")
        event.add_task(PathExecuter(result_callback))

    def __enter__(self):
        """Enter in a 'with' context.  This will run replay()."""
        self.replay()
        return self

    def __exit__(self, type, value, traceback):
        """Exit from a 'with' context.

        This will run restore() at all times, but will only run verify()
        if the 'with' block itself hasn't raised an exception.  Exceptions
        in that block are never swallowed.
        """
        self.restore()
        if type is None:
            self.verify()
        return False

    def _get_replay_restore_event(self):
        """Return unique L{ReplayRestoreEvent}, creating if needed.

        Some tasks only want to replay/restore.  When that's the case,
        they shouldn't act on other events during replay.  Also, they
        can all be put in a single event when that's the case.  Thus,
        we add a single L{ReplayRestoreEvent} as the first element of
        the list.
        """
        if not self._events or type(self._events[0]) != ReplayRestoreEvent:
            self._events.insert(0, ReplayRestoreEvent())
        return self._events[0]


class OrderedContext(object):

    def __init__(self, mocker):
        self._mocker = mocker

    def __enter__(self):
        return None

    def __exit__(self, type, value, traceback):
        self._mocker.unorder()


class Mocker(MockerBase):
    __doc__ = MockerBase.__doc__

# Decorator to add recorders on the standard Mocker class.
recorder = Mocker.add_recorder


# --------------------------------------------------------------------
# Mock object.

class Mock(object):

    def __init__(self, mocker, path=None, name=None, spec=None, type=None,
                 object=None, passthrough=False, patcher=None, count=True):
        self.__mocker__ = mocker
        self.__mocker_path__ = path or Path(self, object)
        self.__mocker_name__ = name
        self.__mocker_spec__ = spec
        self.__mocker_object__ = object
        self.__mocker_passthrough__ = passthrough
        self.__mocker_patcher__ = patcher
        self.__mocker_replace__ = False
        self.__mocker_type__ = type
        self.__mocker_count__ = count

    def __mocker_act__(self, kind, args=(), kwargs={}, object=None):
        if self.__mocker_name__ is None:
            self.__mocker_name__ = find_object_name(self, 2)
        action = Action(kind, args, kwargs, self.__mocker_path__)
        path = self.__mocker_path__ + action
        if object is not None:
            path.root_object = object
        try:
            return self.__mocker__.act(path)
        except MatchError as exception:
            root_mock = path.root_mock
            if (path.root_object is not None and
                root_mock.__mocker_passthrough__):
                return path.execute(path.root_object)
            # Reinstantiate to show raise statement on traceback, and
            # also to make the traceback shown shorter.
            raise MatchError(str(exception))
        except AssertionError as e:
            lines = str(e).splitlines()
            message = [ERROR_PREFIX + "Unmet expectation:", ""]
            message.append("=> " + lines.pop(0))
            message.extend([" " + line for line in lines])
            message.append("")
            raise AssertionError(os.linesep.join(message))

    def __getattribute__(self, name):
        if name.startswith("__mocker_"):
            return super(Mock, self).__getattribute__(name)
        if name == "__class__":
            if self.__mocker__.is_recording() or self.__mocker_type__ is None:
                return type(self)
            return self.__mocker_type__
        if name == "__length_hint__":
            # This is used by Python 2.6+ to optimize the allocation
            # of arrays in certain cases.  Pretend it doesn't exist.
            raise AttributeError("No __length_hint__ here!")
        return self.__mocker_act__("getattr", (name,))

    def __setattr__(self, name, value):
        if name.startswith("__mocker_"):
            return super(Mock, self).__setattr__(name, value)
        return self.__mocker_act__("setattr", (name, value))

    def __delattr__(self, name):
        return self.__mocker_act__("delattr", (name,))

    def __call__(self, *args, **kwargs):
        return self.__mocker_act__("call", args, kwargs)

    def __contains__(self, value):
        return self.__mocker_act__("contains", (value,))

    def __getitem__(self, key):
        return self.__mocker_act__("getitem", (key,))

    def __setitem__(self, key, value):
        return self.__mocker_act__("setitem", (key, value))

    def __delitem__(self, key):
        return self.__mocker_act__("delitem", (key,))

    def __len__(self):
        # MatchError is turned on an AttributeError so that list() and
        # friends act properly when trying to get length hints on
        # something that doesn't offer them.
        try:
            result = self.__mocker_act__("len")
        except MatchError as e:
            raise AttributeError(str(e))
        if type(result) is Mock:
            return 0
        return result

    def __nonzero__(self):
        try:
            result = self.__mocker_act__("nonzero")
        except MatchError as e:
            return True
        if type(result) is Mock:
            return True
        return result

    def __iter__(self):
        # XXX On py3k, when next() becomes __next__(), we'll be able
        #     to return the mock itself because it will be considered
        #     an iterator (we'll be mocking __next__ as well, which we
        #     can't now).
        result = self.__mocker_act__("iter")
        if type(result) is Mock:
            return iter([])
        return result

    # When adding a new action kind here, also add support for it on
    # Action.execute() and Path.__str__().


def find_object_name(obj, depth=0):
    """Try to detect how the object is named on a previous scope."""
    try:
        frame = sys._getframe(depth+1)
    except:
        return None
    for name, frame_obj in iteritems(frame.f_locals):
        if frame_obj is obj:
            return name
    self = frame.f_locals.get("self")
    if self is not None:
        try:
            items = list(self.__dict__.items())
        except:
            pass
        else:
            for name, self_obj in items:
                if self_obj is obj:
                    return name
    return None


# --------------------------------------------------------------------
# Action and path.

class Action(object):

    def __init__(self, kind, args, kwargs, path=None):
        self.kind = kind
        self.args = args
        self.kwargs = kwargs
        self.path = path
        self._execute_cache = {}

    def __repr__(self):
        if self.path is None:
            return "Action(%r, %r, %r)" % (self.kind, self.args, self.kwargs)
        return "Action(%r, %r, %r, %r)" % \
               (self.kind, self.args, self.kwargs, self.path)

    def __eq__(self, other):
        return (self.kind == other.kind and
                self.args == other.args and
                self.kwargs == other.kwargs)

    def __ne__(self, other):
        return not self.__eq__(other)

    def matches(self, other):
        return (self.kind == other.kind and
                match_params(self.args, self.kwargs, other.args, other.kwargs))

    def execute(self, object):
        # This caching scheme may fail if the object gets deallocated before
        # the action, as the id might get reused.  It's somewhat easy to fix
        # that with a weakref callback.  For our uses, though, the object
        # should never get deallocated before the action itself, so we'll
        # just keep it simple.
        if id(object) in self._execute_cache:
            return self._execute_cache[id(object)]
        execute = getattr(object, "__mocker_execute__", None)
        if execute is not None:
            result = execute(self, object)
        else:
            kind = self.kind
            if kind == "getattr":
                result = getattr(object, self.args[0])
            elif kind == "setattr":
                result = setattr(object, self.args[0], self.args[1])
            elif kind == "delattr":
                result = delattr(object, self.args[0])
            elif kind == "call":
                result = object(*self.args, **self.kwargs)
            elif kind == "contains":
                result = self.args[0] in object
            elif kind == "getitem":
                result = object[self.args[0]]
            elif kind == "setitem":
                result = object[self.args[0]] = self.args[1]
            elif kind == "delitem":
                del object[self.args[0]]
                result = None
            elif kind == "len":
                result = len(object)
            elif kind == "nonzero":
                result = bool(object)
            elif kind == "iter":
                result = iter(object)
            else:
                raise RuntimeError("Don't know how to execute %r kind." % kind)
        self._execute_cache[id(object)] = result
        return result


class Path(object):

    def __init__(self, root_mock, root_object=None, actions=()):
        self.root_mock = root_mock
        self.root_object = root_object
        self.actions = tuple(actions)
        self.__mocker_replace__ = False

    def parent_path(self):
        if not self.actions:
            return None
        return self.actions[-1].path
    parent_path = property(parent_path)

    def __add__(self, action):
        """Return a new path which includes the given action at the end."""
        return self.__class__(self.root_mock, self.root_object,
                              self.actions + (action,))

    def __eq__(self, other):
        """Verify if the two paths are equal.

        Two paths are equal if they refer to the same mock object, and
        have the actions with equal kind, args and kwargs.
        """
        if (self.root_mock is not other.root_mock or
            self.root_object is not other.root_object or
            len(self.actions) != len(other.actions)):
            return False
        for action, other_action in zip(self.actions, other.actions):
            if action != other_action:
                return False
        return True

    def matches(self, other):
        """Verify if the two paths are equivalent.

        Two paths are equal if they refer to the same mock object, and
        have the same actions performed on them.
        """
        if (self.root_mock is not other.root_mock or
            len(self.actions) != len(other.actions)):
            return False
        for action, other_action in zip(self.actions, other.actions):
            if not action.matches(other_action):
                return False
        return True

    def execute(self, object):
        """Execute all actions sequentially on object, and return result.
        """
        for action in self.actions:
            object = action.execute(object)
        return object

    def __str__(self):
        """Transform the path into a nice string such as obj.x.y('z')."""
        result = self.root_mock.__mocker_name__ or "<mock>"
        for action in self.actions:
            if action.kind == "getattr":
                result = "%s.%s" % (result, action.args[0])
            elif action.kind == "setattr":
                result = "%s.%s = %r" % (result, action.args[0], action.args[1])
            elif action.kind == "delattr":
                result = "del %s.%s" % (result, action.args[0])
            elif action.kind == "call":
                args = [repr(x) for x in action.args]
                items = list(action.kwargs.items())
                items.sort()
                for pair in items:
                    args.append("%s=%r" % pair)
                result = "%s(%s)" % (result, ", ".join(args))
            elif action.kind == "contains":
                result = "%r in %s" % (action.args[0], result)
            elif action.kind == "getitem":
                result = "%s[%r]" % (result, action.args[0])
            elif action.kind == "setitem":
                result = "%s[%r] = %r" % (result, action.args[0],
                                          action.args[1])
            elif action.kind == "delitem":
                result = "del %s[%r]" % (result, action.args[0])
            elif action.kind == "len":
                result = "len(%s)" % result
            elif action.kind == "nonzero":
                result = "bool(%s)" % result
            elif action.kind == "iter":
                result = "iter(%s)" % result
            else:
                raise RuntimeError("Don't know how to format kind %r" %
                                   action.kind)
        return result


class SpecialArgument(object):
    """Base for special arguments for matching parameters."""

    def __init__(self, object=None):
        self.object = object

    def __repr__(self):
        if self.object is None:
            return self.__class__.__name__
        else:
            return "%s(%r)" % (self.__class__.__name__, self.object)

    def matches(self, other):
        return True

    def __eq__(self, other):
        return type(other) == type(self) and self.object == other.object


class ANY(SpecialArgument):
    """Matches any single argument."""

ANY = ANY()


class ARGS(SpecialArgument):
    """Matches zero or more positional arguments."""

ARGS = ARGS()


class KWARGS(SpecialArgument):
    """Matches zero or more keyword arguments."""

KWARGS = KWARGS()


class IS(SpecialArgument):

    def matches(self, other):
        return self.object is other

    def __eq__(self, other):
        return type(other) == type(self) and self.object is other.object


class CONTAINS(SpecialArgument):

    def matches(self, other):
        try:
            other.__contains__
        except AttributeError:
            try:
                iter(other)
            except TypeError:
                # If an object can't be iterated, and has no __contains__
                # hook, it'd blow up on the test below.  We test this in
                # advance to prevent catching more errors than we really
                # want.
                return False
        return self.object in other


class IN(SpecialArgument):

    def matches(self, other):
        return other in self.object


class MATCH(SpecialArgument):

    def matches(self, other):
        return bool(self.object(other))

    def __eq__(self, other):
        return type(other) == type(self) and self.object is other.object


def match_params(args1, kwargs1, args2, kwargs2):
    """Match the two sets of parameters, considering special parameters."""

    has_args = ARGS in args1
    has_kwargs = KWARGS in args1

    if has_kwargs:
        args1 = [arg1 for arg1 in args1 if arg1 is not KWARGS]
    elif len(kwargs1) != len(kwargs2):
        return False

    if not has_args and len(args1) != len(args2):
        return False

    # Either we have the same number of kwargs, or unknown keywords are
    # accepted (KWARGS was used), so check just the ones in kwargs1.
    for key, arg1 in iteritems(kwargs1):
        if key not in kwargs2:
            return False
        arg2 = kwargs2[key]
        if isinstance(arg1, SpecialArgument):
            if not arg1.matches(arg2):
                return False
        elif arg1 != arg2:
            return False

    # Keywords match.  Now either we have the same number of
    # arguments, or ARGS was used.  If ARGS wasn't used, arguments
    # must match one-on-one necessarily.
    if not has_args:
        for arg1, arg2 in zip(args1, args2):
            if isinstance(arg1, SpecialArgument):
                if not arg1.matches(arg2):
                    return False
            elif arg1 != arg2:
                return False
        return True

    # Easy choice. Keywords are matching, and anything on args is accepted.
    if (ARGS,) == args1:
        return True

    # We have something different there. If we don't have positional
    # arguments on the original call, it can't match.
    if not args2:
        # Unless we have just several ARGS (which is bizarre, but..).
        for arg1 in args1:
            if arg1 is not ARGS:
                return False
        return True

    # Ok, all bets are lost.  We have to actually do the more expensive
    # matching.  This is an algorithm based on the idea of the Levenshtein
    # Distance between two strings, but heavily hacked for this purpose.
    args2l = len(args2)
    if args1[0] is ARGS:
        args1 = args1[1:]
        array = [0]*args2l
    else:
        array = [1]*args2l
    for i in range(len(args1)):
        last = array[0]
        if args1[i] is ARGS:
            for j in range(1, args2l):
                last, array[j] = array[j], min(array[j-1], array[j], last)
        else:
            array[0] = i or int(args1[i] != args2[0])
            for j in range(1, args2l):
                last, array[j] = array[j], last or int(args1[i] != args2[j])
        if 0 not in array:
            return False
    if array[-1] != 0:
        return False
    return True


# --------------------------------------------------------------------
# Event and task base.

class Event(object):
    """Aggregation of tasks that keep track of a recorded action.

    An event represents something that may or may not happen while the
    mocked environment is running, such as an attribute access, or a
    method call.  The event is composed of several tasks that are
    orchestrated together to create a composed meaning for the event,
    including for which actions it should be run, what happens when it
    runs, and what's the expectations about the actions run.
    """

    def __init__(self, path=None):
        self.path = path
        self._tasks = []
        self._has_run = False

    def add_task(self, task):
        """Add a new task to this task."""
        self._tasks.append(task)
        return task

    def prepend_task(self, task):
        """Add a task at the front of the list."""
        self._tasks.insert(0, task)
        return task

    def remove_task(self, task):
        self._tasks.remove(task)

    def replace_task(self, old_task, new_task):
        """Replace old_task with new_task, in the same position."""
        for i in range(len(self._tasks)):
            if self._tasks[i] is old_task:
                self._tasks[i] = new_task
        return new_task

    def get_tasks(self):
        return self._tasks[:]

    def matches(self, path):
        """Return true if *all* tasks match the given path."""
        for task in self._tasks:
            if not task.matches(path):
                return False
        return bool(self._tasks)

    def has_run(self):
        return self._has_run

    def may_run(self, path):
        """Verify if any task would certainly raise an error if run.

        This will call the C{may_run()} method on each task and return
        false if any of them returns false.
        """
        for task in self._tasks:
            if not task.may_run(path):
                return False
        return True

    def run(self, path):
        """Run all tasks with the given action.

        @param path: The path of the expression run.

        Running an event means running all of its tasks individually and in
        order.  An event should only ever be run if all of its tasks claim to
        match the given action.

        The result of this method will be the last result of a task
        which isn't None, or None if they're all None.
        """
        self._has_run = True
        result = None
        errors = []
        for task in self._tasks:
            if not errors or not task.may_run_user_code():
                try:
                    task_result = task.run(path)
                except AssertionError as e:
                    error = str(e)
                    if not error:
                        raise RuntimeError("Empty error message from %r" % task)
                    errors.append(error)
                else:
                    # XXX That's actually a bit weird.  What if a call() really
                    # returned None?  This would improperly change the semantic
                    # of this process without any good reason. Test that with two
                    # call()s in sequence.
                    if task_result is not None:
                        result = task_result
        if errors:
            message = [str(self.path)]
            if str(path) != message[0]:
                message.append("- Run: %s" % path)
            for error in errors:
                lines = error.splitlines()
                message.append("- " + lines.pop(0))
                message.extend(["  " + line for line in lines])
            raise AssertionError(os.linesep.join(message))
        return result

    def satisfied(self):
        """Return true if all tasks are satisfied.

        Being satisfied means that there are no unmet expectations.
        """
        for task in self._tasks:
            try:
                task.verify()
            except AssertionError:
                return False
        return True

    def verify(self):
        """Run verify on all tasks.

        The verify method is supposed to raise an AssertionError if the
        task has unmet expectations, with a one-line explanation about
        why this item is unmet.  This method should be safe to be called
        multiple times without side effects.
        """
        errors = []
        for task in self._tasks:
            try:
                task.verify()
            except AssertionError as e:
                error = str(e)
                if not error:
                    raise RuntimeError("Empty error message from %r" % task)
                errors.append(error)
        if errors:
            message = [str(self.path)]
            for error in errors:
                lines = error.splitlines()
                message.append("- " + lines.pop(0))
                message.extend(["  " + line for line in lines])
            raise AssertionError(os.linesep.join(message))

    def replay(self):
        """Put all tasks in replay mode."""
        self._has_run = False
        for task in self._tasks:
            task.replay()

    def restore(self):
        """Restore the state of all tasks."""
        for task in self._tasks:
            task.restore()


class ReplayRestoreEvent(Event):
    """Helper event for tasks which need replay/restore but shouldn't match."""

    def matches(self, path):
        return False


class Task(object):
    """Element used to track one specific aspect on an event.

    A task is responsible for adding any kind of logic to an event.
    Examples of that are counting the number of times the event was
    made, verifying parameters if any, and so on.
    """

    def matches(self, path):
        """Return true if the task is supposed to be run for the given path.
        """
        return True

    def may_run(self, path):
        """Return false if running this task would certainly raise an error."""
        return True

    def may_run_user_code(self):
        """Return true if there's a chance this task may run custom code.

        Whenever errors are detected, running user code should be avoided,
        because the situation is already known to be incorrect, and any
        errors in the user code are side effects rather than the cause.
        """
        return False

    def run(self, path):
        """Perform the task item, considering that the given action happened.
        """

    def verify(self):
        """Raise AssertionError if expectations for this item are unmet.

        The verify method is supposed to raise an AssertionError if the
        task has unmet expectations, with a one-line explanation about
        why this item is unmet.  This method should be safe to be called
        multiple times without side effects.
        """

    def replay(self):
        """Put the task in replay mode.

        Any expectations of the task should be reset.
        """

    def restore(self):
        """Restore any environmental changes made by the task.

        Verify should continue to work after this is called.
        """


# --------------------------------------------------------------------
# Task implementations.

class OnRestoreCaller(Task):
    """Call a given callback when restoring."""

    def __init__(self, callback):
        self._callback = callback

    def restore(self):
        self._callback()


class PathMatcher(Task):
    """Match the action path against a given path."""

    def __init__(self, path):
        self.path = path

    def matches(self, path):
        return self.path.matches(path)

def path_matcher_recorder(mocker, event):
    event.add_task(PathMatcher(event.path))

Mocker.add_recorder(path_matcher_recorder)


class RunCounter(Task):
    """Task which verifies if the number of runs are within given boundaries.
    """

    def __init__(self, min, max=False):
        self.min = min
        if max is None:
            self.max = sys.maxint
        elif max is False:
            self.max = min
        else:
            self.max = max
        self._runs = 0

    def replay(self):
        self._runs = 0

    def may_run(self, path):
        return self._runs < self.max

    def run(self, path):
        self._runs += 1
        if self._runs > self.max:
            self.verify()

    def verify(self):
        if not self.min <= self._runs <= self.max:
            if self._runs < self.min:
                raise AssertionError("Performed fewer times than expected.")
            raise AssertionError("Performed more times than expected.")


class ImplicitRunCounter(RunCounter):
    """RunCounter inserted by default on any event.

    This is a way to differentiate explicitly added counters and
    implicit ones.
    """

def run_counter_recorder(mocker, event):
    """Any event may be repeated once, unless disabled by default."""
    if event.path.root_mock.__mocker_count__:
        # Rather than appending the task, we prepend it so that the
        # issue is raised before any other side-effects happen.
        event.prepend_task(ImplicitRunCounter(1))

Mocker.add_recorder(run_counter_recorder)

def run_counter_removal_recorder(mocker, event):
    """
    Events created by getattr actions which lead to other events
    may be repeated any number of times. For that, we remove implicit
    run counters of any getattr actions leading to the current one.
    """
    parent_path = event.path.parent_path
    for event in mocker.get_events()[::-1]:
        if (event.path is parent_path and
            event.path.actions[-1].kind == "getattr"):
            for task in event.get_tasks():
                if type(task) is ImplicitRunCounter:
                    event.remove_task(task)

Mocker.add_recorder(run_counter_removal_recorder)


class MockReturner(Task):
    """Return a mock based on the action path."""

    def __init__(self, mocker):
        self.mocker = mocker

    def run(self, path):
        return Mock(self.mocker, path)

def mock_returner_recorder(mocker, event):
    """Events that lead to other events must return mock objects."""
    parent_path = event.path.parent_path
    for event in mocker.get_events():
        if event.path is parent_path:
            for task in event.get_tasks():
                if isinstance(task, MockReturner):
                    break
            else:
                event.add_task(MockReturner(mocker))
            break

Mocker.add_recorder(mock_returner_recorder)


class FunctionRunner(Task):
    """Task that runs a function everything it's run.

    Arguments of the last action in the path are passed to the function,
    and the function result is also returned.
    """

    def __init__(self, func, with_root_object=False):
        self._func = func
        self._with_root_object = with_root_object

    def may_run_user_code(self):
        return True

    def run(self, path):
        action = path.actions[-1]
        if self._with_root_object:
            return self._func(path.root_object, *action.args, **action.kwargs)
        else:
            return self._func(*action.args, **action.kwargs)


class PathExecuter(Task):
    """Task that executes a path in the real object, and returns the result."""

    def __init__(self, result_callback=None):
        self._result_callback = result_callback

    def get_result_callback(self):
        return self._result_callback

    def run(self, path):
        result = path.execute(path.root_object)
        if self._result_callback is not None:
            self._result_callback(result)
        return result


class Orderer(Task):
    """Task to establish an order relation between two events.

    An orderer task will only match once all its dependencies have
    been run.
    """

    def __init__(self, path):
        self.path = path
        self._run = False
        self._dependencies = []

    def replay(self):
        self._run = False

    def has_run(self):
        return self._run

    def may_run(self, path):
        for dependency in self._dependencies:
            if not dependency.has_run():
                return False
        return True

    def run(self, path):
        for dependency in self._dependencies:
            if not dependency.has_run():
                raise AssertionError("Should be after: %s" % dependency.path)
        self._run = True

    def add_dependency(self, orderer):
        self._dependencies.append(orderer)

    def get_dependencies(self):
        return self._dependencies


class SpecChecker(Task):
    """Task to check if arguments of the last action conform to a real method.
    """

    def __init__(self, method):
        self._method = method
        self._unsupported = False

        if method:
            try:
                self._args, self._varargs, self._varkwargs, self._defaults = \
                    inspect.getargspec(method)
            except TypeError:
                self._unsupported = True
            else:
                if self._defaults is None:
                    self._defaults = ()
                if type(method) is type(self.run):
                    self._args = self._args[1:]

    def get_method(self):
        return self._method

    def _raise(self, message):
        spec = inspect.formatargspec(self._args, self._varargs,
                                     self._varkwargs, self._defaults)
        raise AssertionError("Specification is %s%s: %s" %
                             (self._method.__name__, spec, message))

    def verify(self):
        if not self._method:
            raise AssertionError("Method not found in real specification")

    def may_run(self, path):
        try:
            self.run(path)
        except AssertionError:
            return False
        return True

    def run(self, path):
        if not self._method:
            raise AssertionError("Method not found in real specification")
        if self._unsupported:
            return # Can't check it. Happens with builtin functions. :-(
        action = path.actions[-1]
        obtained_len = len(action.args)
        obtained_kwargs = action.kwargs.copy()
        nodefaults_len = len(self._args) - len(self._defaults)
        for i, name in enumerate(self._args):
            if i < obtained_len and name in action.kwargs:
                self._raise("%r provided twice" % name)
            if (i >= obtained_len and i < nodefaults_len and
                name not in action.kwargs):
                self._raise("%r not provided" % name)
            obtained_kwargs.pop(name, None)
        if obtained_len > len(self._args) and not self._varargs:
            self._raise("too many args provided")
        if obtained_kwargs and not self._varkwargs:
            self._raise("unknown kwargs: %s" % ", ".join(obtained_kwargs))

def spec_checker_recorder(mocker, event):
    spec = event.path.root_mock.__mocker_spec__
    if spec:
        actions = event.path.actions
        if len(actions) == 1:
            if actions[0].kind == "call":
                method = getattr(spec, "__call__", None)
                event.add_task(SpecChecker(method))
        elif len(actions) == 2:
            if actions[0].kind == "getattr" and actions[1].kind == "call":
                method = getattr(spec, actions[0].args[0], None)
                event.add_task(SpecChecker(method))

Mocker.add_recorder(spec_checker_recorder)


class ProxyReplacer(Task):
    """Task which installs and deinstalls proxy mocks.

    This task will replace a real object by a mock in all dictionaries
    found in the running interpreter via the garbage collecting system.
    """

    def __init__(self, mock):
        self.mock = mock
        self.__mocker_replace__ = False

    def replay(self):
        global_replace(self.mock.__mocker_object__, self.mock)

    def restore(self):
        global_replace(self.mock, self.mock.__mocker_object__)


def global_replace(remove, install):
    """Replace object 'remove' with object 'install' on all dictionaries."""
    for referrer in gc.get_referrers(remove):
        if (type(referrer) is dict and
            referrer.get("__mocker_replace__", True)):
            for key, value in list(referrer.items()):
                if value is remove:
                    referrer[key] = install


class Undefined(object):

    def __repr__(self):
        return "Undefined"

Undefined = Undefined()


class Patcher(Task):

    def __init__(self):
        super(Patcher, self).__init__()
        self._monitored = {} # {kind: {id(object): object}}
        self._patched = {}

    def is_monitoring(self, obj, kind):
        monitored = self._monitored.get(kind)
        if monitored:
            if id(obj) in monitored:
                return True
            cls = type(obj)
            if issubclass(cls, type):
                cls = obj
            bases = set([id(base) for base in cls.__mro__])
            bases.intersection_update(monitored)
            return bool(bases)
        return False

    def monitor(self, obj, kind):
        if kind not in self._monitored:
            self._monitored[kind] = {}
        self._monitored[kind][id(obj)] = obj

    def patch_attr(self, obj, attr, value):
        original = obj.__dict__.get(attr, Undefined)
        self._patched[id(obj), attr] = obj, attr, original
        setattr(obj, attr, value)

    def get_unpatched_attr(self, obj, attr):
        cls = type(obj)
        if issubclass(cls, type):
            cls = obj
        result = Undefined
        for mro_cls in cls.__mro__:
            key = (id(mro_cls), attr)
            if key in self._patched:
                result = self._patched[key][2]
                if result is not Undefined:
                    break
            elif attr in mro_cls.__dict__:
                result = mro_cls.__dict__.get(attr, Undefined)
                break
        if isinstance(result, object) and hasattr(type(result), "__get__"):
            if cls is obj:
                obj = None
            return result.__get__(obj, cls)
        return result

    def _get_kind_attr(self, kind):
        if kind == "getattr":
            return "__getattribute__"
        return "__%s__" % kind

    def replay(self):
        for kind in self._monitored:
            attr = self._get_kind_attr(kind)
            seen = set()
            for obj in self._monitored[kind].itervalues():
                cls = type(obj)
                if issubclass(cls, type):
                    cls = obj
                if cls not in seen:
                    seen.add(cls)
                    unpatched = getattr(cls, attr, Undefined)
                    self.patch_attr(cls, attr,
                                    PatchedMethod(kind, unpatched,
                                                  self.is_monitoring))
                    self.patch_attr(cls, "__mocker_execute__",
                                    self.execute)

    def restore(self):
        for obj, attr, original in self._patched.itervalues():
            if original is Undefined:
                delattr(obj, attr)
            else:
                setattr(obj, attr, original)
        self._patched.clear()

    def execute(self, action, object):
        attr = self._get_kind_attr(action.kind)
        unpatched = self.get_unpatched_attr(object, attr)
        try:
            return unpatched(*action.args, **action.kwargs)
        except AttributeError:
            type, value, traceback = sys.exc_info()
            if action.kind == "getattr":
                # The normal behavior of Python is to try __getattribute__,
                # and if it raises AttributeError, try __getattr__.   We've
                # tried the unpatched __getattribute__ above, and we'll now
                # try __getattr__.
                try:
                    __getattr__ = unpatched("__getattr__")
                except AttributeError:
                    pass
                else:
                    return __getattr__(*action.args, **action.kwargs)
            raise (type, value, traceback)


class PatchedMethod(object):

    def __init__(self, kind, unpatched, is_monitoring):
        self._kind = kind
        self._unpatched = unpatched
        self._is_monitoring = is_monitoring

    def __get__(self, obj, cls=None):
        object = obj or cls
        if not self._is_monitoring(object, self._kind):
            return self._unpatched.__get__(obj, cls)
        def method(*args, **kwargs):
            if self._kind == "getattr" and args[0].startswith("__mocker_"):
                return self._unpatched.__get__(obj, cls)(args[0])
            mock = object.__mocker_mock__
            return mock.__mocker_act__(self._kind, args, kwargs, object)
        return method

    def __call__(self, obj, *args, **kwargs):
        # At least with __getattribute__, Python seems to use *both* the
        # descriptor API and also call the class attribute directly.  It
        # looks like an interpreter bug, or at least an undocumented
        # inconsistency.  Coverage tests may show this uncovered, because
        # it depends on the Python version.
        return self.__get__(obj)(*args, **kwargs)


def patcher_recorder(mocker, event):
    mock = event.path.root_mock
    if mock.__mocker_patcher__ and len(event.path.actions) == 1:
        patcher = mock.__mocker_patcher__
        patcher.monitor(mock.__mocker_object__, event.path.actions[0].kind)

Mocker.add_recorder(patcher_recorder)
