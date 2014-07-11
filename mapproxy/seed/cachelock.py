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

import errno
import os
import sqlite3
import time
from contextlib import contextmanager

class CacheLockedError(Exception):
    pass

class CacheLocker(object):
    def __init__(self, lockfile, polltime=0.1):
        self.lockfile = lockfile
        self.polltime = polltime
        self._initialize_lockfile()

    def _initialize_lockfile(self):
        db  = sqlite3.connect(self.lockfile)
        db.execute("""
            CREATE TABLE IF NOT EXISTS cache_locks (
                cache_name TEXT NOT NULL,
                created REAL NOT NULL,
                pid INTEGER NUT NULL
            );
        """)
        db.commit()
        db.close()

    @contextmanager
    def _exclusive_db_cursor(self):
        db  = sqlite3.connect(self.lockfile, isolation_level="EXCLUSIVE")
        db.row_factory = sqlite3.Row
        cur = db.cursor()

        try:
            yield cur
        finally:
            db.commit()
            db.close()

    @contextmanager
    def lock(self, cache_name, no_block=False):

        pid = os.getpid()

        while True:
            with self._exclusive_db_cursor() as cur:
                self._add_lock(cur, cache_name, pid)
                if self._poll(cur, cache_name, pid):
                    break
                elif no_block:
                    raise CacheLockedError()
            time.sleep(self.polltime)

        try:
            yield
        finally:
            with self._exclusive_db_cursor() as cur:
                self._remove_lock(cur, cache_name, pid)

    def _poll(self, cur, cache_name, pid):
        active_locks = False
        cur.execute("SELECT * from cache_locks where cache_name = ? ORDER BY created", (cache_name, ))

        for lock in cur:
            if not active_locks and lock['cache_name'] == cache_name and lock['pid'] == pid:
                # we are waiting and it is out turn
                return True

            if not is_running(lock['pid']):
                self._remove_lock(cur, lock['cache_name'], lock['pid'])
            else:
                active_locks = True

        return not active_locks

    def _add_lock(self, cur, cache_name, pid):
        cur.execute("SELECT count(*) from cache_locks WHERE cache_name = ? AND pid = ?", (cache_name, pid))
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO cache_locks (cache_name, pid, created) VALUES (?, ?, ?)", (cache_name, pid, time.time()))

    def _remove_lock(self, cur, cache_name, pid):
        cur.execute("DELETE FROM cache_locks WHERE cache_name = ?  AND pid = ?", (cache_name, pid))

class DummyCacheLocker(object):
    @contextmanager
    def lock(self, cache_name, no_block=False):
        yield

def is_running(pid):
    try:
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == errno.ESRCH:
            return False
        elif err.errno == errno.EPERM:
            return True
        else:
            raise err
    else:
        return True

if __name__ == '__main__':
    locker = CacheLocker('/tmp/cachelock_test')
    with locker.lock('foo'):
        pass