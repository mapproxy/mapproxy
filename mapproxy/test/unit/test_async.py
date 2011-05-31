# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

from __future__ import with_statement

import time
import threading
from mapproxy.util.async import imap_async_threaded, ThreadPool

from nose.tools import eq_
from nose.plugins.skip import SkipTest

class TestThreaded(object):
    def test_map(self):
        def func(x):
            time.sleep(0.05)
            return x
        start = time.time()
        result = list(imap_async_threaded(func, range(40)))
        stop = time.time()
        
        duration = stop - start
        assert duration < 0.2
        
        eq_(len(result), 40)
    
    def test_map_with_exception(self):
        def func(x):
            raise Exception()

        try:
            list(imap_async_threaded(func, range(40)))
        except Exception:
            pass
        else:
            assert False, 'exception expected'

try:
    import eventlet
    from mapproxy.util.async import imap_async_eventlet, EventletPool
    _has_eventlet = True
except ImportError:
    _has_eventlet = False

class TestEventlet(object):
    def setup(self):
        if not _has_eventlet:
            raise SkipTest('eventlet required')
    
    def test_map(self):
        def func(x):
            eventlet.sleep(0.05)
            return x
        start = time.time()
        result = list(imap_async_eventlet(func, range(40)))
        stop = time.time()
        
        duration = stop - start
        assert duration < 0.1
        
        eq_(len(result), 40)
    
    def test_map_with_exception(self):
        def func(x):
            raise Exception()

        try:
            list(imap_async_eventlet(func, range(40)))
        except Exception:
            pass
        else:
            assert False, 'exception expected'



class CommonPoolTests(object):
    def _check_single_arg(self, func):
        result = list(func())
        eq_(result, [3])
    
    def test_single_argument(self):
        f1 = lambda x, y: x+y
        pool = self.mk_pool()
        check = self._check_single_arg
        yield check, lambda: pool.map(f1, [1], [2])
        yield check, lambda: pool.imap(f1, [1], [2])
        yield check, lambda: pool.starmap(f1, [(1, 2)])
        yield check, lambda: pool.starcall([(f1, 1, 2)])
    
    
    def _check_single_arg_raise(self, func):
        try:
            list(func())
        except ValueError:
            pass
        else:
            assert False, 'expected ValueError'
    
    def test_single_argument_raise(self):
        def f1(x, y):
            raise ValueError
        pool = self.mk_pool()
        check = self._check_single_arg_raise
        yield check, lambda: pool.map(f1, [1], [2])
        yield check, lambda: pool.imap(f1, [1], [2])
        yield check, lambda: pool.starmap(f1, [(1, 2)])
        yield check, lambda: pool.starcall([(f1, 1, 2)])

    def _check_single_arg_result_object(self, func):
        result = list(func())
        assert result[0].result == None
        assert isinstance(result[0].exception[1], ValueError)
        
    def test_single_argument_result_object(self):
        def f1(x, y):
            raise ValueError
        pool = self.mk_pool()
        check = self._check_single_arg_result_object
        yield check, lambda: pool.map(f1, [1], [2], use_result_objects=True)
        yield check, lambda: pool.imap(f1, [1], [2], use_result_objects=True)
        yield check, lambda: pool.starmap(f1, [(1, 2)], use_result_objects=True)
        yield check, lambda: pool.starcall([(f1, 1, 2)], use_result_objects=True)


    def _check_multiple_args(self, func):
        result = list(func())
        eq_(result, [3, 5])
    
    def test_multiple_arguments(self):
        f1 = lambda x, y: x+y
        pool = self.mk_pool()
        check = self._check_multiple_args
        yield check, lambda: pool.map(f1, [1, 2], [2, 3])
        yield check, lambda: pool.imap(f1, [1, 2], [2, 3])
        yield check, lambda: pool.starmap(f1, [(1, 2), (2, 3)])
        yield check, lambda: pool.starcall([(f1, 1, 2), (f1, 2, 3)])
    
    def _check_multiple_args_with_exceptions_result_object(self, func):
        result = list(func())
        eq_(result[0].result, 3)
        eq_(type(result[1].exception[1]), ValueError)
        eq_(result[2].result, 7)
    
    def test_multiple_arguments_exceptions_result_object(self):
        def f1(x, y):
            if x+y == 5:
                raise ValueError()
            return x+y
        pool = self.mk_pool()
        check = self._check_multiple_args_with_exceptions_result_object
        yield check, lambda: pool.map(f1, [1, 2, 3], [2, 3, 4], use_result_objects=True)
        yield check, lambda: pool.imap(f1, [1, 2, 3], [2, 3, 4], use_result_objects=True)
        yield check, lambda: pool.starmap(f1, [(1, 2), (2, 3), (3, 4)], use_result_objects=True)
        yield check, lambda: pool.starcall([(f1, 1, 2), (f1, 2, 3), (f1, 3, 4)], use_result_objects=True)
    
    def _check_multiple_args_with_exceptions(self, func):
        result = func()
        try:
            # first result might aleady raise the exception when
            # when second result is returned faster by the ThreadPoolWorker
            eq_(result.next(), 3)
            result.next()
        except ValueError:
            pass
        else:
            assert False, 'expected ValueError'
    
    def test_multiple_arguments_exceptions(self):
        def f1(x, y):
            if x+y == 5:
                raise ValueError()
            return x+y
        pool = self.mk_pool()
        check = self._check_multiple_args_with_exceptions
        
        def check_pool_map():
            try:
                pool.map(f1, [1, 2, 3], [2, 3, 4])
            except ValueError:
                pass
            else:
                assert False, 'expected ValueError'
        yield check_pool_map
        yield check, lambda: pool.imap(f1, [1, 2, 3], [2, 3, 4])
        yield check, lambda: pool.starmap(f1, [(1, 2), (2, 3), (3, 4)])
        yield check, lambda: pool.starcall([(f1, 1, 2), (f1, 2, 3), (f1, 3, 4)])
    


