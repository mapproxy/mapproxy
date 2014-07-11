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
import time
import shutil
import tempfile
from mapproxy.config.loader import load_configuration
from mapproxy.cache.tile import Tile
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.seed.seeder import seed
from mapproxy.seed.cleanup import cleanup
from mapproxy.seed.config import load_seed_tasks_conf
from mapproxy.config import local_base_config
from mapproxy.util.fs import ensure_directory

from mapproxy.test.http import mock_httpd
from mapproxy.test.image import tmp_image, create_tmp_image_buf, create_tmp_image

from nose.tools import eq_

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixture')

class SeedTestEnvironment(object):
    def setup(self):
        self.dir = tempfile.mkdtemp()
        shutil.copy(os.path.join(FIXTURE_DIR, self.seed_conf_name), self.dir)
        shutil.copy(os.path.join(FIXTURE_DIR, self.mapproxy_conf_name), self.dir)
        shutil.copy(os.path.join(FIXTURE_DIR, self.empty_ogrdata), self.dir)
        self.seed_conf_file = os.path.join(self.dir, self.seed_conf_name)
        self.mapproxy_conf_file = os.path.join(self.dir, self.mapproxy_conf_name)
        self.mapproxy_conf = load_configuration(self.mapproxy_conf_file, seed=True)

    def teardown(self):
        shutil.rmtree(self.dir)

    def make_tile(self, coord=(0, 0, 0), timestamp=None):
        """
        Create file for tile at `coord` with given timestamp.
        """
        tile_dir = os.path.join(self.dir, 'cache/one_EPSG4326/%02d/000/000/%03d/000/000/' %
                                (coord[2], coord[0]))

        ensure_directory(tile_dir)
        tile = os.path.join(tile_dir + '%03d.png' % coord[1])
        open(tile, 'wb').write(b'')
        if timestamp:
            os.utime(tile, (timestamp, timestamp))
        return tile

    def tile_exists(self, coord):
        tile_dir = os.path.join(self.dir, 'cache/one_EPSG4326/%02d/000/000/%03d/000/000/' %
                                (coord[2], coord[0]))
        tile = os.path.join(tile_dir + '%03d.png' % coord[1])
        return os.path.exists(tile)

