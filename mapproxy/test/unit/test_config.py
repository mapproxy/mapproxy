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

from mapproxy.config import Options, base_config, load_base_config

from mapproxy.test.helper import TempFiles

def teardown_module():
    load_base_config(clear_existing=True)

class TestOptions(object):
    def test_update_overwrite(self):
        d = Options(foo='bar', baz=4)
        d.update(Options(baz=5))
        assert d.baz == 5
        assert d.foo == 'bar'
    def test_update_new(self):
        d = Options(foo='bar', baz=4)
        d.update(Options(biz=5))
        assert d.baz == 4
        assert d.biz == 5
        assert d.foo == 'bar'
    def test_update_recursive(self):
        d = Options(
            foo='bar',
            baz=Options(ham=2, eggs=4))
        d.update(Options(baz=Options(eggs=5)))
        assert d.foo == 'bar'
        assert d.baz.ham == 2
        assert d.baz.eggs == 5
    def test_compare(self):
        assert Options(foo=4) == Options(foo=4)
        assert Options(foo=Options(bar=4)) == Options(foo=Options(bar=4))


class TestDefaultsLoading(object):
    defaults_yaml = b"""
    foo:
        bar:
            ham: 2
            eggs: 4
    biz: 'foobar'
    wiz: 'foobar'
    """

    def test_defaults(self):
        with TempFiles() as tmp:
            with open(tmp[0], 'wb') as f:
                f.write(TestDefaultsLoading.defaults_yaml)
            load_base_config(config_file=tmp[0], clear_existing=True)

            assert base_config().biz == 'foobar'
            assert base_config().wiz == 'foobar'
            assert base_config().foo.bar.ham == 2
            assert base_config().foo.bar.eggs == 4
            assert not hasattr(base_config(), 'wms')
    def test_defaults_overwrite(self):
        with TempFiles(2) as tmp:
            with open(tmp[0], 'wb') as f:
                f.write(TestDefaultsLoading.defaults_yaml)
            with open(tmp[1], 'wb') as f:
                f.write(b"""
                baz: [9, 2, 1, 4]
                biz: 'barfoo'
                foo:
                    bar:
                        eggs: 5
                """)

            load_base_config(config_file=tmp[0], clear_existing=True)
            load_base_config(config_file=tmp[1])

            assert base_config().biz == 'barfoo'
            assert base_config().wiz == 'foobar'
            assert base_config().baz == [9, 2, 1, 4]
            assert base_config().foo.bar.ham == 2
            assert base_config().foo.bar.eggs == 5
            assert not hasattr(base_config(), 'wms')


class TestSRSConfig(object):
    def setup(self):
        import mapproxy.config.config
        mapproxy.config.config._config.pop()

    def test_user_srs_definitions(self):
        user_yaml = b"""
        srs:
          axis_order_ne: ['EPSG:9999']
        """
        with TempFiles() as tmp:
            with open(tmp[0], 'wb') as f:
                f.write(user_yaml)

            load_base_config(config_file=tmp[0])

            assert 'EPSG:9999' in base_config().srs.axis_order_ne
            assert 'EPSG:9999' not in base_config().srs.axis_order_en

            #defaults still there
            assert 'EPSG:31468' in base_config().srs.axis_order_ne
            assert 'CRS:84' in base_config().srs.axis_order_en


