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
import contextlib

from cStringIO import StringIO
from nose.tools import assert_raises
from mapproxy.script.grids import grids_command

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixture')
GRID_NAMES = [
    'global_geodetic_sqrt2',
    'grid_full_example',
    'another_grid_full_example'
]
UNUSED_GRID_NAMES = [
    'GLOBAL_GEODETIC',
    'GLOBAL_MERCATOR',
    'GLOBAL_WEBMERCATOR',
]


@contextlib.contextmanager
def capture_stderr(io=None):
    if io is None:
        io = StringIO()
    old_stderr = sys.stderr
    sys.stderr = io
    try:
        yield io
    finally:
        sys.stderr = old_stderr

class TestUtilGrids(object):
    def setup(self):
        self.mapproxy_config_file = os.path.join(FIXTURE_DIR, 'util_grids.yaml')
        self.args = ['command_dummy', '-f', self.mapproxy_config_file]

    def test_config_not_found(self):
        self.args = ['command_dummy', '-f', 'foo.bar']
        with capture_stderr() as err:
            assert_raises(SystemExit, grids_command, self.args)
        assert err.getvalue().startswith("ERROR:")

    def test_list_configured(self):
        self.args.append('-l')
        grids_command(self.args)
        captured_output = sys.stdout.getvalue()
        for grid in GRID_NAMES:
            assert grid in captured_output

        number_of_lines = sum(1 for line in captured_output.split('\n') if line)

        assert number_of_lines == len(GRID_NAMES)

    def test_list_configured_all(self):
        self.args.append('-l')
        self.args.append('--all')
        grids_command(self.args)
        captured_output = sys.stdout.getvalue()
        for grid in GRID_NAMES + UNUSED_GRID_NAMES:
            assert grid in captured_output

        number_of_lines = sum(1 for line in captured_output.split('\n') if line)

        assert number_of_lines == len(UNUSED_GRID_NAMES) + len(GRID_NAMES)

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
        assert "origin*: 'll'" in captured_output


