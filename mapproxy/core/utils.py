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

"""
Utility methods and classes (file locking, asynchronous execution pools, etc.).
"""
from __future__ import with_statement
import time
import os
import sys
import errno
import Queue
import threading
import shutil
import datetime
from subprocess import Popen, PIPE

import logging
log = logging.getLogger(__name__)

class LockTimeout(Exception):
    pass


# WINPORT
if sys.platform == 'win32':
    import ctypes
    
    psapi = ctypes.windll.psapi
    kernel = ctypes.windll.kernel32
    
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    
    def process_is_running(pid, pid_exec):
        running = False
        
        mod = ctypes.c_ulong()
        count = ctypes.c_ulong()
        modname = ctypes.create_string_buffer(512)
        
        p = kernel.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, int(pid))
        if p:
            psapi.EnumProcessModules(p, ctypes.byref(mod), ctypes.sizeof(mod),
                ctypes.byref(count))
            psapi.GetModuleBaseNameA(p, mod.value, modname, ctypes.sizeof(modname))
            modname = ctypes.string_at(modname)
            running = modname == os.path.basename(pid_exec)

        kernel.CloseHandle(p)
        return running
    
else:
    def process_is_running(pid, pid_exec):
        pid_exec = os.path.basename(pid_exec)
        ps = Popen(['ps', '-o', 'command', '-p', str(pid)], stdout=PIPE).communicate()[0]
        lines = ps.split('\n')
        assert lines[0] == 'COMMAND'
        if len(lines) == 3 and lines[2] == '':
            lock_exec = lines[1].split(' ', 1)[0]
            lock_exec = os.path.basename(lock_exec)
            return pid_exec == lock_exec
        return False


class FileLock(object):
    def __init__(self, lock_file, timeout=60.0, step=0.01):
        self.lock_file = lock_file
        self.timeout = timeout
        self.step = step
        self._locked = False
        self.max_lock_time = 300
    
    def __enter__(self):
        self.lock()
    
    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.unlock()
    
    def lock(self):
        current_time = time.time()
        stop_time = current_time + self.timeout
        checked_stale = False
        while not self._locked:
            try:
                os.makedirs(self.lock_file)
                with open(_pid_file_for_lock(self.lock_file), 'w') as pid:
                    pid.write(str(os.getpid()) + ',' + sys.executable)
                self._locked = True
            except OSError, e:
                if e.errno is not errno.EEXIST:
                    raise e
                if not checked_stale:
                    checked_stale = True
                    if not self._other_lock_is_running():
                        log.warn('removing stale lock file: ' + self.lock_file)
                        _remove_lock(self.lock_file)
                        continue
                current_time = time.time()
                if current_time < stop_time:
                    time.sleep(self.step)
                    continue
                else:
                    raise LockTimeout('another process is still running with our lock')
    
    def unlock(self):
        if self._locked:
            self._locked = False
            _remove_lock(self.lock_file)
    
    def _read_pid_file(self):
        try:
            with open(_pid_file_for_lock(self.lock_file)) as pid:
                info = pid.readline()
                if ',' in info:
                    pid, executable = info.split(',')
                    return int(pid), executable
                return None, None
        except IOError, e:
            if e.errno is not errno.ENOENT:
                raise
            return None, None
    def _other_lock_is_running(self):
        """
        Check if the locking process is still running. Uses the POSIX ``ps`` command.
        """
        if self._lock_is_old():
            # if the lock is old, we assume it is not running anymore
            return False
        pid, pid_exec = self._read_pid_file()
        if pid is None:
            log.warn('no pid file found for ' + self.lock_file)
            return True
        return process_is_running(pid, pid_exec)
    
    def _lock_is_old(self):
        """
        Check if the lock file is older than ``max_lock_time``.
        """
        if self.max_lock_time <= 0:
            return False
        try:
            mtime = os.stat(self.lock_file).st_mtime
        except OSError, e:
            if e.errno == errno.ENOENT:
                return True
            raise e
        if time.time() - mtime > self.max_lock_time:
            return True
        else:
            return False
        
    def __del__(self):
        self.unlock()

def _remove_lock(lock_file):
    try:
        os.remove(_pid_file_for_lock(lock_file))
    except OSError, e:
        if e.errno == errno.ENOENT:
            log.warn('lock pid disappeared: ' + _pid_file_for_lock(lock_file))
        else:
            import traceback
            traceback.print_exc()
    try:
        os.rmdir(lock_file)
    except OSError, e:
        if e.errno == errno.ENOENT:
            log.warn('lock disappeared: ' + lock_file)
        else:
            import traceback
            traceback.print_exc()

def _pid_file_for_lock(lock_file):
    return os.path.join(lock_file, 'pid')

