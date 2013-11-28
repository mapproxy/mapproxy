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

from __future__ import with_statement, division
import io
import os
import tempfile
import shutil
from webtest import TestApp
from mapproxy.multiapp import app_factory

def module_setup(test_config, config_files):
    fixture_dir = os.path.join(os.path.dirname(__file__), 'fixture')

    test_config['base_dir'] = tempfile.mkdtemp()
    test_config['config_files'] = []

    for config_file in config_files:
        config_file_src = os.path.join(fixture_dir, config_file)
        config_file_dst = os.path.join(test_config['base_dir'], config_file)
        shutil.copy(config_file_src, config_file_dst)
        test_config['config_files'].append(config_file_dst)

    app = app_factory({}, config_dir=test_config['base_dir'], allow_listing=False)
    test_config['multiapp'] = app
    test_config['app'] = TestApp(app, use_unicode=False)

def module_teardown(test_config):
    shutil.rmtree(test_config['base_dir'])
    test_config.clear()


test_config = {}

def setup_module():
    module_setup(test_config, ['multiapp1.yaml', 'multiapp2.yaml'])

def teardown_module():
    module_teardown(test_config)

class TestMultiapp(object):
    def setup(self):
        self.multiapp = test_config['multiapp']
        self.app = test_config['app']

    def test_index_without_list(self):
        resp = self.app.get('/')
        assert 'MapProxy' in resp
        assert 'multiapp1' not in resp

    def test_index_with_list(self):
        try:
            self.multiapp.list_apps = True
            resp = self.app.get('/')
            assert 'MapProxy' in resp
            assert 'multiapp1' in resp
        finally:
            self.multiapp.list_apps = False

    def test_unknown_app(self):
        self.app.get('/unknownapp', status=404)
        # assert status == 404 Not Found in app.get

    def test_known_app(self):
        resp = self.app.get('/multiapp1')
        assert 'demo' in resp

    def test_reloading(self):
        resp = self.app.get('/multiapp1')
        assert 'demo' in resp
        app_config = test_config['config_files'][0]

        replace_text_in_file(app_config, '  demo:', '  #demo:', ts_delta=5)

        resp = self.app.get('/multiapp1')
        assert 'demo' not in resp

        replace_text_in_file(app_config, '  #demo:', '  demo:', ts_delta=10)

        resp = self.app.get('/multiapp1')
        assert 'demo' in resp

def replace_text_in_file(filename, old, new, ts_delta=2):
    text = io.open(filename, encoding='utf-8').read()
    text = text.replace(old, new)
    io.open(filename, 'w', encoding='utf-8').write(text)

    # file timestamps are not precise enough (1sec)
    # add larger delta to force reload
    m_time = os.path.getmtime(filename)
    os.utime(filename, (m_time+ts_delta, m_time+ts_delta))
