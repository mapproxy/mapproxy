# -:- encoding: utf-8 -:-
# This file is part of the MapProxy project.
# Copyright (C) 2013 Omniscale <http://omniscale.de>
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

from mapproxy.compat import iteritems

def seeds(cap, caches):
    seeds = {}
    cleanups = {}

    for cache_name, cache in iteritems(caches):
        for grid in cache['grids']:
            seeds[cache_name + '_' + grid] = {
                'caches': [cache_name],
                'grids': [grid],
            }
            cleanups[cache_name + '_' + grid] = {
                'caches': [cache_name],
                'grids': [grid],
                'remove_before': {
                    'time': '1900-01-01T00:00:00',
                }
            }

    return seeds, cleanups