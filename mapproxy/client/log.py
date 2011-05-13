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
    