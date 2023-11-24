# This file is part of the MapProxy project.
# Copyright (C) 2010-2014 Omniscale <http://omniscale.de>
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

"""
Utility methods and classes (file locking, asynchronous execution pools, etc.).
"""

import random
import time
import os
import errno

from mapproxy.util.ext.lockfile import LockFile, LockError

import logging
log = logging.getLogger(__name__)

__all__ = ['LockTimeout', 'FileLock', 'LockError', 'cleanup_lockdir', 'SemLock']


class LockTimeout(Exception):
    pass


class FileLock(object):
    def __init__(self, lock_file, timeout=60.0, step=0.01, remove_on_unlock=False):
        self.lock_file = lock_file
        self.timeout = timeout
        self.step = step
        self.remove_on_unlock = remove_on_unlock
        self._locked = False

    def __enter__(self):
        self.lock()

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.unlock()

    def _make_lockdir(self):
        if not os.path.exists(os.path.dirname(self.lock_file)):
            try:
                os.makedirs(os.path.dirname(self.lock_file))
            except OSError as e:
                if e.errno is not errno.EEXIST:
                    raise e

    def _try_lock(self):
        return LockFile(self.lock_file)

    def lock(self):
        self._make_lockdir()
        current_time = time.time()
        stop_time = current_time + self.timeout

        while not self._locked:
            try:
                self._lock = self._try_lock()
            except LockError:
                current_time = time.time()
                if current_time < stop_time:
                    time.sleep(self.step)
                    continue
                else:
                    raise LockTimeout('another process is still running with our lock')
            else:
                self._locked = True

    def unlock(self):
        if self._locked:
            self._locked = False
            if self.remove_on_unlock:
                try:
                    # try to release lock by removing
                    # this is not a clean way and more than one process might
                    # grab the lock afterwards but it is ok when the task is
                    # solved by the first process that got the lock (i.e. the
                    # tile is created)
                    os.remove(self.lock_file)
                except OSError:
                    self._lock.close()
            else:
                self._lock.close()

    def __del__(self):
        self.unlock()

_cleanup_counter = -1
def cleanup_lockdir(lockdir, suffix='.lck', max_lock_time=300, force=True):
    """
    Remove files ending with `suffix` from `lockdir` if they are older then
    `max_lock_time` seconds.
    It will not cleanup on every call if `force` is ``False``.
    """
    global _cleanup_counter
    _cleanup_counter += 1
    if not force and _cleanup_counter % 50 != 0:
        return
    expire_time = time.time() - max_lock_time
    if not os.path.exists(lockdir):
        return
    if not os.path.isdir(lockdir):
        log.warning('lock dir not a directory: %s', lockdir)
        return
    for entry in os.listdir(lockdir):
        name = os.path.join(lockdir, entry)
        try:
            if os.path.isfile(name) and name.endswith(suffix):
                if os.path.getmtime(name) < expire_time:
                    try:
                        os.unlink(name)
                    except IOError as ex:
                        log.warning('could not remove old lock file %s: %s', name, ex)
        except OSError as e:
            # some one might have removed the file (ENOENT)
            # or we don't have permissions to remove it (EACCES)
            if e.errno in (errno.ENOENT, errno.EACCES):
                # ignore
                pass
            else:
                raise e


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
