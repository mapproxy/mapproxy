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
                
                