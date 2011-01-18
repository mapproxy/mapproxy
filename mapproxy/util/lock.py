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
