import tempfile
import os
import shutil
import time
import threading
import multiprocessing

from mapproxy.util.lock import FileLock

from nose.tools import eq_

lock_dir = tempfile.mkdtemp()
lock_file = os.path.join(lock_dir, 'lock.lck')
count_file = os.path.join(lock_dir, 'count.txt')
open(count_file, 'w').write('0')

def lock(p=None):
    l = FileLock(lock_file, timeout=60)
    l.lock()
    counter = int(open(count_file).read())
    open(count_file, 'w').write(str(counter+1))
    time.sleep(0.001)
    l.unlock()

def test_file_lock_load():
    def lock_x():
        for x in range(5):
            time.sleep(0.01)
            lock()
    threads = [threading.Thread(target=lock_x) for _ in range(20)]
    p = multiprocessing.Pool(5)
    [t.start() for t in threads]
    p.map(lock, range(50))
    [t.join() for t in threads]

    eq_(int(open(count_file).read()), 150)


def teardown():
    shutil.rmtree(lock_dir)


