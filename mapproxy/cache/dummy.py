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

from mapproxy.cache.base import TileCacheBase
from mapproxy.util.lock import DummyLock


class DummyCache(TileCacheBase):
    def is_cached(self, tile, dimensions=None):
        return False

    def lock(self, tile):
        return DummyLock()

    def load_tile(self, tile, with_metadata=False, dimensions=None):
        pass

    def store_tile(self, tile, dimensions=None):
        pass


class DummyLocker(object):
    def lock(self, tile):
        return DummyLock()
