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

from __future__ import with_statement, division

from mapproxy.test.system import module_setup, module_teardown, SystemTest
from nose.tools import eq_

test_config = {}

def setup_module():
    module_setup(test_config, 'layergroups.yaml')

def teardown_module():
    module_teardown(test_config)

TESTSERVER_ADDRESS = 'localhost', 42423
CAPABILITIES_REQ = "/service?request=GetCapabilities&service=WMS&Version=1.1.1"

class TestWMSAuth(SystemTest):
    config = test_config

    # ###
    # see mapproxy.test.unit.test_auth for WMS GetMap request tests
    # ###
    
    def test_capabilities_authorize_all(self):
        def auth(service, layers):
            eq_(len(layers), 7)
            return {'authorized': 'true'}
        
        resp = self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(xml.xpath('//Layer/Name/text()'), ['layer1', 'layer1a', 'layer1b', 'layer2', 'layer2a', 'layer2b', 'layer2b1'])

    def test_capabilities_authorize_none(self):
        def auth(service, layers):
            eq_(len(layers), 7)
            return {'authorized': 'false'}
        self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth}, status=403)

    def test_capabilities_authorize_partial(self):
        def auth(service, layers):
            eq_(len(layers), 7)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1a': {'map': True},
                    'layer2': {'map': True},
                    'layer2b': {'map': True},
                    'layer2b1': {'map': True},
                }
            }
        resp = self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        # layer1a not included cause root layer (layer1) is not permitted
        eq_(xml.xpath('//Layer/Name/text()'), ['layer2', 'layer2b', 'layer2b1'])
    
    def test_capabilities_authorize_partial_with_fi(self):
        def auth(service, layers):
            eq_(len(layers), 7)
            return {
                'authorized': 'partial',
                'layers': {
                    'layer1': {'map': True},
                    'layer1a': {'map': True},
                    'layer2': {'map': True, 'featureinfo': True},
                }
            }
        resp = self.app.get(CAPABILITIES_REQ, extra_environ={'mapproxy.authorize': auth})
        xml = resp.lxml
        eq_(xml.xpath('//Layer/Name/text()'), ['layer1', 'layer1a', 'layer2'])
    

    