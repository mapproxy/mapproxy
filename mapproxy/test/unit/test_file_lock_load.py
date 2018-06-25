# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

import multiprocessing
import threading
import time

from mapproxy.util.lock import FileLock


def lock(args):
    lock_file, count_file = args
    l = FileLock(lock_file.strpath, timeout=60)
    l.lock()
    counter = int(count_file.read())
    count_file.write(str(counter+1))
    time.sleep(0.001)
    l.unlock()


def test_file_lock_load(tmpdir):
    lock_file = tmpdir.join('lock.lck')
    count_file = tmpdir.join('count.txt')
    count_file.write('0')

    def lock_x():
        for x in range(5):
            time.sleep(0.01)
            lock((lock_file, count_file))
    threads = [threading.Thread(target=lock_x) for _ in range(20)]
    p = multiprocessing.Pool(5)
    [t.start() for t in threads]
    p.map(lock, [(lock_file, count_file) for _ in range(50)])
    [t.join() for t in threads]

    counter = int(count_file.read())
    assert counter == 150
