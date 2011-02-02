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
        