class SeedTestBase(SeedTestEnvironment):

    def test_seed_dry_run(self):
        with local_base_config(self.mapproxy_conf.base_config):
            seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
            tasks, cleanup_tasks = seed_conf.seeds(['one']), seed_conf.cleanups()
            seed(tasks, dry_run=True)
            cleanup(cleanup_tasks, verbose=False, dry_run=True)

    def test_seed(self):
        with tmp_image((256, 256), format='png') as img:
            img_data = img.read()
            expected_req = ({'path': r'/service?LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&VERSION=1.1.1&bbox=-180.0,-90.0,180.0,90.0'
                                  '&width=256&height=128&srs=EPSG:4326'},
                            {'body': img_data, 'headers': {'content-type': 'image/png'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                with local_base_config(self.mapproxy_conf.base_config):
                    seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
                    tasks, cleanup_tasks = seed_conf.seeds(['one']), seed_conf.cleanups()
                    seed(tasks, dry_run=False)
                    cleanup(cleanup_tasks, verbose=False, dry_run=False)

    def test_reseed_uptodate(self):
        # tile already there.
        self.make_tile((0, 0, 0))
        with local_base_config(self.mapproxy_conf.base_config):
            seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
            tasks, cleanup_tasks = seed_conf.seeds(['one']), seed_conf.cleanups()
            seed(tasks, dry_run=False)
            cleanup(cleanup_tasks, verbose=False, dry_run=False)

class TestSeedOldConfiguration(SeedTestBase):
    seed_conf_name = 'seed_old.yaml'
    mapproxy_conf_name = 'seed_mapproxy.yaml'
    empty_ogrdata = 'empty_ogrdata.geojson'

    def test_reseed_remove_before(self):
        # tile already there but too old
        t000 = self.make_tile((0, 0, 0), timestamp=time.time() - (60*60*25))
        # old tile outside the seed view (should be removed)
        t001 = self.make_tile((0, 0, 1), timestamp=time.time() - (60*60*25))
        assert os.path.exists(t000)
        assert os.path.exists(t001)
        with tmp_image((256, 256), format='png') as img:
            img_data = img.read()
            expected_req = ({'path': r'/service?LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&VERSION=1.1.1&bbox=-180.0,-90.0,180.0,90.0'
                                  '&width=256&height=128&srs=EPSG:4326'},
                            {'body': img_data, 'headers': {'content-type': 'image/png'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
                tasks, cleanup_tasks = seed_conf.seeds(), seed_conf.cleanups()
                seed(tasks, dry_run=False)
                cleanup(cleanup_tasks, verbose=False, dry_run=False)

        assert os.path.exists(t000)
        assert os.path.getmtime(t000) - 5 < time.time() < os.path.getmtime(t000) + 5
        assert not os.path.exists(t001)


tile_image_buf = create_tmp_image_buf((256, 256), color='blue')
tile_image = create_tmp_image((256, 256), color='blue')

class TestSeed(SeedTestBase):
    seed_conf_name = 'seed.yaml'
    mapproxy_conf_name = 'seed_mapproxy.yaml'
    empty_ogrdata = 'empty_ogrdata.geojson'

    def test_cleanup_levels(self):
        seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
        cleanup_tasks = seed_conf.cleanups(['cleanup'])

        self.make_tile((0, 0, 0))
        self.make_tile((0, 0, 1))
        self.make_tile((0, 0, 2))
        self.make_tile((0, 0, 3))

        cleanup(cleanup_tasks, verbose=False, dry_run=False)
        assert not self.tile_exists((0, 0, 0))
        assert not self.tile_exists((0, 0, 1))
        assert self.tile_exists((0, 0, 2))
        assert not self.tile_exists((0, 0, 3))

        eq_(sorted(os.listdir(os.path.join(self.dir, 'cache', 'one_EPSG4326'))),
            ['02'])

    def test_cleanup_remove_all(self):
        seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
        cleanup_tasks = seed_conf.cleanups(['remove_all'])

        self.make_tile((0, 0, 0))
        self.make_tile((0, 0, 1))
        self.make_tile((1, 0, 1))
        self.make_tile((0, 1, 1))
        self.make_tile((1, 1, 1))
        self.make_tile((0, 0, 2))
        self.make_tile((0, 0, 3))

        eq_(sorted(os.listdir(os.path.join(self.dir, 'cache', 'one_EPSG4326'))),
            ['00', '01', '02', '03'])

        cleanup(cleanup_tasks, verbose=False, dry_run=False)
        assert self.tile_exists((0, 0, 0))
        assert not self.tile_exists((0, 0, 1))
        assert not self.tile_exists((1, 0, 1))
        assert not self.tile_exists((0, 1, 1))
        assert not self.tile_exists((1, 1, 1))
        assert not self.tile_exists((0, 0, 1))
        assert self.tile_exists((0, 0, 2))
        assert self.tile_exists((0, 0, 3))

        # remove_all should remove the whole directory
        eq_(sorted(os.listdir(os.path.join(self.dir, 'cache', 'one_EPSG4326'))),
            ['00', '02', '03'])

    def test_cleanup_coverage(self):
        seed_conf = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
        cleanup_tasks = seed_conf.cleanups(['with_coverage'])

        self.make_tile((0, 0, 0))
        self.make_tile((1, 0, 1))
        self.make_tile((2, 0, 2))
        self.make_tile((2, 0, 3))
        self.make_tile((4, 0, 3))

        cleanup(cleanup_tasks, verbose=False, dry_run=False)
        assert not self.tile_exists((0, 0, 0))
        assert not self.tile_exists((1, 0, 1))
        assert self.tile_exists((2, 0, 2))
        assert not self.tile_exists((2, 0, 3))
        assert self.tile_exists((4, 0, 3))

    def test_seed_mbtile(self):
        with tmp_image((256, 256), format='png') as img:
            img_data = img.read()
            expected_req = ({'path': r'/service?LAYERS=bar&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetMap&VERSION=1.1.1&bbox=-180.0,-90.0,180.0,90.0'
                                  '&width=256&height=128&srs=EPSG:4326'},
                            {'body': img_data, 'headers': {'content-type': 'image/png'}})
            with mock_httpd(('localhost', 42423), [expected_req]):
                seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
                tasks, cleanup_tasks = seed_conf.seeds(['mbtile_cache']), seed_conf.cleanups(['cleanup_mbtile_cache'])
                seed(tasks, dry_run=False)
                cleanup(cleanup_tasks, verbose=False, dry_run=False)

    def create_tile(self, coord=(0, 0, 0)):
        return Tile(coord,
            ImageSource(tile_image_buf,
                image_opts=ImageOptions(format='image/png')))

    def test_reseed_mbtiles(self):
        seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
        tasks, cleanup_tasks = seed_conf.seeds(['mbtile_cache']), seed_conf.cleanups(['cleanup_mbtile_cache'])

        cache = tasks[0].tile_manager.cache
        cache.store_tile(self.create_tile())
        # no refresh before
        seed(tasks, dry_run=False)

    def test_reseed_mbtiles_with_refresh(self):
        seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
        tasks, cleanup_tasks = seed_conf.seeds(['mbtile_cache_refresh']), seed_conf.cleanups(['cleanup_mbtile_cache'])

        cache = tasks[0].tile_manager.cache
        cache.store_tile(self.create_tile())

        expected_req = ({'path': r'/service?LAYERS=bar&SERVICE=WMS&FORMAT=image%2Fpng'
                          '&REQUEST=GetMap&VERSION=1.1.1&bbox=-180.0,-90.0,180.0,90.0'
                          '&width=256&height=128&srs=EPSG:4326'},
                        {'body': tile_image, 'headers': {'content-type': 'image/png'}})
        with mock_httpd(('localhost', 42423), [expected_req]):
            # mbtiles does not support timestamps, refresh all tiles
            seed(tasks, dry_run=False)

    def test_cleanup_mbtiles(self):
        seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
        tasks, cleanup_tasks = seed_conf.seeds(['mbtile_cache_refresh']), seed_conf.cleanups(['cleanup_mbtile_cache'])

        cache = tasks[0].tile_manager.cache
        cache.store_tile(self.create_tile())

        cleanup(cleanup_tasks, verbose=False, dry_run=False)

    def test_cleanup_sqlite(self):
        seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
        cleanup_tasks = seed_conf.cleanups(['sqlite_cache'])

        cache = cleanup_tasks[0].tile_manager.cache
        cache.store_tile(self.create_tile((0, 0, 2)))
        cache.store_tile(self.create_tile((0, 0, 3)))
        assert cache.is_cached(Tile((0, 0, 2)))
        assert cache.is_cached(Tile((0, 0, 3)))

        eq_(sorted(os.listdir(os.path.join(self.dir, 'cache', 'sqlite_cache', 'GLOBAL_GEODETIC'))),
            ['2.mbtile', '3.mbtile'])

        cleanup(cleanup_tasks, verbose=False, dry_run=False)

        # 3.mbtile file is still there
        eq_(sorted(os.listdir(os.path.join(self.dir, 'cache', 'sqlite_cache', 'GLOBAL_GEODETIC'))),
            ['2.mbtile', '3.mbtile'])
        assert cache.is_cached(Tile((0, 0, 2)))
        assert not cache.is_cached(Tile((0, 0, 3)))

    def test_cleanup_sqlite_remove_all(self):
        seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
        cleanup_tasks = seed_conf.cleanups(['sqlite_cache_remove_all'])

        cache = cleanup_tasks[0].tile_manager.cache
        cache.store_tile(self.create_tile((0, 0, 2)))
        cache.store_tile(self.create_tile((0, 0, 3)))
        assert cache.is_cached(Tile((0, 0, 2)))
        assert cache.is_cached(Tile((0, 0, 3)))

        eq_(sorted(os.listdir(os.path.join(self.dir, 'cache', 'sqlite_cache', 'GLOBAL_GEODETIC'))),
            ['2.mbtile', '3.mbtile'])

        cleanup(cleanup_tasks, verbose=False, dry_run=False)

        # 3.mbtile file should be removed completely
        eq_(sorted(os.listdir(os.path.join(self.dir, 'cache', 'sqlite_cache', 'GLOBAL_GEODETIC'))),
            ['3.mbtile'])
        assert not cache.is_cached(Tile((0, 0, 2)))
        assert cache.is_cached(Tile((0, 0, 3)))

    def test_active_seed_tasks(self):
        with local_base_config(self.mapproxy_conf.base_config):
            seed_conf = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
            assert len(seed_conf.seed_tasks_names()) == 5
            assert len(seed_conf.seeds()) == 5

    def test_seed_refresh_remove_before_from_file(self):
        # tile already there but old
        t000 = self.make_tile((0, 0, 0), timestamp=time.time() - (60*60*25))

        # mtime is older than tile, no create of the tile
        timestamp = time.time() - (60*60*30)
        os.utime(self.seed_conf_file, (timestamp, timestamp))
        with local_base_config(self.mapproxy_conf.base_config):
            seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
            tasks = seed_conf.seeds(['refresh_from_file'])
            seed(tasks, dry_run=False)


        # touch the seed_conf file and refresh everything
        os.utime(self.seed_conf_file, None)
        img_data = create_tmp_image((256, 256), format='png')
        expected_req = ({'path': r'/service?LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                              '&REQUEST=GetMap&VERSION=1.1.1&bbox=-180.0,-90.0,180.0,90.0'
                              '&width=256&height=128&srs=EPSG:4326'},
                        {'body': img_data, 'headers': {'content-type': 'image/png'}})
        with mock_httpd(('localhost', 42423), [expected_req]):
            # touch the seed_conf file and refresh everything
            timestamp = time.time() - 60
            os.utime(self.seed_conf_file, (timestamp, timestamp))

            with local_base_config(self.mapproxy_conf.base_config):
                seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
                tasks = seed_conf.seeds(['refresh_from_file'])
                seed(tasks, dry_run=False)

                assert os.path.exists(t000)
                assert os.path.getmtime(t000) - 5 < time.time() < os.path.getmtime(t000) + 5

        # mtime is older than tile, no cleanup
        timestamp = time.time() - 5
        os.utime(self.seed_conf_file, (timestamp, timestamp))
        with local_base_config(self.mapproxy_conf.base_config):
            seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
            cleanup_tasks = seed_conf.cleanups(['remove_from_file'])
            cleanup(cleanup_tasks, verbose=False, dry_run=False)
        assert os.path.exists(t000)

        # now touch the seed_conf again and remove everything
        timestamp = time.time() + 5
        os.utime(self.seed_conf_file, (timestamp, timestamp))
        with local_base_config(self.mapproxy_conf.base_config):
            seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
            cleanup_tasks = seed_conf.cleanups(['remove_from_file'])
            cleanup(cleanup_tasks, verbose=False, dry_run=False)
        assert not os.path.exists(t000)

class TestConcurrentRequestsSeed(SeedTestEnvironment):
    seed_conf_name = 'seed_timeouts.yaml'
    mapproxy_conf_name = 'seed_timeouts_mapproxy.yaml'
    empty_ogrdata = 'empty_ogrdata.geojson'

    def test_timeout(self):
        # test concurrent seeding where seed concurrency is higher than the permitted
        # concurrent_request value of the source and a lock times out

        seed_conf  = load_seed_tasks_conf(self.seed_conf_file, self.mapproxy_conf)
        tasks = seed_conf.seeds(['test'])

        expected_req1 = ({'path': r'/service?LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                          '&REQUEST=GetMap&VERSION=1.1.1&bbox=-180.0,-90.0,180.0,90.0'
                          '&width=256&height=128&srs=EPSG:4326'},
                        {'body': tile_image, 'headers': {'content-type': 'image/png'}, 'duration': 0.1})

        expected_req2 = ({'path': r'/service?LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                          '&REQUEST=GetMap&VERSION=1.1.1&bbox=-180.0,-90.0,180.0,90.0'
                          '&width=512&height=256&srs=EPSG:4326'},
                        {'body': tile_image, 'headers': {'content-type': 'image/png'}, 'duration': 0.1})

        expected_req3 = ({'path': r'/service?LAYERS=foo&SERVICE=WMS&FORMAT=image%2Fpng'
                          '&REQUEST=GetMap&VERSION=1.1.1&bbox=-180.0,-90.0,180.0,90.0'
                          '&width=1024&height=512&srs=EPSG:4326'},
                        {'body': tile_image, 'headers': {'content-type': 'image/png'}, 'duration': 0.1})


        with mock_httpd(('localhost', 42423), [expected_req1, expected_req2, expected_req3], unordered=True):
            seed(tasks, dry_run=False, concurrency=3)
            # concurrency=3, concurrent_request=1, client_timeout=0.2, response delay=0.1
            # the third request should time out (3x0.1 > 0.2), but exp_backoff() in the seeder ignores this
            # timeout exception and tries a second time

