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

import os
from mapproxy.util.ext.tempita import Template, bunch

__all__ = ['Template', 'bunch', 'template_loader']


def template_loader(module_file, location='templates', namespace={}):
    template_dir = os.path.join(os.path.dirname(module_file), location)
    
    class loader(object):
        def __call__(self, name, from_template=None, default_inherit=None):
            return Template.from_filename(os.path.join(template_dir, name), namespace=namespace,
                                          default_inherit=default_inherit, get_template=self)
    return loader()
