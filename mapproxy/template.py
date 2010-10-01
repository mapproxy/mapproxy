# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
