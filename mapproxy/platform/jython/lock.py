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
from mapproxy.platform.cpython.lock import LockTimeout, FileLock as FileLock_
LockTimeout # prevent pyflakes warnings
from threading import Lock

class LockError(Exception):
    pass

locked_files = set() 
locked_files_lock = Lock()

class FileLock(FileLock_):
    def _make_lockdir(self):
        return
    
    def _try_lock(self):
        return SetLock(self.lock_file)
    

class SetLock(object):
    def __init__(self, name):
        self._name = name
        with locked_files_lock:
            if not name in locked_files:
                locked_files.add(name)
            else:
                raise LockError
            
    def close(self):
        if self._name in locked_files:
            locked_files.remove(self._name)
            
def cleanup_lockdir(*args, **kw):
    return None
                
                