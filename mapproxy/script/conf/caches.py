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

def caches(cap, sources, srs_grids):
    caches = {}
    for name, source in iteritems(sources):
        conf = for_source(name, source, srs_grids)
        if not conf:
            continue
        caches[name[:-len('_wms')] + '_cache'] = conf

    return caches

def for_source(name, source, srs_grids):
    cache = {
        'sources': [name]
    }

    grids = []
    for srs in source['supported_srs']:
        if srs in srs_grids:
            grids.append(srs_grids[srs])

    if not grids:
        return None

    cache['grids'] = grids

    return cache

