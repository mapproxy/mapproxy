# This file is part of the MapProxy project.
# Copyright (C) 2012 Omniscale <http://omniscale.de>
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

import multiprocessing
import os
import shutil
import tempfile
import time

from mapproxy.seed.cachelock import CacheLocker, CacheLockedError

class TestCacheLock(object):
    
    def setup(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.lock_file = os.path.join(self.tmp_dir, 'lock')
        
    def teardown(self):
        shutil.rmtree(self.tmp_dir)
    
    def test_free_lock(self):
        locker = CacheLocker(self.lock_file)
        with locker.lock('foo'):
            assert True
    
    def test_locked_by_process_no_block(self):
        proc_is_locked = multiprocessing.Event()
        def lock():
            locker = CacheLocker(self.lock_file)
            with locker.lock('foo'):
                proc_is_locked.set()
                time.sleep(10)
        
        p = multiprocessing.Process(target=lock)
        p.start()
        # wait for process to start
        proc_is_locked.wait()
        
        locker = CacheLocker(self.lock_file)
        
        # test unlocked bar
        with locker.lock('bar', no_block=True):
            assert True
        
        # test locked foo
        try:
            with locker.lock('foo', no_block=True):
                assert False
        except CacheLockedError:
            pass
        finally:
            p.terminate()
            p.join()
    
    def test_locked_by_process_waiting(self):
        proc_is_locked = multiprocessing.Event()
        def lock():
            locker = CacheLocker(self.lock_file)
            with locker.lock('foo'):
                proc_is_locked.set()
                time.sleep(.1)
        
        p = multiprocessing.Process(target=lock)
        start_time = time.time()
        p.start()
        # wait for process to start
        proc_is_locked.wait()
        
        locker = CacheLocker(self.lock_file, polltime=0.02)
        try:
            with locker.lock('foo', no_block=False):
                diff = time.time() - start_time
                assert diff > 0.1
        finally:
            p.terminate()
            p.join()