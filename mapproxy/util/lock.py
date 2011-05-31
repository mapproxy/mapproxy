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


from mapproxy.util.ext.lockfile import LockFile
from mapproxy.platform.lock import LockTimeout, FileLock, LockError, cleanup_lockdir

__all__ = ['LockTimeout', 'FileLock', 'LockError', 'cleanup_lockdir', 'SemLock']

import random

class SemLock(FileLock):
    """
    File-lock-based counting semaphore (i.e. this lock can be locked n-times).
    """
    def __init__(self, lock_file, n, timeout=60.0, step=0.01):
        FileLock.__init__(self, lock_file, timeout=timeout, step=step)
        self.n = n
    
    def _try_lock(self):
        tries = 0
        i = random.randint(0, self.n-1)
        while True:
            tries += 1
            try:
                return LockFile(self.lock_file + str(i))
            except LockError:
                if tries >= self.n:
                    raise
            i = (i+1) % self.n

class DummyLock(object):
    def __enter__(self):
        pass
    def __exit__(self, _exc_type, _exc_value, _traceback):
        pass
    def lock(self):
        pass
    def unlock(self):
        pass
