# This file is part of the MapProxy project.
# Copyright (C) 2010-2013 Omniscale <http://omniscale.de>
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
File system related utility functions.
"""
from __future__ import with_statement, absolute_import
import time
import os
import sys
import random
import errno
import shutil

def swap_dir(src_dir, dst_dir, keep_old=False, backup_ext='.tmp'):
    """
    Rename `src_dir` to `dst_dir`. The `dst_dir` is first renamed to
    `dst_dir` + `backup_ext` to keep the interruption short.
    Then the `src_dir` is renamed. If `keep_old` is False, the old content
    of `dst_dir` will be removed.
    """
    tmp_dir = dst_dir + backup_ext
    if os.path.exists(dst_dir):
        os.rename(dst_dir, tmp_dir)

    _force_rename_dir(src_dir, dst_dir)

    if os.path.exists(tmp_dir) and not keep_old:
        shutil.rmtree(tmp_dir)

def _force_rename_dir(src_dir, dst_dir):
    """
    Rename `src_dir` to `dst_dir`. If `dst_dir` exists, it will be removed.
    """
    # someone might recreate the directory between rmtree and rename,
    # so we try to remove it until we can rename our new directory
    rename_tries = 0
    while rename_tries < 10:
        try:
            os.rename(src_dir, dst_dir)
        except OSError as ex:
            if ex.errno == errno.ENOTEMPTY or ex.errno == errno.EEXIST:
                if rename_tries > 0:
                    time.sleep(2**rename_tries / 100.0) # from 10ms to 5s
                rename_tries += 1
                shutil.rmtree(dst_dir)
            else:
                raise
        else:
            break # on success

def cleanup_directory(directory, before_timestamp, remove_empty_dirs=True,
                      file_handler=None):
    if file_handler is None:
        if before_timestamp == 0 and remove_empty_dirs == True and os.path.exists(directory):
            shutil.rmtree(directory, ignore_errors=True)
            return

        file_handler = os.remove

    if os.path.exists(directory):
        for dirpath, dirnames, filenames in os.walk(directory, topdown=False):
            if not filenames:
                if (remove_empty_dirs and not os.listdir(dirpath)
                    and dirpath != directory):
                    os.rmdir(dirpath)
                continue
            for filename in filenames:
                filename = os.path.join(dirpath, filename)
                try:
                    if before_timestamp == 0:
                        file_handler(filename)
                    if os.lstat(filename).st_mtime < before_timestamp:
                        file_handler(filename)
                except OSError as ex:
                    if ex.errno != errno.ENOENT: raise

            if remove_empty_dirs:
                remove_dir_if_emtpy(dirpath)

        if remove_empty_dirs:
            remove_dir_if_emtpy(directory)

def remove_dir_if_emtpy(directory):
    try:
        os.rmdir(directory)
    except OSError as ex:
        if ex.errno != errno.ENOENT and ex.errno != errno.ENOTEMPTY: raise

def ensure_directory(file_name):
    """
    Create directory if it does not exist, else do nothing.
    """
    dir_name = os.path.dirname(file_name)
    if not os.path.exists(dir_name):
        try:
            os.makedirs(dir_name)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise e

def write_atomic(filename, data):
    """
    write_atomic writes `data` to a random file in filename's directory
    first and renames that file to the target filename afterwards.
    Rename is atomic on all POSIX platforms.

    Falls back to normal write on Windows.
    """
    if not sys.platform.startswith('win'):
        # write to random filename to prevent concurrent writes in cases
        # where file locking does not work (network fs)
        path_tmp = filename + '.tmp-' + str(random.randint(0, 99999999))
        try:
            fd = os.open(path_tmp, os.O_EXCL | os.O_CREAT | os.O_WRONLY)
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
            os.rename(path_tmp, filename)
        except OSError as ex:
            try:
                os.unlink(path_tmp)
            except OSError:
                pass
            raise ex
    else:
        with open(filename, 'wb') as f:
            f.write(data)
