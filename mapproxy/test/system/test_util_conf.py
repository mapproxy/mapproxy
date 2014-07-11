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

from __future__ import with_statement

import os
import shutil
import tempfile

import yaml

from mapproxy.script.conf.app import config_command
from mapproxy.test.helper import capture

from nose.tools import eq_


def filename(name):
    return os.path.join(
        os.path.dirname(__file__),
        'fixture',
        name,
    )

class TestMapProxyConfCmd(object):
    def setup(self):
        self.dir = tempfile.mkdtemp()

    def teardown(self):
        if os.path.exists(self.dir):
            shutil.rmtree(self.dir)

    def tmp_filename(self, name):
        return os.path.join(
            self.dir,
            name,
        )

    def test_cmd_no_args(self):
        with capture() as (stdout, stderr):
            assert config_command(['mapproxy-conf']) == 2

        assert '--capabilities required' in stderr.getvalue()

    def test_stdout_output(self):
        with capture(bytes=True) as (stdout, stderr):
            assert config_command(['mapproxy-conf', '--capabilities', filename('util-conf-wms-111-cap.xml')]) == 0

        assert stdout.getvalue().startswith(b'# MapProxy configuration')

    def test_test_cap_output_no_base(self):
        with capture(bytes=True) as (stdout, stderr):
            assert config_command(['mapproxy-conf',
                '--capabilities', filename('util-conf-wms-111-cap.xml'),
                '--output', self.tmp_filename('mapproxy.yaml'),
                ]) == 0


        with open(self.tmp_filename('mapproxy.yaml'), 'rb') as f:
            conf = yaml.load(f)

            assert 'grids' not in conf
            eq_(conf['sources'], {
                'osm_roads_wms': {
                    'supported_srs': ['CRS:84', 'EPSG:25831', 'EPSG:25832', 'EPSG:25833', 'EPSG:31466', 'EPSG:31467', 'EPSG:31468', 'EPSG:3857', 'EPSG:4258', 'EPSG:4326', 'EPSG:900913'],
                    'req': {'layers': 'osm_roads', 'url': 'http://osm.omniscale.net/proxy/service?', 'transparent': True},
                    'type': 'wms',
                    'coverage': {'srs': 'EPSG:4326', 'bbox': [-180.0, -85.0511287798, 180.0, 85.0511287798]}
                },
                'osm_wms': {
                    'supported_srs': ['CRS:84', 'EPSG:25831', 'EPSG:25832', 'EPSG:25833', 'EPSG:31466', 'EPSG:31467', 'EPSG:31468', 'EPSG:3857', 'EPSG:4258', 'EPSG:4326', 'EPSG:900913'],
                    'req': {'layers': 'osm', 'url': 'http://osm.omniscale.net/proxy/service?', 'transparent': True},
                    'type': 'wms',
                    'coverage': {
                        'srs': 'EPSG:4326',
                        'bbox': [-180.0, -85.0511287798, 180.0, 85.0511287798],
                    },
                },
            })

            eq_(conf['layers'], [{
                'title': 'Omniscale OpenStreetMap WMS',
                'layers': [
                    {
                        'name': 'osm',
                        'title': 'OpenStreetMap (complete map)',
                        'sources': ['osm_wms'],
                    },
                    {
                        'name': 'osm_roads',
                        'title': 'OpenStreetMap (streets only)',
                        'sources': ['osm_roads_wms'],
                     },
                ]
            }])
            eq_(len(conf['layers'][0]['layers']), 2)

    def test_test_cap_output(self):
        with capture(bytes=True) as (stdout, stderr):
            assert config_command(['mapproxy-conf',
                '--capabilities', filename('util-conf-wms-111-cap.xml'),
                '--output', self.tmp_filename('mapproxy.yaml'),
                '--base', filename('util-conf-base-grids.yaml'),
                ]) == 0


        with open(self.tmp_filename('mapproxy.yaml'), 'rb') as f:
            conf = yaml.load(f)

            assert 'grids' not in conf
            eq_(len(conf['sources']), 2)

            eq_(conf['caches'], {
                'osm_cache': {
                    'grids': ['webmercator', 'geodetic'],
                    'sources': ['osm_wms']
                },
                'osm_roads_cache': {
                    'grids': ['webmercator', 'geodetic'],
                    'sources': ['osm_roads_wms']
                },
            })


            eq_(conf['layers'], [{
                'title': 'Omniscale OpenStreetMap WMS',
                'layers': [
                    {
                        'name': 'osm',
                        'title': 'OpenStreetMap (complete map)',
                        'sources': ['osm_cache'],
                    },
                    {
                        'name': 'osm_roads',
                        'title': 'OpenStreetMap (streets only)',
                        'sources': ['osm_roads_cache'],
                    },
                ]
            }])
            eq_(len(conf['layers'][0]['layers']), 2)

    def test_overwrites(self):
        with capture(bytes=True) as (stdout, stderr):
            assert config_command(['mapproxy-conf',
                '--capabilities', filename('util-conf-wms-111-cap.xml'),
                '--output', self.tmp_filename('mapproxy.yaml'),
                '--overwrite', filename('util-conf-overwrite.yaml'),
                '--base', filename('util-conf-base-grids.yaml'),
                ]) == 0


        with open(self.tmp_filename('mapproxy.yaml'), 'rb') as f:
            conf = yaml.load(f)

            assert 'grids' not in conf
            eq_(len(conf['sources']), 2)

            eq_(conf['sources'], {
                'osm_roads_wms': {
                    'supported_srs': ['EPSG:3857'],
                    'req': {'layers': 'osm_roads', 'url': 'http://osm.omniscale.net/proxy/service?', 'transparent': True, 'param': 42},
                    'type': 'wms',
                    'coverage': {'srs': 'EPSG:4326', 'bbox': [0, 0, 90, 90]}
                },
                'osm_wms': {
                    'supported_srs': ['CRS:84', 'EPSG:25831', 'EPSG:25832', 'EPSG:25833', 'EPSG:31466', 'EPSG:31467', 'EPSG:31468', 'EPSG:3857', 'EPSG:4258', 'EPSG:4326', 'EPSG:900913'],
                    'req': {'layers': 'osm', 'url': 'http://osm.omniscale.net/proxy/service?', 'transparent': True, 'param': 42},
                    'type': 'wms',
                    'coverage': {
                        'srs': 'EPSG:4326',
                        'bbox': [-180.0, -85.0511287798, 180.0, 85.0511287798],
                    },
                },
            })


            eq_(conf['caches'], {
                'osm_cache': {
                    'grids': ['webmercator', 'geodetic'],
                    'sources': ['osm_wms'],
                    'cache': {
                        'type': 'sqlite'
                    },
                },
                'osm_roads_cache': {
                    'grids': ['webmercator'],
                    'sources': ['osm_roads_wms'],
                    'cache': {
                        'type': 'sqlite'
                    },
                },
            })


            eq_(conf['layers'], [{
                'title': 'Omniscale OpenStreetMap WMS',
                'layers': [
                    {
                        'name': 'osm',
                        'title': 'OpenStreetMap (complete map)',
                        'sources': ['osm_cache'],
                    },
                    {
                        'name': 'osm_roads',
                        'title': 'OpenStreetMap (streets only)',
                        'sources': ['osm_roads_cache'],
                     },
                ]
            }])
            eq_(len(conf['layers'][0]['layers']), 2)



