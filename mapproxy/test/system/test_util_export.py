# This file is part of the MapProxy project.
# Copyright (C) 2012 Omniscale <http://omniscale.de>
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

from __future__ import with_statement
import os
import tempfile
import shutil
import contextlib

from nose.tools import eq_, assert_raises
from mapproxy.script.export import export_command
from mapproxy.test.image import tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.helper import capture

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixture')

@contextlib.contextmanager
def tile_server(tile_coords):
    with tmp_image((256, 256), format='jpeg') as img:
        img = img.read()
    expected_reqs = []
    for tile in tile_coords:
        expected_reqs.append(
            ({'path': r'/tiles/%d/%d/%d.png' % (tile[2], tile[0], tile[1])},
             {'body': img, 'headers': {'content-type': 'image/png'}}))
    with mock_httpd(('localhost', 42423), expected_reqs, unordered=True):
        yield

class TestUtilExport(object):
    def setup(self):
        self.dir = tempfile.mkdtemp()
        self.dest = os.path.join(self.dir, 'dest')
        self.mapproxy_conf_name = 'mapproxy_export.yaml'
        shutil.copy(os.path.join(FIXTURE_DIR, self.mapproxy_conf_name), self.dir)
        self.mapproxy_conf_file = os.path.join(self.dir, self.mapproxy_conf_name)
        self.args = ['command_dummy', '-f', self.mapproxy_conf_file]

    def teardown(self):
        shutil.rmtree(self.dir)

    def test_config_not_found(self):
        self.args = ['command_dummy', '-f', 'foo.bar']
        with capture() as (out, err):
            try:
                export_command(self.args)
            except SystemExit as ex:
                assert ex.code != 0
            else:
                assert False, 'export command did not exit'
        assert err.getvalue().startswith("ERROR:")

    def test_no_fetch_missing_tiles(self):
        self.args += ['--grid', 'GLOBAL_MERCATOR', '--dest', self.dest,
            '--levels', '0', '--source', 'tms_cache']
        with capture() as (out, err):
            export_command(self.args)

        eq_(os.listdir(self.dest), ['tile_locks'])

    def test_fetch_missing_tiles(self):
        self.args += ['--grid', 'GLOBAL_MERCATOR', '--dest', self.dest,
            '--levels', '0,1', '--source', 'tms_cache', '--fetch-missing-tiles']
        with tile_server([(0, 0, 0), (0, 0, 1), (0, 1, 1), (1, 0, 1), (1, 1, 1)]):
            with capture() as (out, err):
                export_command(self.args)

        assert os.path.exists(os.path.join(self.dest, 'tile_locks'))
        assert os.path.exists(os.path.join(self.dest, '0', '0', '0.png'))
        assert os.path.exists(os.path.join(self.dest, '1', '0', '0.png'))
        assert os.path.exists(os.path.join(self.dest, '1', '0', '1.png'))
        assert os.path.exists(os.path.join(self.dest, '1', '1', '0.png'))
        assert os.path.exists(os.path.join(self.dest, '1', '1', '1.png'))

    def test_force(self):
        self.args += ['--grid', 'GLOBAL_MERCATOR', '--dest', self.dest,
            '--levels', '0', '--source', 'tms_cache']
        with capture() as (out, err):
            export_command(self.args)

        with capture() as (out, err):
            assert_raises(SystemExit, export_command, self.args)

        with capture() as (out, err):
            export_command(self.args + ['--force'])

    def test_invalid_grid_definition(self):
        self.args += ['--grid', 'foo=1', '--dest', self.dest,
            '--levels', '0', '--source', 'tms_cache']
        with capture() as (out, err):
            assert_raises(SystemExit, export_command, self.args)
            assert 'foo' in err.getvalue()

    def test_custom_grid(self):
        self.args += ['--grid', 'base=GLOBAL_MERCATOR min_res=100000', '--dest', self.dest,
            '--levels', '1', '--source', 'tms_cache', '--fetch-missing-tiles']
        with tile_server([(0, 3, 2), (1, 3, 2), (2, 3, 2), (3, 3, 2),
                          (0, 2, 2), (1, 2, 2), (2, 2, 2), (3, 2, 2),
                          (0, 1, 2), (1, 1, 2), (2, 1, 2), (3, 1, 2),
                          (0, 0, 2), (1, 0, 2), (2, 0, 2), (3, 0, 2)]):
            with capture() as (out, err):
                export_command(self.args)

        assert os.path.exists(os.path.join(self.dest, 'tile_locks'))
        assert os.path.exists(os.path.join(self.dest, '1', '0', '0.png'))
        assert os.path.exists(os.path.join(self.dest, '1', '3', '3.png'))


    def test_coverage(self):
        self.args += ['--grid', 'GLOBAL_MERCATOR', '--dest', self.dest,
            '--levels', '0..2', '--source', 'tms_cache', '--fetch-missing-tiles',
            '--coverage', '10,10,20,20', '--srs', 'EPSG:4326']
        with tile_server([(0, 0, 0), (1, 1, 1), (2, 2, 2)]):
            with capture() as (out, err):
                export_command(self.args)

        assert os.path.exists(os.path.join(self.dest, 'tile_locks'))
        assert os.path.exists(os.path.join(self.dest, '0', '0', '0.png'))
        assert os.path.exists(os.path.join(self.dest, '1', '1', '1.png'))
        assert os.path.exists(os.path.join(self.dest, '2', '2', '2.png'))
