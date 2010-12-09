# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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
import os
import tempfile
import shutil
from webtest import TestApp
from mapproxy.wsgiapp import make_wsgi_app 

def module_setup(test_config, config_file, with_cache_data=False):
    fixture_dir = os.path.join(os.path.dirname(__file__), 'fixture')
    fixture_layer_conf = os.path.join(fixture_dir, config_file)
    
    if 'base_dir' not in test_config:
        test_config['base_dir'] = tempfile.mkdtemp()
    test_config['config_file'] = os.path.join(test_config['base_dir'], config_file)
    shutil.copy(fixture_layer_conf, test_config['config_file'])
    if with_cache_data:
        shutil.copytree(os.path.join(fixture_dir, 'cache_data'),
                        os.path.join(test_config['base_dir'], 'cache_data'))
    app = make_wsgi_app(test_config['config_file'])
    app.application.base_config.debug_mode = True
    test_config['app'] = TestApp(app, use_unicode=False)

def module_teardown(test_config):
    shutil.rmtree(test_config['base_dir'])
    test_config.clear()
    
def make_base_config(test_config):
    return lambda: test_config['app'].app.application.base_config

class SystemTest(object):
    def setup(self):
        self.app = self.config['app']
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
