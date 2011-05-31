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

from __future__ import with_statement
import os
import glob
import sys
import shutil
import tempfile
import threading
import random
import time
from mapproxy.util.lock import (
    FileLock,
    SemLock,
    cleanup_lockdir,
    LockTimeout,
)
from mapproxy.util import (
    _force_rename_dir,
    swap_dir,
    cleanup_directory,
    timestamp_before,
)
from mapproxy.test.helper import Mocker

from nose.tools import eq_

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
        lock = self._create_lock()
        assert_locked(self.lock_file)
        lock # prevent lint warnings
    
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
        
        assert counter == 400, counter
    
    def test_remove_on_unlock(self):
        l = FileLock(self.lock_file, remove_on_unlock=True)
        l.lock()
        assert os.path.exists(self.lock_file)
        l.unlock()
        assert not os.path.exists(self.lock_file)

        l.lock()
        assert os.path.exists(self.lock_file)
        os.remove(self.lock_file)
        assert not os.path.exists(self.lock_file)
        # ignore removed lock
        l.unlock()
        assert not os.path.exists(self.lock_file)

    
    def _create_lock(self):
        lock = FileLock(self.lock_file)
        lock.lock()
        return lock

def assert_locked(lock_file, timeout=0.02, step=0.001):
    assert os.path.exists(lock_file)
    l = FileLock(lock_file, timeout=timeout, step=step)
    try:
        l.lock()
        assert False, 'file was not locked'
    except LockTimeout:
        pass


class TestSemLock(object):
    def setup(self):
        self.lock_dir = tempfile.mkdtemp()
        self.lock_file = os.path.join(self.lock_dir, 'lock.lck')
    def teardown(self):
        shutil.rmtree(self.lock_dir)
    
    def count_lockfiles(self):
        return len(glob.glob(self.lock_file + '*'))
    
    def test_single(self):
        locks = [SemLock(self.lock_file, 1, timeout=0.01) for _ in range(2)]
        locks[0].lock()
        try:
            locks[1].lock()
        except LockTimeout:
            pass
        else:
            assert False, 'expected LockTimeout'
        
    
    def test_creating(self):
        locks = [SemLock(self.lock_file, 2) for _ in range(3)]
        
        eq_(self.count_lockfiles(), 0)
        locks[0].lock()
        eq_(self.count_lockfiles(), 1)
        locks[1].lock()
        eq_(self.count_lockfiles(), 2)
        assert os.path.exists(locks[0]._lock._path)
        assert os.path.exists(locks[1]._lock._path)
        locks[0].unlock()
        locks[2].lock()
        locks[2].unlock()
        locks[1].unlock()

    def test_timeout(self):
        locks = [SemLock(self.lock_file, 2, timeout=0.1) for _ in range(3)]
        
        eq_(self.count_lockfiles(), 0)
        locks[0].lock()
        eq_(self.count_lockfiles(), 1)
        locks[1].lock()
        eq_(self.count_lockfiles(), 2)
        try:
            locks[2].lock()
        except LockTimeout:
            pass
        else:
            assert False, 'expected LockTimeout'
        locks[0].unlock()
        locks[2].unlock()
    
    def test_load(self):
        locks = [SemLock(self.lock_file, 8, timeout=1) for _ in range(20)]
        
        new_locks = random.sample([l for l in locks if not l._locked], 5)
        for l in new_locks:
            l.lock()
        
        for _ in range(20):
            old_locks = random.sample([l for l in locks if l._locked], 3)
            for l in old_locks:
                l.unlock()
            eq_(len([l for l in locks if l._locked]), 2)
            eq_(len([l for l in locks if not l._locked]), 18)

            new_locks = random.sample([l for l in locks if not l._locked], 3)
            for l in new_locks:
                l.lock()

            eq_(len([l for l in locks if l._locked]), 5)
            eq_(len([l for l in locks if not l._locked]), 15)
        
        assert self.count_lockfiles() == 8


class DirTest(object):
    def setup(self):
        self.tmpdir = tempfile.mkdtemp()
    def teardown(self):
        if os.path.exists(self.tmpdir):
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
