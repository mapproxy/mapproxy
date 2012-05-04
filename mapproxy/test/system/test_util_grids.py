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

from __future__ import with_statement
import os
import sys

from cStringIO import StringIO
from nose.tools import assert_raises
from mapproxy.script.grids import grids_command

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixture')
GRID_NAMES = [
    'global_geodetic_sqrt2',
    'GLOBAL_GEODETIC',
    'GLOBAL_MERCATOR',
    'grid_full_example',
    'another_grid_full_example'
]

class TestUtilGrids(object):
    def setup(self):
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        sys.stdout = sys.stderr = StringIO()
        self.mapproxy_config_file = os.path.join(FIXTURE_DIR, 'util_grids.yaml')
        self.args = ['-f', self.mapproxy_config_file]

    def teardown(self):
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr

    def test_config_not_found(self):
        self.args = ['-f', 'foo.bar']
        with assert_raises(SystemExit) as cm:
            grids_command(self.args)
        assert sys.stdout.getvalue().startswith("ERROR:")
        
    def test_list_configured(self):
        self.args.append('-l')
        grids_command(self.args)
        captured_output = sys.stdout.getvalue()
        assert "Configured Grids" in captured_output
        for grid in GRID_NAMES:
            assert grid in captured_output

        number_of_lines = 0
        for line in captured_output.split('\n'):
            if line: #last line is emtpy
                number_of_lines += 1
        # 5 entries plus one header
        assert number_of_lines == 6        

    def test_display_single_grid(self):
        self.args.append('-g')
        self.args.append('GLOBAL_MERCATOR')
        grids_command(self.args)
        captured_output = sys.stdout.getvalue()
        assert "GLOBAL_MERCATOR" in captured_output

    def test_ignore_case(self):
        self.args.append('-g')
        self.args.append('global_geodetic')
        grids_command(self.args)
        captured_output = sys.stdout.getvalue()
        assert "GLOBAL_GEODETIC" in captured_output

    def test_all_grids(self):
        grids_command(self.args)
        captured_output = sys.stdout.getvalue()
        assert "GLOBAL_MERCATOR" in captured_output
        assert "origin: 'sw'" in captured_output


