# -:- encoding: utf-8 -:-
# This file is part of the MapProxy project.
# Copyright (C) 2013 Omniscale <http://omniscale.de>
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

from copy import deepcopy

from mapproxy.script.conf.utils import update_config


class TestUpdateConfig(object):

    def test_empty(self):
        a = {"a": "foo", "b": 42}
        b = {}
        assert update_config(deepcopy(a), b) == a

    def test_add(self):
        a = {"a": "foo", "b": 42}
        b = {"c": [1, 2, 3]}
        assert update_config(a, b) == {"a": "foo", "b": 42, "c": [1, 2, 3]}

    def test_mod(self):
        a = {"a": "foo", "b": 42, "c": {}}
        b = {"a": [1, 2, 3], "c": 1}
        assert update_config(a, b) == {"b": 42, "a": [1, 2, 3], "c": 1}

    def test_nested_add_mod(self):
        a = {"a": "foo", "b": {"ba": 42, "bb": {}}}
        b = {"b": {"bb": {"bba": 1}, "bc": [1, 2, 3]}}
        assert update_config(a, b) == {
            "a": "foo",
            "b": {"ba": 42, "bb": {"bba": 1}, "bc": [1, 2, 3]},
        }

    def test_add_all(self):
        a = {"a": "foo", "b": {"ba": 42, "bb": {}}}
        b = {"__all__": {"ba": 1}}
        assert update_config(a, b) == {"a": {"ba": 1}, "b": {"ba": 1, "bb": {}}}

    def test_extend(self):
        a = {"a": "foo", "b": ["ba"]}
        b = {"b__extend__": ["bb", "bc"]}
        assert update_config(a, b) == {"a": "foo", "b": ["ba", "bb", "bc"]}

    def test_prefix_wildcard(self):
        a = {"test_foo": "foo", "test_bar": "ba", "test2_foo": "test2", "nounderfoo": 1}
        b = {"____foo": 42}
        assert update_config(a, b) == {
            "test_foo": 42,
            "test_bar": "ba",
            "test2_foo": 42,
            "nounderfoo": 1,
        }

    def test_suffix_wildcard(self):
        a = {"test_foo": "foo", "test_bar": "ba", "test2_foo": "test2", "nounderfoo": 1}
        b = {"test____": 42}
        assert update_config(a, b) == {
            "test_foo": 42,
            "test_bar": 42,
            "test2_foo": "test2",
            "nounderfoo": 1,
        }
