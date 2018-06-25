# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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
import tempfile

from mapproxy.util.yaml import load_yaml, load_yaml_file, YAMLError
from mapproxy.compat import string_type


class TestLoadYAMLFile(object):

    def setup(self):
        self.tmp_files = []

    def teardown(self):
        for f in self.tmp_files:
            os.unlink(f)

    def yaml_file(self, content):
        fd, fname = tempfile.mkstemp()
        f = os.fdopen(fd, "w")
        f.write(content)
        self.tmp_files.append(fname)
        return fname

    def test_load_yaml_file(self):
        f = self.yaml_file("hello:\n - 1\n - 2")
        doc = load_yaml_file(open(f))
        assert doc == {"hello": [1, 2]}

    def test_load_yaml_file_filename(self):
        f = self.yaml_file("hello:\n - 1\n - 2")
        assert isinstance(f, string_type)
        doc = load_yaml_file(f)
        assert doc == {"hello": [1, 2]}

    def test_load_yaml(self):
        doc = load_yaml("hello:\n - 1\n - 2")
        assert doc == {"hello": [1, 2]}

    def test_load_yaml_with_tabs(self):
        try:
            f = self.yaml_file("hello:\n\t- world")
            load_yaml_file(f)
        except YAMLError as ex:
            assert "line 2" in str(ex)
        else:
            assert False, "expected YAMLError"

    def test_load_yaml_string_error(self):
        try:
            load_yaml('only a string')
        except YAMLError as ex:
            assert "not a YAML dict" in str(ex)
        else:
            assert False, "expected YAMLError"
