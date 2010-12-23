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

from __future__ import with_statement
import os
import time
import shutil
import tempfile
from mapproxy.seed import seed_from_yaml_conf

from mapproxy.test.http import mock_httpd
from mapproxy.test.image import tmp_image

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixture')

class TestSeed(object):
    def setup(self):
        self.dir = tempfile.mkdtemp()
        shutil.copy(os.path.join(FIXTURE_DIR, 'seed_mapproxy.yaml'), self.dir)
        shutil.copy(os.path.join(FIXTURE_DIR, 'seed.yaml'), self.dir)
        self.seed_conf_file = os.path.join(self.dir, 'seed.yaml')
        self.mapproxy_conf_file = os.path.join(self.dir, 'seed_mapproxy.yaml')
        
    def teardown(self):
        shutil.rmtree(self.dir)
    
    def make_tile(self, coord=(0, 0, 0), timestamp=None):
        """
        Create file for tile at `coord` with given timestamp.
        """
        tile_dir = os.path.join(self.dir, 'cache/one_EPSG4326/%02d/000/000/%03d/000/000/' %
                                (coord[2], coord[0]))
        os.makedirs(tile_dir)
        tile = os.path.join(tile_dir + '%03d.png' % coord[1])
        open(tile, 'w').write('')
        if timestamp:
            os.utime(tile, (timestamp, timestamp))
        return tile
    
    def test_seed_dry_run(self):
       seed_from_yaml_conf(self.seed_conf_file, self.mapproxy_conf_file, verbose=False, dry_run=True)
    
    def test_seed(self):
        with tmp_image((256, 256), format='png') as img:
            img_data = img.read()
            expected_req = ({'path': r'/service?LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&VERSION=1.1.1&bbox=-180.0,-90.0,180.0,90.0'
                                  '&width=256&height=128&srs=EPSG:4326'},
                            {'body': img_data, 'headers': {'content-type': 'image/png'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                seed_from_yaml_conf(self.seed_conf_file, self.mapproxy_conf_file, verbose=True, dry_run=False)

    def test_reseed_uptodate(self):
        # tile already there.
        self.make_tile((0, 0, 0))
        seed_from_yaml_conf(self.seed_conf_file, self.mapproxy_conf_file, verbose=False)
    
    def test_reseed_remove_before(self):
        # tile already there but too old
        t000 = self.make_tile((0, 0, 0), timestamp=time.time() - (60*60*25))
        # old tile outside the seed view (should be removed)
        t001 = self.make_tile((0, 0, 1), timestamp=time.time() - (60*60*25))
        assert os.path.exists(t000)
        assert os.path.exists(t001)
        with tmp_image((256, 256), format='png') as img:
            img_data = img.read()
            expected_req = ({'path': r'/service?LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&VERSION=1.1.1&bbox=-180.0,-90.0,180.0,90.0'
                                  '&width=256&height=128&srs=EPSG:4326'},
                            {'body': img_data, 'headers': {'content-type': 'image/png'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                seed_from_yaml_conf(self.seed_conf_file, self.mapproxy_conf_file, verbose=True, dry_run=False)
        
        assert os.path.exists(t000)
        assert os.path.getmtime(t000) - 5 < time.time() < os.path.getmtime(t000) + 5
        assert not os.path.exists(t001)