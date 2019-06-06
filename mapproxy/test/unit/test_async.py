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

from __future__ import print_function

import time
import threading

import pytest

from mapproxy.util.async_ import imap, ThreadPool


class TestThreaded(object):
    def test_map(self):
        def func(x):
            time.sleep(0.05)
            return x
        start = time.time()
        result = list(imap(func, list(range(40))))
        stop = time.time()

        duration = stop - start
        assert duration < 0.5, "took %s" % duration

        assert len(result) == 40

    def test_map_with_exception(self):
        def func(x):
            raise Exception()

        try:
            list(imap(func, list(range(40))))
        except Exception:
            pass
        else:
            assert False, 'exception expected'


class CommonPoolTests(object):
    def _check_single_arg(self, func):
        result = list(func())
        assert result == [3]

    def test_single_argument(self):
        f1 = lambda x, y: x+y
        pool = self.mk_pool()
        check = self._check_single_arg
        check(lambda: pool.map(f1, [1], [2]))
        check(lambda: pool.imap(f1, [1], [2]))
        check(lambda: pool.starmap(f1, [(1, 2)]))
        check(lambda: pool.starcall([(f1, 1, 2)]))


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
        check(lambda: pool.map(f1, [1], [2]))
        check(lambda: pool.imap(f1, [1], [2]))
        check(lambda: pool.starmap(f1, [(1, 2)]))
        check(lambda: pool.starcall([(f1, 1, 2)]))

    def _check_single_arg_result_object(self, func):
        result = list(func())
        assert result[0].result == None
        assert isinstance(result[0].exception[1], ValueError)

    def test_single_argument_result_object(self):
        def f1(x, y):
            raise ValueError
        pool = self.mk_pool()
        check = self._check_single_arg_result_object
        check(lambda: pool.map(f1, [1], [2], use_result_objects=True))
        check(lambda: pool.imap(f1, [1], [2], use_result_objects=True))
        check(lambda: pool.starmap(f1, [(1, 2)], use_result_objects=True))
        check(lambda: pool.starcall([(f1, 1, 2)], use_result_objects=True))


    def _check_multiple_args(self, func):
        result = list(func())
        assert result == [3, 5]

    def test_multiple_arguments(self):
        f1 = lambda x, y: x+y
        pool = self.mk_pool()
        check = self._check_multiple_args
        check(lambda: pool.map(f1, [1, 2], [2, 3]))
        check(lambda: pool.imap(f1, [1, 2], [2, 3]))
        check(lambda: pool.starmap(f1, [(1, 2), (2, 3)]))
        check(lambda: pool.starcall([(f1, 1, 2), (f1, 2, 3)]))

    def _check_multiple_args_with_exceptions_result_object(self, func):
        result = list(func())
        assert result[0].result == 3
        assert type(result[1].exception[1]) == ValueError
        assert result[2].result == 7

    def test_multiple_arguments_exceptions_result_object(self):
        def f1(x, y):
            if x+y == 5:
                raise ValueError()
            return x+y
        pool = self.mk_pool()
        check = self._check_multiple_args_with_exceptions_result_object
        check(lambda: pool.map(f1, [1, 2, 3], [2, 3, 4], use_result_objects=True))
        check(lambda: pool.imap(f1, [1, 2, 3], [2, 3, 4], use_result_objects=True))
        check(lambda: pool.starmap(f1, [(1, 2), (2, 3), (3, 4)], use_result_objects=True))
        check(lambda: pool.starcall([(f1, 1, 2), (f1, 2, 3), (f1, 3, 4)], use_result_objects=True))

    def _check_multiple_args_with_exceptions(self, func):
        result = func()
        try:
            # first result might aleady raise the exception when
            # when second result is returned faster by the ThreadPoolWorker
            assert next(result) == 3
            next(result)
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
        check_pool_map()
        check(lambda: pool.imap(f1, [1, 2, 3], [2, 3, 4]))
        check(lambda: pool.starmap(f1, [(1, 2), (2, 3), (3, 4)]))
        check(lambda: pool.starcall([(f1, 1, 2), (f1, 2, 3), (f1, 3, 4)]))



class TestThreadPool(CommonPoolTests):
    def mk_pool(self):
        return ThreadPool()

    def test_base_config(self):
        # test that all concurrent have access to their
        # local base_config
        from mapproxy.config import base_config
        from mapproxy.config import local_base_config
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
                list(pool1.imap(check1, list(range(200))))

        def test2():
            with local_base_config(conf2):
                pool2 = ThreadPool(5)
                list(pool2.imap(check2, list(range(200))))

        t1 = threading.Thread(target=test1)
        t2 = threading.Thread(target=test2)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
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
            self.te.map(self.execute, list(range(100)))
        except DummyException:
            print(self.exec_count)
            assert 7 <= self.exec_count <= 10, 'execution should be interrupted really '\
                                               'soon (exec_count should be 7+(max(3)))'
        else:
            assert False, 'expected DummyException'

