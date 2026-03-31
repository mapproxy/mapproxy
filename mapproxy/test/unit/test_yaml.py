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

from mapproxy.util.yaml import load_yaml, load_yaml_file, YAMLError, replace_env_vars, expand_env


class TestLoadYAMLFile(object):

    def setup_method(self):
        self.tmp_files = []

    def teardown_method(self):
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
        assert isinstance(f, str)
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


class TestReplaceEnvVars:
    """Tests for replace_env_vars: substitutes $VAR and ${VAR} with environment variables."""

    def test_simple_var(self, monkeypatch):
        monkeypatch.setenv("MY_VAR", "hello")
        assert replace_env_vars("$MY_VAR") == "hello"

    def test_braced_var(self, monkeypatch):
        monkeypatch.setenv("MY_VAR", "hello")
        assert replace_env_vars("${MY_VAR}") == "hello"

    def test_var_embedded_in_string(self, monkeypatch):
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "5432")
        assert replace_env_vars("http://$HOST:${PORT}/path") == "http://localhost:5432/path"

    def test_unknown_var_stays_unchanged(self, monkeypatch):
        monkeypatch.delenv("UNKNOWN_VAR_XYZ", raising=False)
        assert replace_env_vars("$UNKNOWN_VAR_XYZ") == "$UNKNOWN_VAR_XYZ"
        assert replace_env_vars("${UNKNOWN_VAR_XYZ}") == "${UNKNOWN_VAR_XYZ}"

    def test_mixed_known_and_unknown(self, monkeypatch):
        monkeypatch.setenv("KNOWN", "value")
        monkeypatch.delenv("UNKNOWN_VAR_XYZ", raising=False)
        assert replace_env_vars("$KNOWN and $UNKNOWN_VAR_XYZ") == "value and $UNKNOWN_VAR_XYZ"

    def test_multiple_vars(self, monkeypatch):
        monkeypatch.setenv("A", "1")
        monkeypatch.setenv("B", "2")
        monkeypatch.setenv("C", "3")
        assert replace_env_vars("$A-${B}-$C") == "1-2-3"

    def test_empty_string(self):
        assert replace_env_vars("") == ""

    def test_no_vars(self):
        assert replace_env_vars("just a plain string") == "just a plain string"

    def test_var_with_empty_value(self, monkeypatch):
        monkeypatch.setenv("EMPTY_VAR", "")
        assert replace_env_vars("prefix${EMPTY_VAR}suffix") == "prefixsuffix"

    def test_var_with_special_characters_in_value(self, monkeypatch):
        monkeypatch.setenv("SPECIAL", "hello world/foo@bar")
        assert replace_env_vars("${SPECIAL}") == "hello world/foo@bar"


class TestExpandEnv:
    """Tests for expand_env: recursively expands env vars in nested structures."""

    def test_string(self, monkeypatch):
        monkeypatch.setenv("X", "expanded")
        assert expand_env("$X") == "expanded"

    def test_dict(self, monkeypatch):
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_PORT", "3306")
        data = {"host": "$DB_HOST", "port": "${DB_PORT}"}
        assert expand_env(data) == {"host": "myhost", "port": "3306"}

    def test_list(self, monkeypatch):
        monkeypatch.setenv("ITEM", "val")
        assert expand_env(["$ITEM", "static"]) == ["val", "static"]

    def test_nested_dict_and_list(self, monkeypatch):
        monkeypatch.setenv("URL", "http://example.com")
        data = {
            "sources": [
                {"url": "$URL", "name": "test"},
            ],
            "meta": {"ref": "${URL}/api"},
        }
        expected = {
            "sources": [
                {"url": "http://example.com", "name": "test"},
            ],
            "meta": {"ref": "http://example.com/api"},
        }
        assert expand_env(data) == expected

    def test_tuple(self, monkeypatch):
        monkeypatch.setenv("T", "tval")
        result = expand_env(("$T", "fixed"))
        assert result == ("tval", "fixed")
        assert isinstance(result, tuple)

    def test_non_string_values_unchanged(self):
        assert expand_env(42) == 42
        assert expand_env(3.14) == 3.14
        assert expand_env(True) is True
        assert expand_env(None) is None

    def test_dict_with_non_string_values(self, monkeypatch):
        monkeypatch.setenv("NAME", "test")
        data = {"name": "$NAME", "count": 5, "active": True, "ratio": 0.5}
        expected = {"name": "test", "count": 5, "active": True, "ratio": 0.5}
        assert expand_env(data) == expected

    def test_deeply_nested(self, monkeypatch):
        monkeypatch.setenv("DEEP", "found")
        data = {"a": {"b": {"c": {"d": "$DEEP"}}}}
        assert expand_env(data) == {"a": {"b": {"c": {"d": "found"}}}}

    def test_unknown_env_in_nested_structure(self, monkeypatch):
        monkeypatch.delenv("MISSING_XYZ", raising=False)
        data = {"key": "${MISSING_XYZ}"}
        assert expand_env(data) == {"key": "${MISSING_XYZ}"}


class TestLoadYamlWithEnvVars:
    """Integration tests: load_yaml with environment variable expansion."""

    def test_load_yaml_expands_env(self, monkeypatch):
        monkeypatch.setenv("CACHE_DIR", "/tmp/cache")
        doc = load_yaml("cache:\n  directory: ${CACHE_DIR}")
        assert doc == {"cache": {"directory": "/tmp/cache"}}

    def test_load_yaml_expands_env_in_list(self, monkeypatch):
        monkeypatch.setenv("SRC", "http://wms.example.com")
        doc = load_yaml("sources:\n  - $SRC\n  - http://static.example.com")
        assert doc == {"sources": ["http://wms.example.com", "http://static.example.com"]}
