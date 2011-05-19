# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

from mapproxy.util.ext.dictspec.validator import validate, ValidationError
from mapproxy.util.ext.dictspec.spec import one_off, anything, number
from mapproxy.util.ext.dictspec.spec import required

from mapproxy.config.spec import coverage

def validate_seed_conf(conf_dict):
    """
    Validate `conf_dict` agains seed.yaml spec.
    Returns lists with errors. List is empty when no errors where found.
    """
    try:
        validate(seed_yaml_spec, conf_dict)
    except ValidationError, ex:
        return ex.errors, ex.informal_only
    else:
        return [], True

time_spec = {
    'seconds': number(),
    'minutes': number(),
    'hours': number(),
    'days': number(),
    'weeks': number(),
    'time': anything(),
}

from_to_spec = {
    'from': number(),
    'to': number(),
}

seed_yaml_spec = {
    'coverages': {
        anything(): coverage,
    },
    'seeds': {
        anything(): {
            required('caches'): [str()],
            'grids': [str()],
            'coverages': [str()],
            'refresh_before': time_spec,
            'levels': one_off([int()], from_to_spec),
            'resolutions': one_off([int()], from_to_spec),
        },
    },
    'cleanups': {
        anything(): {
            required('caches'): [str()],
            'grids': [str()],
            'coverages': [str()],
            'remove_before': time_spec,
            'levels': one_off([int()], from_to_spec),
            'resolutions': one_off([int()], from_to_spec),
        }
    },
}
