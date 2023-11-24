# -:- encoding: utf-8 -:-
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
import time

import pytest

from mapproxy.multiapp import DirectoryConfLoader, MultiMapProxy


class TestDirectoryConfLoader(object):

    @pytest.fixture
    def loader(self, tmpdir):
        return DirectoryConfLoader(tmpdir.strpath)

    def make_conf_file(self, dir, name):
        conf_file_name = os.path.join(dir, name)
        with open(conf_file_name, "wb"):
            pass
        return conf_file_name

    def test_available_apps_empty(self, loader):
        assert loader.available_apps() == []

    def test_available_apps(self, loader):
        self.make_conf_file(loader.base_dir, "foo.yaml")
        self.make_conf_file(loader.base_dir, "bar.yaml")
        assert set(loader.available_apps()) == set(["foo", "bar"])
        self.make_conf_file(loader.base_dir, "bazz.yaml")
        assert set(loader.available_apps()) == set(["foo", "bar", "bazz"])

    def test_app_available(self, loader):
        self.make_conf_file(loader.base_dir, "foo.yaml")
        assert loader.app_available("foo")
        assert not loader.app_available("bar")

    def test_app_conf(self, loader):
        foo_conf_file = self.make_conf_file(loader.base_dir, "foo.yaml")
        app_conf = loader.app_conf("foo")
        assert app_conf["mapproxy_conf"] == foo_conf_file

    def test_app_conf_unknown_app(self, loader):
        app_conf = loader.app_conf("foo")
        assert app_conf is None

    def test_needs_reload(self, loader):
        foo_conf_file = self.make_conf_file(loader.base_dir, "foo.yaml")
        mtime = os.path.getmtime(foo_conf_file)
        timestamps = {foo_conf_file: mtime}
        assert loader.needs_reload("foo", timestamps) == False

        timestamps[foo_conf_file] -= 10
        assert loader.needs_reload("foo", timestamps) == True

    def test_custom_suffix(self, loader):
        self.make_conf_file(loader.base_dir, "foo.conf")
        loader = DirectoryConfLoader(loader.base_dir, suffix=".conf")
        assert loader.app_available("foo")


minimal_mapproxy_conf = b"""
services:
  wms:

layers:
  - name: mylayer
    title: My Layer
    sources: [mysource]

sources:
  mysource:
    type: wms
    req:
      url: http://example.org/service?
      layers: foo,bar
"""


class DummyReq(object):
    script_url = ""


class TestMultiMapProxy(object):

    @pytest.fixture
    def loader(self, tmpdir):
        return DirectoryConfLoader(tmpdir.strpath)

    def make_conf_file(self, dir, name):
        app_conf_file_name = os.path.join(dir, name)
        with open(app_conf_file_name, "wb") as f:
            f.write(minimal_mapproxy_conf)
        return app_conf_file_name

    def test_listing_with_apps(self, loader):
        self.make_conf_file(loader.base_dir, "foo.yaml")
        mmp = MultiMapProxy(loader, list_apps=True)
        resp = mmp.index_list(DummyReq())
        assert "foo" in resp.response

    def test_listing_without_apps(self, loader):
        self.make_conf_file(loader.base_dir, "foo.yaml")
        mmp = MultiMapProxy(loader)
        resp = mmp.index_list(DummyReq())
        assert "foo" not in resp.response
        assert mmp.proj_app("foo") is not None

    def test_cached_app_loading(self, loader):
        self.make_conf_file(loader.base_dir, "foo.yaml")
        mmp = MultiMapProxy(loader)
        app1 = mmp.proj_app("foo")
        app2 = mmp.proj_app("foo")

        # app is cached
        assert app1 is app2

    def test_app_reloading(self, loader):
        app_conf_file_name = self.make_conf_file(loader.base_dir, "foo.yaml")
        mmp = MultiMapProxy(loader)
        app = mmp.proj_app("foo")

        # touch configuration file
        os.utime(app_conf_file_name, (time.time() + 10, time.time() + 10))
        # app was reloaded
        assert app is not mmp.proj_app("foo")

    def test_app_unloading(self, loader):
        self.make_conf_file(loader.base_dir, "app1.yaml")
        self.make_conf_file(loader.base_dir, "app2.yaml")
        self.make_conf_file(loader.base_dir, "app3.yaml")
        mmp = MultiMapProxy(loader, app_cache_size=2)

        app1 = mmp.proj_app("app1")
        app2 = mmp.proj_app("app2")

        # lru cache [app1, app2]
        assert app1 is mmp.proj_app("app1")
        assert app2 is mmp.proj_app("app2")

        # lru cache [app1, app2]
        app3 = mmp.proj_app("app3")
        # lru cache [app2, app3]
        assert app3 is mmp.proj_app("app3")
        assert app2 is mmp.proj_app("app2")
        assert app1 is not mmp.proj_app("app1")

        # lru cache [app2, app1]
        assert app3 is not mmp.proj_app("app3")
