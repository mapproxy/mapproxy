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
