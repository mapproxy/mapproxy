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
Configuration loading and system initializing.
"""
from __future__ import with_statement

import logging
log = logging.getLogger(__name__)

from mapproxy.request.wms import WMS100MapRequest, WMS111MapRequest, WMS130MapRequest,\
                                  WMS100FeatureInfoRequest, WMS111FeatureInfoRequest,\
                                  WMS130FeatureInfoRequest


wms_version_requests = {'1.0.0': {'featureinfo': WMS100FeatureInfoRequest,
                                  'map': WMS100MapRequest,},
                        '1.1.1': {'featureinfo': WMS111FeatureInfoRequest,
                                  'map': WMS111MapRequest,},
                        '1.3.0': {'featureinfo': WMS130FeatureInfoRequest,
                                  'map': WMS130MapRequest,},
                       }

def create_request(req_data, param, req_type='map', version='1.1.1'):
    url = req_data['url']
    req_data = req_data.copy()
    del req_data['url']
    if 'request_format' in param:
        req_data['format'] = param['request_format']
    else:
        req_data['format'] = param['format']
    # req_data['bbox'] = param['bbox']
    # if isinstance(req_data['bbox'], types.ListType):
    #     req_data['bbox'] = ','.join(str(x) for x in req_data['bbox'])
    # req_data['srs'] = param['srs']
    
    return wms_version_requests[version][req_type](url=url, param=req_data)
