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

import pytest

from mapproxy.script.grids import grids_command
from mapproxy.test.helper import capture


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixture")
GRID_NAMES = ["global_geodetic_sqrt2", "grid_full_example", "another_grid_full_example"]
UNUSED_GRID_NAMES = ["GLOBAL_GEODETIC", "GLOBAL_MERCATOR", "GLOBAL_WEBMERCATOR"]


class TestUtilGrids(object):

    def setup(self):
        self.mapproxy_config_file = os.path.join(FIXTURE_DIR, "util_grids.yaml")
        self.args = ["command_dummy", "-f", self.mapproxy_config_file]

    def test_config_not_found(self):
        self.args = ["command_dummy", "-f", "foo.bar"]
        with capture() as (_, err):
            with pytest.raises(SystemExit):
                grids_command(self.args)
        assert err.getvalue().startswith("ERROR:")

    def test_list_configured(self):
        self.args.append("-l")
        with capture() as (out, err):
            grids_command(self.args)
        captured_output = out.getvalue()
        for grid in GRID_NAMES:
            assert grid in captured_output

        number_of_lines = sum(1 for line in captured_output.split("\n") if line)

        assert number_of_lines == len(GRID_NAMES)

    def test_list_configured_all(self):
        self.args.append("-l")
        self.args.append("--all")
        with capture() as (out, err):
            grids_command(self.args)
        captured_output = out.getvalue()
        for grid in GRID_NAMES + UNUSED_GRID_NAMES:
            assert grid in captured_output

        number_of_lines = sum(1 for line in captured_output.split("\n") if line)

        assert number_of_lines == len(UNUSED_GRID_NAMES) + len(GRID_NAMES)

    def test_display_single_grid(self):
        self.args.append("-g")
        self.args.append("GLOBAL_MERCATOR")
        with capture() as (out, err):
            grids_command(self.args)
        captured_output = out.getvalue()
        assert "GLOBAL_MERCATOR" in captured_output

    def test_ignore_case(self):
        self.args.append("-g")
        self.args.append("global_geodetic")
        with capture() as (out, err):
            grids_command(self.args)
        captured_output = out.getvalue()
        assert "GLOBAL_GEODETIC" in captured_output

    def test_all_grids(self):
        with capture() as (out, err):
            grids_command(self.args)
        captured_output = out.getvalue()
        assert "GLOBAL_MERCATOR" in captured_output
        assert "origin*: 'll'" in captured_output
