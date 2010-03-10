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

from mapproxy.core.config import Options, base_config, load_base_config

from mapproxy.tests.helper import TempFiles

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
    defaults_yaml = """
    foo:
        bar:
            ham: 2
            eggs: 4
    biz: 'foobar'
    wiz: 'foobar'
    """
    
    def test_defaults(self):
        with TempFiles() as tmp:
            with open(tmp[0], 'w') as f:
                f.write(TestDefaultsLoading.defaults_yaml)
            load_base_config(config_file=tmp[0], clear_existing=True)
            
            assert base_config().biz == 'foobar'
            assert base_config().wiz == 'foobar'
            assert base_config().foo.bar.ham == 2
            assert base_config().foo.bar.eggs == 4
            assert not hasattr(base_config(), 'wms')
    def test_defaults_overwrite(self):
        with TempFiles(2) as tmp:
            with open(tmp[0], 'w') as f:
                f.write(TestDefaultsLoading.defaults_yaml)
            with open(tmp[1], 'w') as f:
                f.write("""
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
        
            