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

"""
Wrapper service handler for all OWS services (/service?).
"""

class OWSServer(object):
    """
    Wraps all OWS services (/service?) and dispatches requests
    based on the ``services`` query argument.
    """
    names = ('service', )
    
    def __init__(self, services):
        self.services = {}
        for service in services:
            self.services[service.service] = service
    
    def handle(self, req):
        service = req.args.get('service', 'wms').lower()
        if service not in self.services:
            # TODO
            return
        
        return self.services[service].handle(req)
        