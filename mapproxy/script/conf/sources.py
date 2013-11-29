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

from mapproxy.srs import SRS

import logging

def sources(cap):
    sources = {}
    for layer in cap.layers_list():
        name, conf = for_layer(cap, layer)
        sources[name+'_wms'] = conf

    return sources

_checked_srs = {}

def check_srs(srs):
    if srs not in _checked_srs:
        try:
            SRS(srs)
            _checked_srs[srs] = True
        except Exception as ex:
            logging.getLogger(__name__).warn('unable to initialize srs for %s: %s', srs, ex)
            _checked_srs[srs] = False

    return _checked_srs[srs]

def for_layer(cap, layer):
    source = {'type': 'wms'}

    req = {
        'url': layer['url'],
        'layers': layer['name'],
    }

    if not layer['opaque']:
        req['transparent'] = True

    wms_opts = {}
    if cap.version != '1.1.1':
        wms_opts['version'] = cap.version
    if layer['queryable']:
        wms_opts['featureinfo'] = True
    if layer['legend']:
        wms_opts['legendurl'] = layer['legend']['url']
    if wms_opts:
        source['wms_opts'] = wms_opts

    source['req'] = req

    source['supported_srs'] = []
    for srs in layer['srs']:
        if check_srs(srs):
            source['supported_srs'].append(srs)
    source['supported_srs'].sort()

    if layer['llbbox']:
        source['coverage'] = {
            'srs': 'EPSG:4326',
            'bbox': layer['llbbox'],
        }

    res_hint = layer['res_hint']
    if res_hint:
        if res_hint[0]:
            source['min_res'] = res_hint[0]
        if res_hint[1]:
            source['max_res'] = res_hint[1]

    return layer['name'], source


