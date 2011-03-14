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

import os
import stat
import platform
import shutil

from cStringIO import StringIO

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.platform.image import Image
from mapproxy.test.image import is_png
from mapproxy.test.system import prepare_env, create_app, module_teardown, SystemTest
from nose.tools import eq_
from nose.plugins.skip import SkipTest

test_config = {}

def setup_module():
    if platform.system() == 'Windows':
        raise SkipTest('CGI test only works on Unix (for now)')
        
    prepare_env(test_config, 'mapserver.yaml')
    
    shutil.copy(os.path.join(test_config['fixture_dir'], 'cgi.py'),
        test_config['base_dir'])
    
    os.chmod(os.path.join(test_config['base_dir'], 'cgi.py'),
        stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)
    
    os.mkdir(os.path.join(test_config['base_dir'], 'tmp'))
    
    create_app(test_config)

def teardown_module():
    module_teardown(test_config)

class TestMapServerCGI(SystemTest):
    config = test_config
    def setup(self):
        SystemTest.setup(self)
        self.common_map_req = WMS111MapRequest(url='/service?', param=dict(service='WMS', 
             version='1.1.1', bbox='-180,0,0,80', width='200', height='200',
             layers='ms', srs='EPSG:4326', format='image/png',
             styles='', request='GetMap'))
    
    def test_get_map(self):
        resp = self.app.get(self.common_map_req)
        eq_(resp.content_type, 'image/png')
        data = StringIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        img = img.convert('RGB')
        eq_(img.getcolors(), [(200*200, (255, 0, 0))])