class ThreadedExecutor(object):
    class Executor(threading.Thread):
        def __init__(self, func, task_queue, result_queue):
            threading.Thread.__init__(self)
            self.func = func
            self.task_queue = task_queue
            self.result_queue = result_queue
        def run(self):
            while True:
                task = self.task_queue.get()
                if task is None:
                    self.task_queue.task_done()
                    break
                exec_id, args = task
                try:
                    result = self.func(args)
                except Exception:
                    result = sys.exc_info()
                self.result_queue.put((exec_id, result))
                self.task_queue.task_done()
    def __init__(self, func, pool_size=2):
        self.func = func
        self.pool_size = pool_size
        self.task_queue = Queue.Queue()
        self.result_queue = Queue.Queue()
        self.pool = self._init_pool()
    def execute(self, args):
        for i, arg in enumerate(args):
            self.task_queue.put((i, arg))
        result = []
        # immediately get results so we can raise exceptions asap 
        self._get_results(result)
        # wait for task_queue (all task_done calls)...
        self.task_queue.join()
        # and get remaining results
        self._get_results(result)
        
        result.sort()
        return [value for _, value in result]
    
    def _get_results(self, result):
        while not self.task_queue.empty() or not self.result_queue.empty():
            task_result = self.result_queue.get()
            if isinstance(task_result[1], tuple) and \
               isinstance(task_result[1][1], Exception):
                self.shutdown(force=True)
                exc_class, exc, tb = task_result[1]
                raise exc_class, exc, tb
            result.append(task_result)
        
    def __del__(self):
        self.shutdown()
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
        pool = []
        for _ in range(self.pool_size):
            t = ThreadedExecutor.Executor(self.func, self.task_queue, self.result_queue)
            t.daemon = True
            t.start()
            pool.append(t)
        return pool

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
    
def reraise_exception(new_exc, exc_info):
    """
    Reraise exception (`new_exc`) with the given `exc_info`.
    """
    _exc_class, _exc, tb = exc_info
    raise new_exc.__class__, new_exc, tb

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

def swap_dir(src_dir, dst_dir, keep_old=False, backup_ext='.tmp'):
    """
    Rename `src_dir` to `dst_dir`. The `dst_dir` is first renamed to
    `dst_dir` + `backup_ext` to keep the interruption short.
    Then the `src_dir` is renamed. If `keep_old` is False, the old content
    of `dst_dir` will be removed.
    """
    tmp_dir = dst_dir + backup_ext
    if os.path.exists(dst_dir):
        os.rename(dst_dir, tmp_dir)
    
    _force_rename_dir(src_dir, dst_dir)
    
    if os.path.exists(tmp_dir) and not keep_old:
        shutil.rmtree(tmp_dir)

def _force_rename_dir(src_dir, dst_dir):
    """
    Rename `src_dir` to `dst_dir`. If `dst_dir` exists, it will be removed.
    """
    # someone might recreate the directory between rmtree and rename,
    # so we try to remove it until we can rename our new directory
    rename_tries = 0
    while rename_tries < 10:
        try:
            os.rename(src_dir, dst_dir)
        except OSError, ex:
            if ex.errno == errno.ENOTEMPTY or ex.errno == errno.EEXIST:
                if rename_tries > 0:
                    time.sleep(2**rename_tries / 100.0) # from 10ms to 5s
                rename_tries += 1
                shutil.rmtree(dst_dir)
            else:
                raise
        else:
            break # on success

def timestamp_before(weeks=0, days=0, hours=0, minutes=0):
    """
    >>> time.time() - timestamp_before(minutes=1) - 60 <= 1
    True
    >>> time.time() - timestamp_before(days=1, minutes=2) - 86520 <= 1
    True
    >>> time.time() - timestamp_before(hours=2) - 7200 <= 1
    True
    """
    delta = datetime.timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes)
    before = datetime.datetime.now() - delta
    return time.mktime(before.timetuple())

def timestamp_from_isodate(isodate):
    """
    >>> timestamp_from_isodate('2009-06-09T10:57:00')
    1244537820.0
    >>> timestamp_from_isodate('2009-06-09T10:57')
    Traceback (most recent call last):
      ...
    ValueError: time data did not match format:  data=2009-06-09T10:57  fmt=%Y-%m-%dT%H:%M:%S
    """
    date = datetime.datetime.strptime(isodate, "%Y-%m-%dT%H:%M:%S")
    return time.mktime(date.timetuple())

def cleanup_directory(directory, before_timestamp, remove_empty_dirs=True, 
                      file_handler=None):
    if file_handler is None:
        file_handler = os.remove
    if os.path.exists(directory):
        for dirpath, dirnames, filenames in os.walk(directory, topdown=False):
            if not filenames:
                if (remove_empty_dirs and not os.listdir(dirpath)
                    and dirpath != directory):
                    os.rmdir(dirpath)
                continue
            for filename in filenames:
                filename = os.path.join(dirpath, filename)
                if os.stat(filename).st_mtime < before_timestamp:
                    file_handler(filename)
            if (remove_empty_dirs and not os.listdir(dirpath)
                and dirpath != directory):
                os.rmdir(dirpath)

def replace_instancemethod(old_method, new_method):
    """
    Replace an instance method.
    
    >>> class Foo(object):
    ...    val = 'bar'
    ...    def bar(self):
    ...        return self.val
    >>> f = Foo()
    >>> f.bar()
    'bar'
    >>> replace_instancemethod(f.bar, lambda self: 'foo' + self.val)
    >>> f.bar()
    'foobar'
    """
    cls = old_method.im_class
    obj = old_method.im_self
    name = old_method.im_func.func_name
    instancemethod = type(old_method)
    setattr(obj, name, instancemethod(new_method, obj, cls))