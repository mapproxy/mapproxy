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

import logging
logger = logging.getLogger('mapproxy.source.request')

def log_request(url, status, result=None, size=None, method='GET', duration=None):
    if not logger.isEnabledFor(logging.INFO):
        return
    
    if not size and result is not None:
        size = result.headers.get('Content-length')
    if size:
        size = '%.1f' % (int(size)/1024.0, )
    else:
        size = '-'
    if not status:
        status = '-'
    duration = '%d' % (duration*1000) if duration else '-'
    logger.info('%s %s %s %s %s', method, url.replace(' ', ''), status, size, duration)
    