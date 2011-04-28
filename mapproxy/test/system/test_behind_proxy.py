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
from nose.tools import eq_, assert_almost_equal

from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config

test_config = {}
base_config = make_base_config(test_config)

def setup_module():
    module_setup(test_config, 'layer.yaml', with_cache_data=True)

def teardown_module():
    module_teardown(test_config)


class TestWMSBehindProxy(SystemTest):
    """
    Check WMS OnlineResources for requests behind HTTP proxies.
    """
    config = test_config

    def test_no_proxy(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&VERSION=1.1.0')
        assert '"http://localhost/service' in resp

    def test_with_script_name(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&VERSION=1.1.0', extra_environ={'HTTP_X_SCRIPT_NAME': '/foo'})
        assert '"http://localhost/service' not in resp
        assert '"http://localhost/foo/service' in resp

    def test_with_host(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&VERSION=1.1.0', extra_environ={'HTTP_HOST': 'example.org'})
        assert '"http://localhost/service' not in resp
        assert '"http://example.org/service' in resp

    def test_with_host_and_script_name(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
            '&VERSION=1.1.0', extra_environ={'HTTP_X_SCRIPT_NAME': '/foo', 'HTTP_HOST': 'example.org'})
        assert '"http://localhost/service' not in resp
        assert '"http://example.org/foo/service' in resp

    def test_with_forwarded_host(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&VERSION=1.1.0', extra_environ={'HTTP_X_FORWARDED_HOST': 'example.org'})
        assert '"http://localhost/service' not in resp
        assert '"http://example.org/service' in resp

    def test_with_forwarded_host_and_script_name(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
            '&VERSION=1.1.0', extra_environ={'HTTP_X_FORWARDED_HOST': 'example.org', 'HTTP_X_SCRIPT_NAME': '/foo'})
        assert '"http://localhost/service' not in resp
        assert '"http://example.org/foo/service' in resp

    def test_with_forwarded_proto_and_script_name_and_host(self):
        resp = self.app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
            '&VERSION=1.1.0', extra_environ={
                'HTTP_X_FORWARDED_PROTO': 'https',
                'HTTP_X_SCRIPT_NAME': '/foo',
                'HTTP_HOST': 'example.org:443'
            })
        assert '"http://localhost/service' not in resp
        assert '"https://example.org/foo/service' in resp

