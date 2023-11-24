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


MAX_MAP_ASYNC_THREADS = 20

try:
    import Queue
except ImportError:
    import queue as Queue

import sys
import threading

from mapproxy.config import base_config
from mapproxy.config import local_base_config
from mapproxy.compat import PY2

import logging
log_system = logging.getLogger('mapproxy.system')

class AsyncResult(object):
    def __init__(self, result=None, exception=None):
        self.result = result
        self.exception = exception

    def __repr__(self):
        return "<AsyncResult result='%s' exception='%s'>" % (
            self.result, self.exception)


def _result_iter(results, use_result_objects=False):
    for result in results:
        if use_result_objects:
            exception = None
            if (isinstance(result, tuple) and len(result) == 3 and
                isinstance(result[1], Exception)):
                exception = result
                result = None
            yield AsyncResult(result, exception)
        else:
            yield result


class ThreadWorker(threading.Thread):
    def __init__(self, task_queue, result_queue):
        threading.Thread.__init__(self)
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.base_config = base_config()
    def run(self):
        with local_base_config(self.base_config):
            while True:
                task = self.task_queue.get()
                if task is None:
                    self.task_queue.task_done()
                    break
                exec_id, func, args = task
                try:
                    result = func(*args)
                except Exception:
                    result = sys.exc_info()
                self.result_queue.put((exec_id, result))
                self.task_queue.task_done()


def _consume_queue(queue):
    """
    Get all items from queue.
    """
    while not queue.empty():
        try:
            queue.get(block=False)
            queue.task_done()
        except Queue.Empty:
            pass


class ThreadPool(object):
    def __init__(self, size=4):
        self.pool_size = size
        self.task_queue = Queue.Queue()
        self.result_queue = Queue.Queue()
        self.pool = None
    def map_each(self, func_args, raise_exceptions):
        """
        args should be a list of function arg tuples.
        map_each calls each function with the given arg.
        """
        if self.pool_size < 2:
            for func, arg in func_args:
                try:
                    yield func(*arg)
                except Exception:
                    yield sys.exc_info()
            return

        self.pool = self._init_pool()

        i = 0
        for i, (func, arg) in enumerate(func_args):
            self.task_queue.put((i, func, arg))

        results = {}

        next_result = 0
        for value in self._get_results(next_result, results, raise_exceptions):
            yield value
            next_result += 1

        self.task_queue.join()
        for value in self._get_results(next_result, results, raise_exceptions):
            yield value
            next_result += 1

        self.shutdown()

    def _single_call(self, func, args, use_result_objects):
        try:
            result = func(*args)
        except Exception:
            if not use_result_objects:
                raise
            result = sys.exc_info()
        return _result_iter([result], use_result_objects)

    def map(self, func, *args, **kw):
        return list(self.imap(func, *args, **kw))

    def imap(self, func, *args, **kw):
        use_result_objects = kw.get('use_result_objects', False)
        if len(args[0]) == 1:
            return self._single_call(func, next(iter(zip(*args))), use_result_objects)
        return _result_iter(self.map_each([(func, arg) for arg in zip(*args)], raise_exceptions=not use_result_objects),
                            use_result_objects)

    def starmap(self, func, args, **kw):
        use_result_objects = kw.get('use_result_objects', False)
        if len(args[0]) == 1:
            return self._single_call(func, args[0], use_result_objects)

        return _result_iter(self.map_each([(func, arg) for arg in args], raise_exceptions=not use_result_objects),
                            use_result_objects)

    def starcall(self, args, **kw):
        def call(func, *args):
            return func(*args)
        return self.starmap(call, args, **kw)

    def _get_results(self, next_result, results, raise_exceptions):
        for i, value in self._fetch_results(raise_exceptions):
            if i == next_result:
                yield value
                next_result += 1
                while next_result in results:
                    yield results.pop(next_result)
                    next_result += 1
            else:
                results[i] = value

    def _fetch_results(self, raise_exceptions):
        while not self.task_queue.empty() or not self.result_queue.empty():
            task_result = self.result_queue.get()
            if (raise_exceptions and isinstance(task_result[1], tuple) and
                len(task_result[1]) == 3 and
                isinstance(task_result[1][1], Exception)):
                self.shutdown(force=True)
                exc_class, exc, tb = task_result[1]
                if PY2:
                    exec('raise exc_class, exc, tb')
                else:
                    raise exc.with_traceback(tb)
            yield task_result

    def shutdown(self, force=False):
        """
        Send shutdown sentinel to all executor threads. If `force` is True,
        clean task_queue and result_queue.
        """

        if force:
            _consume_queue(self.task_queue)
            _consume_queue(self.result_queue)
        for _ in range(self.pool_size):
            self.task_queue.put(None)

    def _init_pool(self):
        if self.pool_size < 2:
            return []
        pool = []
        for _ in range(self.pool_size):
            t = ThreadWorker(self.task_queue, self.result_queue)
            t.daemon = True
            t.start()
            pool.append(t)
        return pool


def imap(func, *args):
    pool = ThreadPool(min(len(args[0]), MAX_MAP_ASYNC_THREADS))
    return pool.imap(func, *args)

def starmap(func, args):
    pool = ThreadPool(min(len(args[0]), MAX_MAP_ASYNC_THREADS))
    return pool.starmap(func, args)

def starcall(args):
    pool = ThreadPool(min(len(args[0]), MAX_MAP_ASYNC_THREADS))
    return pool.starcall(args)

def run_non_blocking(func, args, kw={}):
    return func(*args, **kw)


Pool = ThreadPool
