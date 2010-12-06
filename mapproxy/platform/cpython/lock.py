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
import errno

from mapproxy.util.ext.lockfile import LockFile, LockError

import logging
log = logging.getLogger(__name__)

class LockTimeout(Exception):
    pass


class FileLock(object):
    def __init__(self, lock_file, timeout=60.0, step=0.01):
        self.lock_file = lock_file
        self.timeout = timeout
        self.step = step
        self._locked = False
    
    def __enter__(self):
        self.lock()
    
    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.unlock()
    
    def _make_lockdir(self):
        if not os.path.exists(os.path.dirname(self.lock_file)):
            try:
                os.makedirs(os.path.dirname(self.lock_file))
            except OSError, e:
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
            self._lock.close()
    
    def __del__(self):
        self.unlock()


def cleanup_lockdir(lockdir, suffix='.lck', max_lock_time=300):
    expire_time = time.time() - max_lock_time
    if not os.path.exists(lockdir) or not os.path.isdir(lockdir):
        log.warn('lock dir not a directory: %s', lockdir)
        return
    for entry in os.listdir(lockdir):
        name = os.path.join(lockdir, entry)
        try:
            if os.path.isfile(name) and name.endswith(suffix):
                if os.path.getmtime(name) < expire_time:
                    try:
                        os.unlink(name)
                    except IOError, ex:
                        log.warn('could not remove old lock file %s: %s', name, ex)
        except OSError, e:
            # some one might remove the file, ignore this
            if e.errno != errno.ENOENT:
                raise e


