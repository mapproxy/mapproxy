##############################################################################
#
# This is a modified version of zc.lockfile 1.0.0
# (http://pypi.python.org/pypi/zc.lockfile/1.0.0)
#
# Copyright (c) 2001, 2002 Zope Corporation and Contributors.
# All Rights Reserved.
#
# ==== Changelog ====
# 2010-04-01 - Commented out logging. <olt@omniscale.de>
#
# ==== License ====
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).
#
# Zope Public License (ZPL) Version 2.1
#
# A copyright notice accompanies this license document that identifies the
# copyright holders.
#
# This license has been certified as open source. It has also been designated as
# GPL compatible by the Free Software Foundation (FSF).
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# - Redistributions in source code must retain the accompanying copyright
#   notice, this list of conditions, and the following disclaimer.
#
# - Redistributions in binary form must reproduce the accompanying copyright
#   notice, this list of conditions, and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
# - Names of the copyright holders must not be used to endorse or promote
#   products derived from this software without prior written permission from
#   the copyright holders.
#
# - The right to distribute this software or to use it for any purpose does not
#   give you the right to use Servicemarks (sm) or Trademarks (tm) of the
#   copyright holders. Use of them is covered by separate agreement with the
#   copyright holders.
#
# - If any files are modified, you must cause the modified files to carry
#   prominent notices stating that you changed the files and the date of any
#   change.
#
# Disclaimer
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY EXPRESSED
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
# EVENT SHALL THE COPYRIGHT HOLDERS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE
##############################################################################

import os
# import logging
# logger = logging.getLogger("zc.lockfile")

class LockError(Exception):
    """Couldn't get a lock
    """

try:
    import fcntl
except ImportError:
    try:
        import msvcrt
    except ImportError:
        def _lock_file(file):
            raise TypeError('No file-locking support on this platform')
        def _unlock_file(file):
            raise TypeError('No file-locking support on this platform')

    else:
        # Windows
        def _lock_file(file):
            # Lock just the first byte
            try:
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            except IOError:
                raise LockError("Couldn't lock %r" % file.name)

        def _unlock_file(file):
            try:
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            except IOError:
                raise LockError("Couldn't unlock %r" % file.name)

else:
    # Unix
    _flags = fcntl.LOCK_EX | fcntl.LOCK_NB

    def _lock_file(file):
        try:
            fcntl.flock(file.fileno(), _flags)
        except IOError:
            raise LockError("Couldn't lock %r" % file.name)


    def _unlock_file(file):
        # File is automatically unlocked on close
        pass


class LockFile:

    _fp = None

    def __init__(self, path):
        self._path = path
        fp = open(path, 'w+')

        try:
            _lock_file(fp)
        except Exception as ex:
            try:
                fp.close()
            except Exception:
                pass
            raise ex

        self._fp = fp
        fp.write(" %s\n" % os.getpid())
        fp.truncate()
        fp.flush()

    def close(self):
        if self._fp is not None:
            _unlock_file(self._fp)
            self._fp.close()
            self._fp = None
