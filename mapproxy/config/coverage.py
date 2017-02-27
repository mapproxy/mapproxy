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
from mapproxy.util.geom import (
    load_datasource,
    load_ogr_datasource,
    load_polygons,
    load_expire_tiles,
    require_geom_support,
    build_multipolygon,
)
from mapproxy.util.coverage import (
    coverage,
    diff_coverage,
    union_coverage,
    intersection_coverage,
)
from mapproxy.compat import string_type

bbox_string_re = re.compile(r'[-+]?\d*.?\d+,[-+]?\d*.?\d+,[-+]?\d*.?\d+,[-+]?\d*.?\d+')

def load_coverage(conf, base_path=None):
    clip = False
    if 'clip' in conf:
        clip = conf['clip']

    if 'union' in conf:
        parts = []
        for cov in conf['union']:
            parts.append(load_coverage(cov))
        return union_coverage(parts, clip=clip)
    elif 'intersection' in conf:
        parts = []
        for cov in conf['intersection']:
            parts.append(load_coverage(cov))
        return intersection_coverage(parts, clip=clip)
    elif 'difference' in conf:
        parts = []
        for cov in conf['difference']:
            parts.append(load_coverage(cov))
        return diff_coverage(parts, clip=clip)
    elif 'ogr_datasource' in conf:
        require_geom_support()
        srs = conf['ogr_srs']
        datasource = conf['ogr_datasource']
        if not re.match(r'^\w{2,}:', datasource):
            # looks like a file and not PG:, MYSQL:, etc
            # make absolute path
            datasource = abspath(datasource, base_path=base_path)
        where = conf.get('ogr_where', None)
        geom = load_ogr_datasource(datasource, where)
        bbox, geom = build_multipolygon(geom, simplify=True)
    elif 'polygons' in conf:
        require_geom_support()
        srs = conf['polygons_srs']
        geom = load_polygons(abspath(conf['polygons'], base_path=base_path))
        bbox, geom = build_multipolygon(geom, simplify=True)
    elif 'bbox' in conf:
        srs = conf.get('bbox_srs') or conf['srs']
        bbox = conf['bbox']
        if isinstance(bbox, string_type):
            bbox = [float(x) for x in bbox.split(',')]
        geom = None
    elif 'datasource' in conf:
        require_geom_support()
        datasource = conf['datasource']
        srs = conf['srs']
        if isinstance(datasource, (list, tuple)):
            bbox = datasource
            geom = None
        elif bbox_string_re.match(datasource):
            bbox = [float(x) for x in datasource.split(',')]
            geom = None
        else:
            if not re.match(r'^\w{2,}:', datasource):
                # looks like a file and not PG:, MYSQL:, etc
                # make absolute path
                datasource = abspath(datasource, base_path=base_path)
            where = conf.get('where', None)
            geom = load_datasource(datasource, where)
            bbox, geom = build_multipolygon(geom, simplify=True)
    elif 'expire_tiles' in conf:
        require_geom_support()
        filename = abspath(conf['expire_tiles'])
        geom = load_expire_tiles(filename)
        _, geom = build_multipolygon(geom, simplify=False)
        return coverage(geom, SRS(3857))
    else:
        return None

    return coverage(geom or bbox, SRS(srs), clip=clip)
