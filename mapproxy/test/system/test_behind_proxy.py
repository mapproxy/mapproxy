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

from __future__ import division

import pytest

from mapproxy.test.system import SysTest


class TestWMSBehindProxy(SysTest):
    """
    Check WMS OnlineResources for requests behind HTTP proxies.
    """
    @pytest.fixture(scope='class')
    def config_file(self):
        return 'layer.yaml'

    def test_no_proxy(self, app):
        resp = app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&VERSION=1.1.0')
        assert '"http://localhost/service' in resp

    def test_with_script_name(self, app):
        resp = app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&VERSION=1.1.0', extra_environ={'HTTP_X_SCRIPT_NAME': '/foo'})
        assert '"http://localhost/service' not in resp
        assert '"http://localhost/foo/service' in resp

    def test_with_host(self, app):
        resp = app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&VERSION=1.1.0', extra_environ={'HTTP_HOST': 'example.org'})
        assert '"http://localhost/service' not in resp
        assert '"http://example.org/service' in resp

    def test_with_host_and_script_name(self, app):
        resp = app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
            '&VERSION=1.1.0', extra_environ={'HTTP_X_SCRIPT_NAME': '/foo', 'HTTP_HOST': 'example.org'})
        assert '"http://localhost/service' not in resp
        assert '"http://example.org/foo/service' in resp

    def test_with_forwarded_host(self, app):
        resp = app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
                            '&VERSION=1.1.0', extra_environ={'HTTP_X_FORWARDED_HOST': 'example.org, bar.org'})
        assert '"http://localhost/service' not in resp
        assert '"http://example.org/service' in resp

    def test_with_forwarded_host_and_script_name(self, app):
        resp = app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
            '&VERSION=1.1.0', extra_environ={'HTTP_X_FORWARDED_HOST': 'example.org', 'HTTP_X_SCRIPT_NAME': '/foo'})
        assert '"http://localhost/service' not in resp
        assert '"http://example.org/foo/service' in resp

    def test_with_forwarded_proto_and_script_name_and_host(self, app):
        resp = app.get('http://localhost/service?SERVICE=WMS&REQUEST=GetCapabilities'
            '&VERSION=1.1.0', extra_environ={
                'HTTP_X_FORWARDED_PROTO': 'https',
                'HTTP_X_SCRIPT_NAME': '/foo',
                'HTTP_HOST': 'example.org:443'
            })
        assert '"http://localhost/service' not in resp
        assert '"https://example.org/foo/service' in resp

