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

import os
import tempfile

from mapproxy.util.yaml import load_yaml, load_yaml_file, YAMLError
from nose.tools import eq_


class TestLoadYAMLFile(object):
    def setup(self):
        self.tmp_files = []
    
    def teardown(self):
        for f in self.tmp_files:
            os.unlink(f)
    
    def yaml_file(self, content):
        fd, fname = tempfile.mkstemp()
        f = os.fdopen(fd, 'w')
        f.write(content)
        return fname
    
    def test_load_yaml_file(self):
        f = self.yaml_file("hello:\n - 1\n - 2")
        doc = load_yaml_file(open(f))
        eq_(doc, {'hello': [1, 2]})
    
    def test_load_yaml_file_filename(self):
        f = self.yaml_file("hello:\n - 1\n - 2")
        assert isinstance(f, basestring)
        doc = load_yaml_file(f)
        eq_(doc, {'hello': [1, 2]})

    def test_load_yaml(self):
        doc = load_yaml("hello:\n - 1\n - 2")
        eq_(doc, {'hello': [1, 2]})
    
    def test_load_yaml_with_tabs(self):
        try:
            f = self.yaml_file("hello:\n\t- world")
            load_yaml_file(f)
        except YAMLError, ex:
            assert 'line 2' in str(ex)
        else:
            assert False, 'expected YAMLError'
            