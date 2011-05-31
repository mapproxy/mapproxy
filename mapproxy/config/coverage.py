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

import re

from mapproxy.srs import SRS
from mapproxy.config import abspath
from mapproxy.util.geom import load_datasource, load_polygons, require_geom_support, coverage

def load_coverage(conf):
    if 'ogr_datasource' in conf:
        require_geom_support()
        srs = conf['ogr_srs']
        datasource = conf['ogr_datasource']
        if not re.match(r'^\w{2,}:', datasource):
            # looks like a file and not PG:, MYSQL:, etc
            # make absolute path
            datasource = abspath(datasource)
        where = conf.get('ogr_where', None)
        bbox, geom = load_datasource(datasource, where)
    elif 'polygons' in conf:
        require_geom_support()
        srs = conf['polygons_srs']
        bbox, geom = load_polygons(abspath(conf['polygons']))
    else:
        srs = conf['bbox_srs']
        bbox = conf['bbox']
        if isinstance(bbox, basestring):
            bbox = map(float, bbox.split(','))
        geom = None

    return coverage(geom or bbox, SRS(srs))
        