class TestThreadPool(CommonPoolTests):
    def mk_pool(self):
        return ThreadPool()
    
    def test_base_config(self):
        # test that all concurrent have access to their
        # local base_config
        from mapproxy.config import base_config
        from mapproxy.util import local_base_config
        from copy import deepcopy

        # make two separate base_configs
        conf1 = deepcopy(base_config())
        conf1.conf = 1
        conf2 = deepcopy(base_config())
        conf2.conf = 2
        base_config().bar = 'baz'

        # run test in parallel, check1 and check2 should interleave
        # each with their local conf
        
        error_occured = False
        
        def check1(x):
            global error_occured
            if base_config().conf != 1 or 'bar' in base_config():
                error_occured = True

        def check2(x):
            global error_occured
            if base_config().conf != 2 or 'bar' in base_config():
                error_occured = True

        assert 'bar' in base_config()

        def test1():
            with local_base_config(conf1):
                pool1 = ThreadPool(5)
                list(pool1.imap(check1, range(200)))

        def test2():
            with local_base_config(conf2):
                pool2 = ThreadPool(5)
                list(pool2.imap(check2, range(200)))

        t1 = threading.Thread(target=test1)
        t2 = threading.Thread(target=test2)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert not error_occured
        assert 'bar' in base_config()


class TestEventletPool(CommonPoolTests):
    def setup(self):
        if not _has_eventlet:
            raise SkipTest('eventlet required')
    
    def mk_pool(self):
        if not _has_eventlet:
            raise SkipTest('eventlet required')
        return EventletPool()
    
    def test_base_config(self):
        # test that all concurrent have access to their
        # local base_config
        from mapproxy.config import base_config
        from mapproxy.util import local_base_config
        from copy import deepcopy

        # make two separate base_configs
        conf1 = deepcopy(base_config())
        conf1.conf = 1
        conf2 = deepcopy(base_config())
        conf2.conf = 2
        base_config().bar = 'baz'

        # run test in parallel, check1 and check2 should interleave
        # each with their local conf

        error_occured = False
        
        def check1(x):
            global error_occured
            if base_config().conf != 1 or 'bar' in base_config():
                error_occured = True

        def check2(x):
            global error_occured
            if base_config().conf != 2 or 'bar' in base_config():
                error_occured = True
                
        assert 'bar' in base_config()

        def test1():
            with local_base_config(conf1):
                pool1 = EventletPool(5)
                list(pool1.imap(check1, range(200)))

        def test2():
            with local_base_config(conf2):
                pool2 = EventletPool(5)
                list(pool2.imap(check2, range(200)))

        t1 = eventlet.spawn(test1)
        t2 = eventlet.spawn(test2)
        t1.wait()
        t2.wait()
        assert not error_occured
        assert 'bar' in base_config()


class DummyException(Exception):
    pass

class TestThreadedExecutorException(object):
    def setup(self):
        self.lock = threading.Lock()
        self.exec_count = 0
        self.te = ThreadPool(size=2)
    def execute(self, x):
        time.sleep(0.005)
        with self.lock:
            self.exec_count += 1
            if self.exec_count == 7:
                raise DummyException()
        return x
    def test_execute_w_exception(self):
        try:
            self.te.map(self.execute, range(100))
        except DummyException:
            print self.exec_count
            assert 7 <= self.exec_count <= 10, 'execution should be interrupted really '\
                                               'soon (exec_count should be 7+(max(3)))'
        else:
            assert False, 'expected DummyException'

