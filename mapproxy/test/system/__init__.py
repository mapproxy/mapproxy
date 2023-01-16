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
import shutil

import pytest

from webtest import TestApp as _TestApp

from mapproxy.wsgiapp import make_wsgi_app


class WSGITestApp(_TestApp):
    """
    Wraps webtest.TestApp and explicitly converts URLs to strings.
    Behavior changed with webtest from 1.2->1.3.
    """

    def get(self, url, *args, **kw):
        return _TestApp.get(self, str(url), *args, **kw)


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
    def app(self, base_dir, config_file, additional_files):
        filename = base_dir.join(config_file)
        app = make_wsgi_app(filename.strpath, ignore_config_warnings=False)
        app.base_config.debug_mode = True
        return WSGITestApp(app, use_unicode=False)

    @pytest.fixture(scope="class")
    def additional_files(self, base_dir):
        return

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
