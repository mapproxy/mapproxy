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

from __future__ import with_statement
import os
import stat
import sys
import shutil
import tempfile
import thread
import threading
import time
import mapproxy.core.utils
from mapproxy.core.utils import (
    FileLock,
    cleanup_lockdir,
    LockTimeout,
    ThreadedExecutor,
    _force_rename_dir,
    swap_dir,
    cleanup_directory,
    timestamp_before,
)
from mapproxy.tests.helper import Mocker, mocker, LogMock

from nose.tools import timed

is_win = sys.platform == 'win32'

class TestFileLock(Mocker):
    def setup(self):
        Mocker.setup(self)
        self.lock_dir = tempfile.mkdtemp()
        self.lock_file = os.path.join(self.lock_dir, 'lock.lck')
    def teardown(self):
        shutil.rmtree(self.lock_dir)
        Mocker.teardown(self)
    def test_file_lock_timeout(self):
        running_lock = self._create_lock()
        assert_locked(self.lock_file)
    
    def test_file_lock(self):
        # Test a lock that becomes free during a waiting lock() call.
        class Lock(threading.Thread):
            def __init__(self, lock_file):
                threading.Thread.__init__(self)
                self.lock_file = lock_file
                self.lock = FileLock(self.lock_file)
            def run(self):
                self.lock.lock()
                time.sleep(0.2)
                self.lock.unlock()
        
        lock_thread = Lock(self.lock_file)
        start_time = time.time()
        lock_thread.start()
        
        # wait until thread got the locked
        while not lock_thread.lock._locked:
            time.sleep(0.001)
        
        # one lock that times out
        assert_locked(self.lock_file)
        
        # one lock that will get it after some time
        l = FileLock(self.lock_file, timeout=0.3, step=0.001)
        l.lock()
        
        locked_for = time.time() - start_time
        assert locked_for - 0.2 <=0.1, 'locking took to long?! (rerun if not sure)'
        
        #cleanup
        l.unlock()
        lock_thread.join()
    
    def test_lock_cleanup(self):
        old_lock_file = os.path.join(self.lock_dir, 'lock_old.lck')
        l = FileLock(old_lock_file)
        l.lock()
        l.unlock()
        mtime = os.stat(old_lock_file).st_mtime
        mtime -= 7*60
        os.utime(old_lock_file, (mtime, mtime))
        
        l = self._create_lock()
        l.unlock()
        assert os.path.exists(old_lock_file)
        assert os.path.exists(self.lock_file)
        cleanup_lockdir(self.lock_dir)
        
        assert not os.path.exists(old_lock_file)
        assert os.path.exists(self.lock_file)
    
    def test_concurrent_access(self):
        count_file = os.path.join(self.lock_dir, 'count.txt')
        with open(count_file, 'wb') as f:
            f.write('0')
        
        def count_up():
            with FileLock(self.lock_file, timeout=60):
                with open(count_file, 'r+b') as f:
                    counter = int(f.read().strip())
                    f.seek(0)
                    f.write(str(counter+1))

        def do_it():
            for x in range(20):
                time.sleep(0.002)
                count_up()
        threads = [threading.Thread(target=do_it) for _ in range(20)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        
        with open(count_file, 'r+b') as f:
            counter = int(f.read().strip())
        
        assert counter == 400
    
    def _create_lock(self):
        lock = FileLock(self.lock_file)
        lock.lock()
        return lock

def assert_locked(lock_file, timeout=0.02, step=0.001):
    assert os.path.exists(lock_file)
    l = FileLock(lock_file, timeout=timeout, step=step)
    try:
        l.lock()
        assert False
    except LockTimeout, e:
        pass

class TestThreadedExecutor(object):
    def setup(self):
        self.lock = threading.Lock()
        self.exec_count = 0
        self.te = ThreadedExecutor(self.execute, pool_size=5)
    def execute(self, x):
        with self.lock:
            self.exec_count += 1
        return x
    def test_execute(self):
        self.te.execute(range(10))
        assert self.exec_count == 10
    def test_execute_result_order(self):
        result = self.te.execute(x for x in range(1000))
        assert result == range(1000)

class TestThreadedExecutorPool(object):
    def setup(self):
        self.lock = threading.Lock()
        self.exec_count = 0
        self.te = ThreadedExecutor(self.execute, pool_size=5)
    def execute(self, x):
        time.sleep(0.005)
        with self.lock:
            self.exec_count += 1
        return x
    def test_execute(self):
        self.te.execute(range(10))
        print self.exec_count
        assert self.exec_count == 10


class DummyException(Exception):
    pass

class TestThreadedExecutorException(object):
    def setup(self):
        self.lock = threading.Lock()
        self.exec_count = 0
        self.te = ThreadedExecutor(self.execute, pool_size=2)
    def execute(self, x):
        time.sleep(0.005)
        with self.lock:
            self.exec_count += 1
            if self.exec_count == 7:
                raise DummyException()
        return x
    def test_execute_w_exception(self):
        try:
            self.te.execute(range(100))
        except DummyException:
            print self.exec_count
            assert 7 <= self.exec_count <= 10, 'execution should be interrupted really '\
                                               'soon (exec_count should be 7+(max(3)))'
        else:
            assert False, 'expected DummyException'

class DirTest(object):
    def setup(self):
        self.tmpdir = tempfile.mkdtemp()
    def teardown(self):
        shutil.rmtree(self.tmpdir)
    def mkdir(self, name):
        dirname = os.path.join(self.tmpdir, name)
        os.mkdir(dirname)
        self.mkfile(name, dirname=dirname)
        return dirname
    def mkfile(self, name, dirname=None):
        if dirname is None:
            dirname = self.mkdir(name)
        filename = os.path.join(dirname, name + '.txt')
        open(filename, 'w').close()
        return filename
        

class TestForceRenameDir(DirTest):
    def test_rename(self):
        src_dir = self.mkdir('bar')
        dst_dir = os.path.join(self.tmpdir, 'baz')
        _force_rename_dir(src_dir, dst_dir)
        assert os.path.exists(dst_dir)
        assert os.path.exists(os.path.join(dst_dir, 'bar.txt'))
        assert not os.path.exists(src_dir)
    def test_rename_overwrite(self):
        src_dir = self.mkdir('bar')
        dst_dir = self.mkdir('baz')
        _force_rename_dir(src_dir, dst_dir)
        assert os.path.exists(dst_dir)
        assert os.path.exists(os.path.join(dst_dir, 'bar.txt'))
        assert not os.path.exists(src_dir)


class TestSwapDir(DirTest):
    def test_swap_dir(self):
        src_dir = self.mkdir('bar')
        dst_dir = os.path.join(self.tmpdir, 'baz')
        
        swap_dir(src_dir, dst_dir)
        assert os.path.exists(dst_dir)
        assert os.path.exists(os.path.join(dst_dir, 'bar.txt'))
        assert not os.path.exists(src_dir)
    
    def test_swap_dir_w_old(self):
        src_dir = self.mkdir('bar')
        dst_dir = self.mkdir('baz')
        
        swap_dir(src_dir, dst_dir)
        assert os.path.exists(dst_dir)
        assert os.path.exists(os.path.join(dst_dir, 'bar.txt'))
        assert not os.path.exists(src_dir)
    
    def test_swap_dir_keep_old(self):
        src_dir = self.mkdir('bar')
        dst_dir = self.mkdir('baz')
        
        swap_dir(src_dir, dst_dir, keep_old=True, backup_ext='.bak')
        assert os.path.exists(dst_dir)
        assert os.path.exists(os.path.join(dst_dir, 'bar.txt'))
        assert os.path.exists(dst_dir + '.bak')
        assert os.path.exists(os.path.join(dst_dir + '.bak', 'baz.txt'))
        

class TestCleanupDirectory(DirTest):
    def test_no_remove(self):
        dirs = [self.mkdir('dir'+str(n)) for n in range(10)]
        for d in dirs:
            assert os.path.exists(d), d
        cleanup_directory(self.tmpdir, timestamp_before(minutes=1))
        for d in dirs:
            assert os.path.exists(d), d

    def test_file_handler(self):
        files = []
        file_handler_calls = []
        def file_handler(filename):
            file_handler_calls.append(filename)
        new_date = timestamp_before(weeks=1)
        for n in range(10):
            fname = 'foo'+str(n)
            filename = self.mkfile(fname)
            os.utime(filename, (new_date, new_date))
            files.append(filename)
        
        for filename in files:
            assert os.path.exists(filename), filename
        cleanup_directory(self.tmpdir, timestamp_before(), file_handler=file_handler)
        for filename in files:
            assert os.path.exists(filename), filename
        
        assert set(files) == set(file_handler_calls)
    
    def test_no_directory(self):
        cleanup_directory(os.path.join(self.tmpdir, 'invalid'), timestamp_before())
        # nothing should happen
    
    def test_remove_all(self):
        files = []
        new_date = timestamp_before(weeks=1)
        for n in range(10):
            fname = 'foo'+str(n)
            filename = self.mkfile(fname)
            os.utime(filename, (new_date, new_date))
            files.append(filename)
        
        for filename in files:
            assert os.path.exists(filename), filename
        cleanup_directory(self.tmpdir, timestamp_before())
        for filename in files:
            assert not os.path.exists(filename), filename
            assert not os.path.exists(os.path.dirname(filename)), filename
            
    
    def test_remove_empty_dirs(self):
        os.makedirs(os.path.join(self.tmpdir, 'foo', 'bar', 'baz'))
        cleanup_directory(self.tmpdir, timestamp_before(minutes=-1))
        assert not os.path.exists(os.path.join(self.tmpdir, 'foo'))
    
    def test_remove_some(self):
        files = []
        new_date = timestamp_before(weeks=1)
        for n in range(10):
            fname = 'foo'+str(n)
            filename = self.mkfile(fname)
            if n % 2 == 0:
                os.utime(filename, (new_date, new_date))
            files.append(filename)
        
        for filename in files:
            assert os.path.exists(filename), filename
        cleanup_directory(self.tmpdir, timestamp_before())
        for filename in files[::2]:
            assert not os.path.exists(filename), filename
            assert not os.path.exists(os.path.dirname(filename)), filename
        for filename in files[1::2]:
            assert os.path.exists(filename), filename
