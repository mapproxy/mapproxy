# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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
Loading of template files (e.g. capability documents)
"""
try:
    import importlib_resources
except ImportError:
    from importlib import resources as importlib_resources  # type: ignore
import os
from mapproxy.util.ext.tempita import Template, bunch
from mapproxy.config.config import base_config

__all__ = ['Template', 'bunch', 'template_loader']


def template_loader(module_name, location='templates', namespace={}):

    class loader(object):
        def __call__(self, name, from_template=None, default_inherit=None):
            if os.path.isabs(name):
                template_file = name
            elif base_config().template_dir:
                template_file = os.path.join(base_config().template_dir, name)
            else:
                template_file = importlib_resources.files(module_name).joinpath(location).joinpath(name)
            return Template.from_filename(template_file, namespace=namespace, encoding='utf-8',
                                          default_inherit=default_inherit, get_template=self)
    return loader()


class recursive_bunch(bunch):

    def __getitem__(self, key):
        if 'default' in self:
            try:
                value = dict.__getitem__(self, key)
            except KeyError:
                value = dict.__getitem__(self, 'default')
        else:
            value = dict.__getitem__(self, key)
        if isinstance(value, dict):
            value = recursive_bunch(**value)
        return value
