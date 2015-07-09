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

"""
Wrapper service handler for all OWS services (/service?).
"""

class OWSServer(object):
    """
    Wraps all OWS services (/service?, /ows?, /wms?, /wmts?) and dispatches requests
    based on the ``services`` query argument.
    """

    def __init__(self, services):
        self.names = ['service', 'ows']
        self.services = {}
        for service in services:
            if service.service == 'wms' and 'wms' not in self.names:
                self.names.append('wms')
            self.services[service.service] = service

    def handle(self, req):
        service = req.args.get('service', 'wms').lower()
        assert service in self.services

        return self.services[service].handle(req)
