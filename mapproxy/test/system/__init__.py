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
import os
import tempfile
import shutil

import pytest

from webtest import TestApp as TestApp_

from mapproxy.wsgiapp import make_wsgi_app


class TestApp(TestApp_):
    """
    Wraps webtest.TestApp and explicitly converts URLs to strings.
    Behavior changed with webtest from 1.2->1.3.
    """

    def get(self, url, *args, **kw):
        return TestApp_.get(self, str(url), *args, **kw)


def module_setup(test_config, config_file, with_cache_data=False):
    prepare_env(test_config, config_file, with_cache_data)
    create_app(test_config)


def prepare_env(test_config, config_file, with_cache_data=False):
    if "fixture_dir" not in test_config:
        test_config["fixture_dir"] = os.path.join(os.path.dirname(__file__), "fixture")

    fixture_layer_conf = os.path.join(test_config["fixture_dir"], config_file)

    if "base_dir" not in test_config:
        test_config["tmp_dir"] = tempfile.mkdtemp()
        test_config["base_dir"] = os.path.join(test_config["tmp_dir"], "etc")
        os.mkdir(test_config["base_dir"])
    test_config["config_file"] = os.path.join(test_config["base_dir"], config_file)
    test_config["cache_dir"] = os.path.join(test_config["base_dir"], "cache_data")
    shutil.copy(fixture_layer_conf, test_config["config_file"])
    if with_cache_data:
        shutil.copytree(
            os.path.join(test_config["fixture_dir"], "cache_data"),
            test_config["cache_dir"],
        )


def create_app(test_config):
    app = make_wsgi_app(test_config["config_file"], ignore_config_warnings=False)
    app.base_config.debug_mode = True
    test_config["app"] = TestApp(app, use_unicode=False)


def module_teardown(test_config):
    shutil.rmtree(test_config["base_dir"])
    if "tmp_dir" in test_config:
        shutil.rmtree(test_config["tmp_dir"])

    test_config.clear()


def make_base_config(test_config):

    def wrapped():
        if hasattr(test_config["app"], "base_config"):
            return test_config["app"].base_config
        return test_config["app"].app.base_config

    return wrapped


class SystemTest(object):

    def setup(self):
        self.app = self.config["app"]
        self.created_tiles = []
        self.base_config = make_base_config(self.config)

    def created_tiles_filenames(self):
        base_dir = self.base_config().cache.base_dir
        for filename in self.created_tiles:
            yield os.path.join(base_dir, filename)

    def _test_created_tiles(self):
        for filename in self.created_tiles_filenames():
            if not os.path.exists(filename):
                assert False, "didn't found tile " + filename

    def teardown(self):
        self._test_created_tiles()
        for filename in self.created_tiles_filenames():
            if os.path.exists(filename):
                os.remove(filename)


@pytest.mark.usefixtures("cache_dir")
class SysTest(object):
    """
    Baseclass for pytest-based system tests.
    Provides `app` fixture with a configured MapProxy instance, wrapped in
    webtest.TestApp.

    `app` is reused within each test class, `cache_dir` is cleaned with
    each test.
    """

    @pytest.fixture(scope="class")
    def app(self, base_dir, config_file):
        filename = base_dir.join(config_file)
        print("loading", filename)
        app = make_wsgi_app(filename.strpath, ignore_config_warnings=False)
        app.base_config.debug_mode = True
        return TestApp(app, use_unicode=False)

    @pytest.fixture(scope="class")
    def base_config(self, app):
        return app.app.base_config

    @pytest.fixture(scope="class")
    def base_dir(self, tmpdir_factory, config_file):
        dir = tmpdir_factory.mktemp("base_dir")

        fixture_dir = os.path.join(os.path.dirname(__file__), "fixture")
        fixture_layer_conf = os.path.join(fixture_dir, config_file)
        shutil.copy(fixture_layer_conf, dir.strpath)

        return dir

    @pytest.fixture(scope="function")
    def cache_dir(self, base_dir):
        """
        cache_dir fixture returns a fresh cache_data directory used by `app`.
        """
        cache_dir = base_dir.join("cache_data")
        if cache_dir.check():
            cache_dir.remove()

        yield cache_dir

        if cache_dir.check():
            cache_dir.remove()

    @pytest.fixture(scope="function")
    def fixture_cache_data(self, cache_dir):
        """
        fixture_cache_data ensures that the system/fixture files are copied into
        `cache_dir`.
        """
        fixture_dir = os.path.join(os.path.dirname(__file__), "fixture")
        shutil.copytree(os.path.join(fixture_dir, "cache_data"), cache_dir.strpath)
