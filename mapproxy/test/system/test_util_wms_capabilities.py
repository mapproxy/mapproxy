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

import os

import pytest

from mapproxy.client.http import HTTPClient
from mapproxy.script.wms_capabilities import wms_capabilities_command
from mapproxy.test.http import mock_httpd
from mapproxy.test.helper import capture


TESTSERVER_ADDRESS = ("127.0.0.1", 56413)
TESTSERVER_URL = "http://%s:%s" % TESTSERVER_ADDRESS
CAPABILITIES111_FILE = os.path.join(
    os.path.dirname(__file__), "fixture", "util_wms_capabilities111.xml"
)
CAPABILITIES130_FILE = os.path.join(
    os.path.dirname(__file__), "fixture", "util_wms_capabilities130.xml"
)
SERVICE_EXCEPTION_FILE = os.path.join(
    os.path.dirname(__file__), "fixture", "util_wms_capabilities_service_exception.xml"
)


class TestUtilWMSCapabilities(object):

    def setup(self):
        self.client = HTTPClient()
        self.args = ["command_dummy", "--host", TESTSERVER_URL + "/service"]

    def test_http_error(self):
        self.args = ["command_dummy", "--host", "http://foo.doesnotexist"]
        with capture() as (out, err):
            with pytest.raises(SystemExit):
                wms_capabilities_command(self.args)
        assert err.getvalue().startswith("ERROR:")

        self.args[2] = "/no/valid/url"
        with capture() as (out, err):
            with pytest.raises(SystemExit):
                wms_capabilities_command(self.args)
        assert err.getvalue().startswith("ERROR:")

    def test_request_not_parsable(self):
        with mock_httpd(
            TESTSERVER_ADDRESS,
            [
                (
                    {
                        "path": "/service?request=GetCapabilities&version=1.1.1&service=WMS",
                        "method": "GET",
                    },
                    {"status": "200", "body": ""},
                )
            ],
        ):
            with capture() as (out, err):
                with pytest.raises(SystemExit):
                    wms_capabilities_command(self.args)
            error_msg = err.getvalue().rsplit("-" * 80, 1)[1].strip()
            assert error_msg.startswith("Could not parse the document")

    def test_service_exception(self):
        self.args = [
            "command_dummy",
            "--host",
            TESTSERVER_URL + "/service?request=GetCapabilities",
        ]
        with open(SERVICE_EXCEPTION_FILE, "rb") as fp:
            capabilities_doc = fp.read()
            with mock_httpd(
                TESTSERVER_ADDRESS,
                [
                    (
                        {
                            "path": "/service?request=GetCapabilities&version=1.1.1&service=WMS",
                            "method": "GET",
                        },
                        {"status": "200", "body": capabilities_doc},
                    )
                ],
            ):
                with capture() as (out, err):
                    with pytest.raises(SystemExit):
                        wms_capabilities_command(self.args)
                error_msg = err.getvalue().rsplit("-" * 80, 1)[1].strip()
                assert "Not a capabilities document" in error_msg

    def test_parse_capabilities(self):
        self.args = [
            "command_dummy",
            "--host",
            TESTSERVER_URL + "/service?request=GetCapabilities",
            "--version",
            "1.1.1",
        ]
        with open(CAPABILITIES111_FILE, "rb") as fp:
            capabilities_doc = fp.read()
            with mock_httpd(
                TESTSERVER_ADDRESS,
                [
                    (
                        {
                            "path": "/service?request=GetCapabilities&version=1.1.1&service=WMS",
                            "method": "GET",
                        },
                        {"status": "200", "body": capabilities_doc},
                    )
                ],
            ):
                with capture() as (out, err):
                    wms_capabilities_command(self.args)
                lines = out.getvalue().split("\n")
                assert lines[1].startswith("Capabilities Document Version 1.1.1")

    def test_parse_130capabilities(self):
        self.args = [
            "command_dummy",
            "--host",
            TESTSERVER_URL + "/service?request=GetCapabilities",
            "--version",
            "1.3.0",
        ]
        with open(CAPABILITIES130_FILE, "rb") as fp:
            capabilities_doc = fp.read()
            with mock_httpd(
                TESTSERVER_ADDRESS,
                [
                    (
                        {
                            "path": "/service?request=GetCapabilities&version=1.3.0&service=WMS",
                            "method": "GET",
                        },
                        {"status": "200", "body": capabilities_doc},
                    )
                ],
            ):
                with capture() as (out, err):
                    wms_capabilities_command(self.args)
                lines = out.getvalue().split("\n")
                assert lines[1].startswith("Capabilities Document Version 1.3.0")

    def test_key_error(self):
        self.args = [
            "command_dummy",
            "--host",
            TESTSERVER_URL + "/service?request=GetCapabilities",
        ]
        with open(CAPABILITIES111_FILE, "rb") as fp:
            capabilities_doc = fp.read()
            capabilities_doc = capabilities_doc.replace(b"minx", b"foo")
            with mock_httpd(
                TESTSERVER_ADDRESS,
                [
                    (
                        {
                            "path": "/service?request=GetCapabilities&version=1.1.1&service=WMS",
                            "method": "GET",
                        },
                        {"status": "200", "body": capabilities_doc},
                    )
                ],
            ):
                with capture() as (out, err):
                    with pytest.raises(SystemExit):
                        wms_capabilities_command(self.args)

                assert err.getvalue().startswith("XML-Element has no such attribute")
