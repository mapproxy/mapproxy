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

def layers(cap, caches):
    return [_layer(cap.layers(), caches)]

def _layer(layer, caches):
    name, conf = for_layer(layer, caches)
    child_layers = []

    for child_layer in layer['layers']:
        child_layers.append(_layer(child_layer, caches))

    if child_layers:
        conf['layers'] = child_layers

    return conf


def for_layer(layer, caches):
    conf = {
        'title': layer['title'],
    }

    if layer['name']:
        conf['name'] = layer['name']

        if layer['name'] + '_cache' in caches:
            conf['sources'] = [layer['name'] + '_cache']
        else:
            conf['sources'] = [layer['name'] + '_wms']

    md = {}
    if layer['abstract']:
        md['abstract'] = layer['abstract']

    if md:
        conf['md'] = md

    return layer['name'], conf

