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

from copy import copy
from mapproxy.compat import iteritems

__all__ = ['update_config', 'MapProxyYAMLDumper']

def update_config(conf, overwrites):
    wildcard_keys = []
    for k, v in iteritems(overwrites):
        if k == '__all__':
            continue
        if  k.startswith('___') or k.endswith('___'):
            wildcard_keys.append(k)
            continue

        if k.endswith('__extend__'):
            k = k[:-len('__extend__')]
            if k not in conf:
                conf[k] = v
            elif isinstance(v, list):
                conf[k].extend(v)
            else:
                raise ValueError('cannot extend non-list:', v)
        elif k not in conf:
            conf[k] = copy(v)
        else:
            if isinstance(conf[k], dict) and isinstance(v, dict):
                conf[k] = update_config(conf[k], v)
            else:
                conf[k] = copy(v)

    if '__all__' in overwrites:
        v = overwrites['__all__']
        for conf_k, conf_v in iteritems(conf):
            if isinstance(conf_v, dict):
                conf[conf_k] = update_config(conf_v, v)
            else:
                conf[conf_k] = v

    if wildcard_keys:
        for key in wildcard_keys:
            v = overwrites[key]
            if key.startswith('___'):
                key = key[3:]
                key_check = lambda x: x.endswith(key)
            else:
                key = key[:-3]
                key_check = lambda x: x.startswith(key)
            for conf_k, conf_v in iteritems(conf):
                if not key_check(conf_k):
                    continue
                if isinstance(conf_v, dict):
                    conf[conf_k] = update_config(conf_v, v)
                else:
                    conf[conf_k] = v

    return conf


from yaml.serializer import Serializer
from yaml.nodes import ScalarNode, SequenceNode, MappingNode
from yaml.emitter import Emitter
from yaml.representer import SafeRepresenter
from yaml.resolver import Resolver

class _MixedFlowSortedSerializer(Serializer):
    def serialize_node(self, node, parent, index):
        # reset any anchors
        if parent is None:
            for k in self.anchors:
                self.anchors[k] = None
        self.serialized_nodes = {}

        if isinstance(node, SequenceNode) and all(isinstance(item, ScalarNode) for item in node.value):
            node.flow_style = True
        elif isinstance(node, MappingNode):
            node.value.sort(key=lambda x: x[0].value)
        return Serializer.serialize_node(self, node, parent, index)

class _EmptyNoneRepresenter(SafeRepresenter):
    def represent_none(self, data):
        return self.represent_scalar(u'tag:yaml.org,2002:null',
                u'')
_EmptyNoneRepresenter.add_representer(type(None), _EmptyNoneRepresenter.represent_none)

class MapProxyYAMLDumper(Emitter, _MixedFlowSortedSerializer, _EmptyNoneRepresenter, Resolver):
    """
    YAML dumper that uses block style by default, except for
    node-only sequences. Also sorts dicts by key, prevents `none`
    for empty entries and prevents any anchors.
    """
    def __init__(self, stream,
            default_style=None, default_flow_style=False,
            canonical=None, indent=None, width=None,
            allow_unicode=None, line_break=None,
            encoding=None, explicit_start=None, explicit_end=None,
            version=None, tags=None, sort_keys=None):
        Emitter.__init__(self, stream, canonical=canonical,
                indent=indent, width=width,
                allow_unicode=allow_unicode, line_break=line_break)
        Serializer.__init__(self, encoding=encoding,
                explicit_start=explicit_start, explicit_end=explicit_end,
                version=version, tags=tags)
        _EmptyNoneRepresenter.__init__(self, default_style=default_style,
                default_flow_style=default_flow_style)
        Resolver.__init__(self)

from mapproxy.request.base import BaseRequest, url_decode
from mapproxy.client.http import open_url
from mapproxy.compat.modules import urlparse

def wms_capapilities_url(url):
    parsed_url = urlparse.urlparse(url)
    base_req = BaseRequest(
        url=url.split('?', 1)[0],
        param=url_decode(parsed_url.query),
    )

    base_req.params['service'] = 'WMS'
    if not base_req.params['version']:
        base_req.params['version'] = '1.1.1'
    base_req.params['request'] = 'GetCapabilities'
    return base_req.complete_url

def download_capabilities(url):
    capabilities_url = wms_capapilities_url(url)
    return open_url(capabilities_url)

