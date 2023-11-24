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

from __future__ import division

import io
import os
import shutil

import pytest

from mapproxy.multiapp import make_wsgi_app

from mapproxy.test.system import SysTest, WSGITestApp


class TestMultiapp(SysTest):

    @pytest.fixture(scope="class")
    def app(self, base_dir):
        app = make_wsgi_app(base_dir.strpath, allow_listing=False)
        return WSGITestApp(app, use_unicode=False)

    @pytest.fixture(scope="class")
    def base_dir(self, tmpdir_factory):
        dir = tmpdir_factory.mktemp("base_dir")

        fixture_dir = os.path.join(os.path.dirname(__file__), "fixture")
        shutil.copy(os.path.join(fixture_dir, "multiapp1.yaml"), dir.strpath)
        shutil.copy(os.path.join(fixture_dir, "multiapp2.yaml"), dir.strpath)

        return dir

    def test_index_without_list(self, app):
        resp = app.get("/")
        assert "MapProxy" in resp
        assert "multiapp1" not in resp

    def test_index_with_list(self, app):
        try:
            app.app.list_apps = True
            resp = app.get("/")
            assert "MapProxy" in resp
            assert "multiapp1" in resp
        finally:
            app.app.list_apps = False

    def test_unknown_app(self, app):
        app.get("/unknownapp", status=404)
        # assert status == 404 Not Found in app.get

    def test_known_app(self, app):
        resp = app.get("/multiapp1")
        assert "demo" in resp

    def test_reloading(self, app, base_dir):
        resp = app.get("/multiapp1")
        assert "demo" in resp
        app_config = base_dir.join("multiapp1.yaml").strpath

        replace_text_in_file(app_config, "  demo:", "  #demo:", ts_delta=5)

        resp = app.get("/multiapp1")
        assert "demo" not in resp

        replace_text_in_file(app_config, "  #demo:", "  demo:", ts_delta=10)

        resp = app.get("/multiapp1")
        assert "demo" in resp


def replace_text_in_file(filename, old, new, ts_delta=2):
    text = io.open(filename, encoding="utf-8").read()
    text = text.replace(old, new)
    io.open(filename, "w", encoding="utf-8").write(text)

    # file timestamps are not precise enough (1sec)
    # add larger delta to force reload
    m_time = os.path.getmtime(filename)
    os.utime(filename, (m_time + ts_delta, m_time + ts_delta))
